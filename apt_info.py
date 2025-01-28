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
import argparse
import collections
import logging
import os
import sys
from prometheus_client import CollectorRegistry, Gauge, generate_latest

_UpgradeInfo = collections.namedtuple("_UpgradeInfo", ["labels", "count"])


def _convert_candidates_to_upgrade_infos(candidates):
    changes_dict = collections.defaultdict(lambda: collections.defaultdict(int))

    for candidate in candidates:
        # The 'now' archive only shows that packages are not installed. We tend
        # to filter the candidates on those kinds of conditions before reaching
        # here so here we don't want to include this information in order to
        # reduce noise in the data.
        origins = sorted(
            {f"{o.origin}:{o.codename}/{o.archive}" for o in candidate.origins
             if o.archive != 'now'}
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


def _write_pending_upgrades(registry, cache, exclusions):
    candidates = {
        p.candidate
        for p in cache
        if p.is_upgradable and not p.phasing_applied and p.name not in exclusions
    }
    for candidate in candidates:
        logging.debug(
            "pending upgrade: %s / %s",
            candidate.package,
            candidate.architecture,
        )
    upgrade_list = _convert_candidates_to_upgrade_infos(candidates)

    if upgrade_list:
        g = Gauge('apt_upgrades_pending', "Apt packages pending updates by origin",
                  ['origin', 'arch'], registry=registry)
        for change in upgrade_list:
            g.labels(change.labels['origin'], change.labels['arch']).set(change.count)


def _write_held_upgrades(registry, cache, exclusions):
    held_candidates = {
        p.candidate for p in cache
        if (
            p.is_upgradable
            and p._pkg.selected_state == apt_pkg.SELSTATE_HOLD
            and not p.phasing_applied
            and p.name not in exclusions
        )
    }
    for candidate in held_candidates:
        logging.debug(
            "held upgrade: %s / %s",
            candidate.package,
            candidate.architecture,
        )
    upgrade_list = _convert_candidates_to_upgrade_infos(held_candidates)

    if upgrade_list:
        g = Gauge('apt_upgrades_held', "Apt packages pending updates but held back.",
                  ['origin', 'arch'], registry=registry)
        for change in upgrade_list:
            g.labels(change.labels['origin'], change.labels['arch']).set(change.count)


def _write_obsolete_packages(registry, cache, exclusions):
    # This corresponds to the apt filter "?obsolete"
    obsoletes = [p for p in cache if p.is_installed and (
                  p.candidate is None or
                  not p.candidate.origins or
                  (len(p.candidate.origins) == 1 and
                   p.candidate.origins[0].origin in ['', "/var/lib/dpkg/status"])
                  and p.name not in exclusions
                )]
    for package in obsoletes:
        if package.candidate is None:
            logging.debug("obsolete package with no candidate: %s", package)
        else:
            logging.debug(
                "obsolete package: %s / %s",
                package,
                package.candidate.architecture,
            )

    g = Gauge('apt_packages_obsolete_count', "Apt packages which are obsolete",
              registry=registry)
    g.set(len(obsoletes))


def _write_autoremove_pending(registry, cache, exclusions):
    autoremovable_packages = {
        p.candidate
        for p in cache
        if p.is_auto_removable and p.name not in exclusions
    }
    for candidate in autoremovable_packages:
        logging.debug(
            "autoremovable package: %s / %s",
            candidate.package,
            candidate.architecture,
        )
    g = Gauge('apt_autoremove_pending', "Apt packages pending autoremoval.",
              registry=registry)
    g.set(len(autoremovable_packages))


def _write_installed_packages_per_origin(registry, cache):
    installed_packages = {p.candidate for p in cache if p.is_installed}
    per_origin = _convert_candidates_to_upgrade_infos(installed_packages)

    if per_origin:
        g = Gauge('apt_packages_per_origin_count', "Number of packages installed per origin.",
                  ['origin', 'arch'], registry=registry)
        for o in per_origin:
            g.labels(o.labels['origin'], o.labels['arch']).set(o.count)


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
    if os.getenv('DEBUG'):
        logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude", nargs='*', default=[])
    args = parser.parse_args(sys.argv[1:])

    cache = apt.cache.Cache()

    registry = CollectorRegistry()
    _write_pending_upgrades(registry, cache, args.exclude)
    _write_held_upgrades(registry, cache, args.exclude)
    _write_obsolete_packages(registry, cache, args.exclude)
    _write_autoremove_pending(registry, cache, args.exclude)
    _write_installed_packages_per_origin(registry, cache)
    _write_cache_timestamps(registry)
    _write_reboot_required(registry)
    print(generate_latest(registry).decode(), end='')


if __name__ == "__main__":
    _main()
