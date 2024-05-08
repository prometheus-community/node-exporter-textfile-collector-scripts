#!/usr/bin/env python3

"""
Description: Expose metrics from apt. This is inspired by and
intended to be a replacement for the original apt.sh.

This script deliberately does *not* update the apt cache. You need
something else to run `apt update` regularly for the metrics to be
up to date. This can be done in numerous ways, but the canonical way
is to use the normal `APT::Periodic::Update-Package-Lists`
setting.

This, for example, will enable a nightly job that runs `apt update`:

    echo 'APT::Periodic::Update-Package-Lists "1";' > /etc/apt/apt.conf.d/99_auto_apt_update.conf

See /usr/lib/apt/apt.systemd.daily for details.

Dependencies: python3-apt, python3-prometheus-client

Authors: Kyle Fazzari <kyrofa@ubuntu.com>
         Daniel Swarbrick <dswarbrick@debian.org>
"""

import apt
import apt_pkg
import collections
import os
from prometheus_client import CollectorRegistry, Gauge, generate_latest

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


def _write_pending_upgrades(registry, cache):
    candidates = {
        p.candidate for p in cache if p.is_upgradable
    }
    upgrade_list = _convert_candidates_to_upgrade_infos(candidates)

    if upgrade_list:
        g = Gauge('apt_upgrades_pending', "Apt packages pending updates by origin",
                  ['origin', 'arch'], registry=registry)
        for change in upgrade_list:
            g.labels(change.labels['origin'], change.labels['arch']).set(change.count)


def _write_held_upgrades(registry, cache):
    held_candidates = {
        p.candidate for p in cache
        if p.is_upgradable and p._pkg.selected_state == apt_pkg.SELSTATE_HOLD
    }
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


def _write_cache_timestamps(registry):
    g = Gauge('apt_package_cache_timestamp_seconds', "Apt update last run time.", registry=registry)
    apt_pkg.init_config()
    if (
        apt_pkg.config.find_b("APT::Periodic::Update-Package-Lists") and
        os.path.isfile("/var/lib/apt/periodic/update-success-stamp")
    ):
        # if we run updates automatically with APT::Periodic, we can
        # check this timestamp file if it exists
        stamp_file = "/var/lib/apt/periodic/update-success-stamp"
    else:
        # if not, let's just fallback on the partial file of the lists directory
        stamp_file = '/var/lib/apt/lists/partial'
    try:
        g.set(os.stat(stamp_file).st_mtime)
    except OSError:
        pass


def _write_reboot_required(registry):
    g = Gauge('node_reboot_required', "Node reboot is required for software updates.",
              registry=registry)
    g.set(int(os.path.isfile('/run/reboot-required')))


def _main():
    cache = apt.cache.Cache()

    registry = CollectorRegistry()
    _write_pending_upgrades(registry, cache)
    _write_held_upgrades(registry, cache)
    _write_autoremove_pending(registry, cache)
    _write_cache_timestamps(registry)
    _write_reboot_required(registry)
    print(generate_latest(registry).decode(), end='')


if __name__ == "__main__":
    _main()
