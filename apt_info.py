#!/usr/bin/env python3
#
# Description: Expose metrics from apt. This is inspired by and
# intended to be a replacement for the original apt.sh.
#
# This script deliberately does *not* update the apt cache. You need
# something else to run `apt update` regularly for the metrics to be
# up to date. This can be done in numerous ways, but the canonical way
# is to use the normal `APT::Periodic::Update-Package-Lists`
# setting.
#
# This, for example, will enable a nightly job that runs `apt update`:
#
#     echo 'APT::Periodic::Update-Package-Lists "1";' > /etc/apt/apt.conf.d/99_auto_apt_update.conf
#
# See /usr/lib/apt/apt.systemd.daily for details.
#
# Dependencies: python3-apt, python3-prometheus-client
#
# Authors: Kyle Fazzari <kyrofa@ubuntu.com>
#          Daniel Swarbrick <dswarbrick@debian.org>

import argparse
import collections
import os
import apt
import apt_pkg
from prometheus_client import CollectorRegistry, Gauge, generate_latest

_UpgradeInfo = collections.namedtuple("_UpgradeInfo", ["labels", "count"])


def _convert_candidates_to_upgrade_infos(candidates):
    changes_dict = collections.defaultdict(lambda: collections.defaultdict(int))

    for candidate in candidates:
        origins = sorted(
            {f"{o.origin}:{o.codename}/{o.archive}" for o in candidate.origins}
        )
        changes_dict[",".join(origins)][candidate.architecture] += 1

    changes_list = []
    for origin in sorted(changes_dict.keys()):
        for arch in sorted(changes_dict[origin].keys()):
            changes_list.append(
                _UpgradeInfo(
                    labels={"origin": origin, "arch": arch},
                    count=changes_dict[origin][arch],
                )
            )

    return changes_list


def _write_pending_upgrades(registry, cache):
    # Discount any changes that apply to packages that aren't installed (e.g.
    # count an upgrade to package A that adds a new dependency on package B as
    # only one upgrade, not two). See the following issue for more details:
    # https://github.com/prometheus-community/node-exporter-textfile-collector-scripts/issues/85
    candidates = {
        p.candidate for p in cache.get_changes() if p.is_installed and p.marked_upgrade
    }
    upgrade_list = _convert_candidates_to_upgrade_infos(candidates)

    if upgrade_list:
        g = Gauge('apt_upgrades_pending', "Apt packages pending updates by origin",
                  ['origin', 'arch'], registry=registry)
        for change in upgrade_list:
            g.labels(change.labels['origin'], change.labels['arch']).set(change.count)


def _write_held_upgrades(registry, cache):
    held_candidates = {p.candidate for p in cache if p.is_upgradable and p.marked_keep}
    upgrade_list = _convert_candidates_to_upgrade_infos(held_candidates)

    if upgrade_list:
        g = Gauge('apt_upgrades_held', "Apt packages pending updates but held back.",
                  ['origin', 'arch'], registry=registry)
        for change in upgrade_list:
            g.labels(change.labels['origin'], change.labels['arch']).set(change.count)


def _write_autoremove_pending(registry, cache):
    autoremovable_packages = {p for p in cache if p.is_auto_removable}
    g = Gauge('apt_autoremove_pending', "Apt packages pending autoremoval.",
              registry=registry)
    g.set(len(autoremovable_packages))


def _write_cache_timestamps(registry, root_dir):
    g = Gauge('apt_package_cache_timestamp_seconds', "Apt update last run time.", registry=registry)
    apt_pkg.init_config()
    if apt_pkg.config.find_b("APT::Periodic::Update-Package-Lists"):
        # if we run updates automatically with APT::Periodic, we can
        # check this timestamp file
        stamp_file = os.path.join(root_dir, 'var/lib/apt/periodic/update-success-stamp')
    else:
        # if not, let's just fallback on the lists directory
        stamp_file = os.path.join(root_dir, 'var/lib/apt/lists')
    try:
        g.set(os.stat(stamp_file).st_mtime)
    except OSError:
        pass


def _write_reboot_required(registry, root_dir):
    g = Gauge('node_reboot_required', "Node reboot is required for software updates.",
              registry=registry)
    g.set(int(os.path.isfile(os.path.join(root_dir, 'run/reboot-required'))))


def generate_metrics(root_dir: str = '/') -> bytes:
    cache = apt.cache.Cache(rootdir=root_dir)
    registry = CollectorRegistry()

    _write_pending_upgrades(registry, cache)
    _write_held_upgrades(registry, cache)
    _write_autoremove_pending(registry, cache)
    _write_cache_timestamps(registry, root_dir)
    _write_reboot_required(registry, root_dir)

    return generate_latest(registry)


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--root-dir', dest='root_dir', type=str, default='/',
                        help="Set root directory to a different path than /")
    args = parser.parse_args()

    metrics = generate_metrics(args.root_dir)

    print(metrics.decode(), end='')


if __name__ == "__main__":
    _main()
