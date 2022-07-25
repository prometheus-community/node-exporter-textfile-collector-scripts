#!/usr/bin/env python3
#
# Description: Expose metrics from apt. This is inspired by and
# intended to be a replacement for the original apt.sh.
#
# Dependencies: python3-apt
#
# Author: Kyle Fazzari <kyrofa@ubuntu.com>

import apt
import collections
import contextlib
import os

_UpgradeInfo = collections.namedtuple("_UpgradeInfo", ["labels", "count"])


def _convert_candidates_to_upgrade_infos(candidates):
    changes_dict = collections.defaultdict(lambda: collections.defaultdict(int))

    for candidate in candidates:
        origins = sorted(
            {f"{o.origin}:{o.codename}/{o.archive}" for o in candidate.origins}
        )
        changes_dict[",".join(origins)][candidate.architecture] += 1

    changes_list = list()
    for origin in sorted(changes_dict.keys()):
        for arch in sorted(changes_dict[origin].keys()):
            changes_list.append(
                _UpgradeInfo(
                    labels=dict(origin=origin, arch=arch),
                    count=changes_dict[origin][arch],
                )
            )

    return changes_list


def _write_upgrade_info(key, candidates):
    upgrade_list = _convert_candidates_to_upgrade_infos(candidates)

    if upgrade_list:
        for change in upgrade_list:
            labels = [f'{key}="{value}"' for key, value in change.labels.items()]
            print(f'{key}{{{",".join(labels)}}} {change.count}')
    else:
        print(f'{key}{{origin="",arch=""}} 0')


def _write_pending_upgrades(cache):
    print("# HELP apt_upgrades_pending Apt packages pending updates by origin.")
    print("# TYPE apt_upgrades_pending gauge")

    # Discount any changes that apply to packages that aren't installed (e.g.
    # count an upgrade to package A that adds a new dependency on package B as
    # only one upgrade, not two). See the following issue for more details:
    # https://github.com/prometheus-community/node-exporter-textfile-collector-scripts/issues/85
    candidates = {
        p.candidate for p in cache.get_changes() if p.is_installed and p.marked_upgrade
    }
    _write_upgrade_info("apt_upgrades_pending", candidates)


def _write_held_upgrades(cache):
    print("# HELP apt_upgrades_held Apt packages pending updates but held back.")
    print("# TYPE apt_upgrades_held gauge")

    held_candidates = {p.candidate for p in cache if p.is_upgradable and p.marked_keep}
    _write_upgrade_info("apt_upgrades_held", held_candidates)


def _write_autoremove_pending(cache):
    autoremovable_packages = {p for p in cache if p.is_auto_removable}

    print("# HELP apt_autoremove_pending Apt packages pending autoremoval.")
    print("# TYPE apt_autoremove_pending gauge")
    print(f"apt_autoremove_pending {len(autoremovable_packages)}")


def _write_reboot_required():
    print("# HELP node_reboot_required Node reboot is required for software updates.")
    print("# TYPE node_reboot_required gauge")
    if os.path.isfile(os.path.join(os.path.sep, "run", "reboot-required")):
        print("node_reboot_required 1")
    else:
        print("node_reboot_required 0")


def _main():
    cache = apt.cache.Cache()

    # First of all, attempt to update the index. If we don't have permission
    # to do so (or it fails for some reason), it's not the end of the world,
    # we'll operate on the old index.
    with contextlib.suppress(apt.cache.LockFailedException, apt.cache.FetchFailedException):
        cache.update()

    cache.open()
    cache.upgrade(True)
    _write_pending_upgrades(cache)
    _write_held_upgrades(cache)
    _write_autoremove_pending(cache)
    _write_reboot_required()


if __name__ == "__main__":
    _main()
