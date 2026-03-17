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
        origins = set()
        # this is like candidate.origins, but without the expensive
        # find_index() that we do not need
        for f, _ in candidate._cand.file_list:
            if f.archive == "now":
                continue
            origins.add(f"{f.origin}:{f.codename}/{f.archive}")

        changes_dict[",".join(sorted(origins))][candidate.architecture] += 1

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


# This corresponds to the apt filter "?obsolete"
def is_obsolete(p):
    # no candidate, obsolete
    if p.candidate is None:
        return True
    # replace the expensive candidate.origins lookup
    #
    # we do this because the Origin constructor performs an expensive
    # find_index() call every time, which we do not need
    origins = p.candidate._cand.file_list
    # there is a candidate, but we don't have that version
    # installed for some reason, obsolete
    if not origins:
        return True
    # origins[0] is the first origin of the file_list and
    # origins[0][0] is a lookup through the `file_list`, which returns
    # a (PackageFile, offset) tuple, and the PackageFile is what we're
    # interested in.
    if len(origins) == 1 and origins[0][0].origin in ["", "/var/lib/dpkg/status"]:
        return True


def _write_packages_states(registry, cache, exclusions):
    installed_packages = set()
    upgrade_candidates = set()
    autoremovable_packages = set()
    obsoletes = []
    held_candidates = set()

    # apt_pkg.CURSTATE_CONFIG_FILES
    #
    #     Only the configuration files of the package exist on the system.
    #
    # apt_pkg.CURSTATE_HALF_CONFIGURED
    #
    #     The package is unpacked and configuration has been started, but not yet completed.
    #
    # apt_pkg.CURSTATE_HALF_INSTALLED
    #
    #     The installation of the package has been started, but not completed.
    #
    # apt_pkg.CURSTATE_INSTALLED
    #
    #     The package is unpacked, configured and OK.
    #
    # apt_pkg.CURSTATE_NOT_INSTALLED
    #
    #     The package is not installed.
    #
    # apt_pkg.CURSTATE_UNPACKED
    #
    #     The package is unpacked, but not configured.
    states_to_text = {
        apt_pkg.CURSTATE_CONFIG_FILES: "config-files",
        apt_pkg.CURSTATE_HALF_CONFIGURED: "half-configured",
        apt_pkg.CURSTATE_HALF_INSTALLED: "half-installed",
        apt_pkg.CURSTATE_INSTALLED: "installed",
        apt_pkg.CURSTATE_NOT_INSTALLED: "not-installed",
        apt_pkg.CURSTATE_UNPACKED: "unpacked",
    }
    # counter for the various values
    #
    # we don't use the inc() function here because it's too slow for
    # the hot loop
    states_counts = {}
    for key, value in states_to_text.items():
        states_counts[key] = 0

    for package in cache:
        label_name = states_to_text.get(package._pkg.current_state, None)
        if label_name is None:
            logging.warning("unknown package state for package %s: %s", package, package._pkg.current_state)
        else:
            states_counts[package._pkg.current_state]+=1

        if package.is_installed:
            installed_packages.add(package.candidate)

        if package.name in exclusions:
            continue

        if package.is_upgradable:
            upgrade_candidates.add(package.candidate)

        if package.is_auto_removable:
            autoremovable_packages.add(package.candidate)

        if package.is_installed and is_obsolete(package):
            obsoletes.append(package)

        # Package.phasing_applied is not available in debian bookworm
        # would be: and not p.phasing_applied
        if package.is_upgradable and package._pkg.selected_state == apt_pkg.SELSTATE_HOLD:
            held_candidates.add(package.candidate)

    # installed packages per origin
    packages_per_origin_count = Gauge('apt_packages_per_origin_count', "Number of packages installed per origin.", ['origin', 'arch'], registry=registry)
    per_origin = _convert_candidates_to_upgrade_infos(installed_packages)

    if per_origin:
        for o in per_origin:
            packages_per_origin_count.labels(o.labels['origin'], o.labels['arch']).set(o.count)

    # upgradable packages
    for candidate in upgrade_candidates:
        logging.debug(
            "pending upgrade: %s / %s",
            candidate.package,
            candidate.architecture,
        )
    upgrade_list = _convert_candidates_to_upgrade_infos(upgrade_candidates)

    if upgrade_list:
        g = Gauge('apt_upgrades_pending', "Apt packages pending updates by origin",
                  ['origin', 'arch'], registry=registry)
        for change in upgrade_list:
            g.labels(change.labels['origin'], change.labels['arch']).set(change.count)

    # autoremove packages
    for candidate in autoremovable_packages:
        logging.debug(
            "autoremovable package: %s / %s",
            candidate.package,
            candidate.architecture,
        )

    g = Gauge('apt_autoremove_pending', "Apt packages pending autoremoval.",
              registry=registry)
    g.set(len(autoremovable_packages))

    # obsolete packages
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

    # held packages
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

    # other package states
    packages_count = Gauge('apt_packages_count', "Apt packages count.", ['state'], registry=registry)
    for key, label_name in states_to_text.items():
        packages_count.labels(label_name).set(states_counts[key])


def _write_cache_timestamps(registry):
    g = Gauge('apt_package_cache_timestamp_seconds', "Apt update last run time.", registry=registry)
    apt_pkg.init_config()
    if os.path.isfile("/var/lib/apt/periodic/update-success-stamp"):
        # this file is often used as a flag file for sucessful runs on
        # systems that do not use apt-periodic features, namely
        # apt-config-auto-update and the Puppetlabs "apt" puppet
        # module.
        #
        # Example configuration:
        #
        # APT::Update::Post-Invoke-Success {"touch /var/lib/apt/periodic/update-success-stamp";};
        stamp_file = "/var/lib/apt/periodic/update-success-stamp"
    elif apt_pkg.config.find_b("APT::Periodic::Update-Package-Lists"):
        # if we run updates automatically with APT::Periodic, we can
        # check this timestamp file
        stamp_file = "/var/lib/apt/periodic/update-stamp"
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
    _write_packages_states(registry, cache, args.exclude)
    _write_cache_timestamps(registry)
    _write_reboot_required(registry)
    print(generate_latest(registry).decode(), end='')


if __name__ == "__main__":
    _main()
