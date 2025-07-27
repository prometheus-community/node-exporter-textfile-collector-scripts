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

import collections
import os
import sys
from typing import Dict, Iterable, List, NamedTuple

# Gracefully handle missing dependencies, which is a common operational issue.
try:
    import apt
    import apt_pkg
    from prometheus_client import CollectorRegistry, Gauge, generate_latest
except ImportError as e:
    sys.stderr.write(f"Error: Missing required library. {e}\n")
    sys.stderr.write("Please install python3-apt and python3-prometheus-client.\n")
    sys.exit(1)


# Using a class-based structure for the named tuple for better type hinting.
class UpgradeInfo(NamedTuple):
    labels: Dict[str, str]
    count: int


def _convert_candidates_to_upgrade_infos(
    candidates: Iterable[apt.package.Package],
) -> List[UpgradeInfo]:
    """Groups package candidates by origin and architecture."""
    changes_dict = collections.defaultdict(lambda: collections.defaultdict(int))

    for candidate in candidates:
        # Gracefully handle packages with no origins.
        if not candidate.origins:
            origin_str = "unknown"
        else:
            origins = sorted(
                {f"{o.origin}:{o.codename}/{o.archive}" for o in candidate.origins}
            )
            origin_str = ",".join(origins)

        changes_dict[origin_str][candidate.architecture] += 1

    changes_list = []
    for origin, arch_counts in sorted(changes_dict.items()):
        for arch, count in sorted(arch_counts.items()):
            changes_list.append(
                UpgradeInfo(
                    labels=dict(origin=origin, arch=arch),
                    count=count,
                )
            )

    return changes_list


def _write_pending_upgrades(
    registry: CollectorRegistry, cache: apt.cache.Cache
) -> None:
    """Exposes metrics for all pending upgrades."""
    candidates = {p.candidate for p in cache if p.is_upgradable}
    upgrade_list = _convert_candidates_to_upgrade_infos(candidates)

    if upgrade_list:
        g = Gauge(
            "apt_upgrades_pending",
            "Apt packages pending updates by origin",
            ["origin", "arch"],
            registry=registry,
        )
        for change in upgrade_list:
            g.labels(**change.labels).set(change.count)


def _write_held_upgrades(registry: CollectorRegistry, cache: apt.cache.Cache) -> None:
    """Exposes metrics for held packages that could be upgraded."""
    held_candidates = {
        p.candidate
        for p in cache
        if p.is_upgradable and p._pkg.selected_state == apt_pkg.SELSTATE_HOLD
    }
    upgrade_list = _convert_candidates_to_upgrade_infos(held_candidates)

    if upgrade_list:
        g = Gauge(
            "apt_upgrades_held",
            "Apt packages pending updates but held back",
            ["origin", "arch"],
            registry=registry,
        )
        for change in upgrade_list:
            g.labels(**change.labels).set(change.count)


def _write_autoremove_pending(
    registry: CollectorRegistry, cache: apt.cache.Cache
) -> None:
    """Exposes metrics for packages pending autoremoval."""
    autoremovable_packages = {p for p in cache if p.is_auto_removable}
    g = Gauge(
        "apt_autoremove_pending",
        "Apt packages pending autoremoval",
        registry=registry,
    )
    g.set(len(autoremovable_packages))


def _write_cache_timestamps(registry: CollectorRegistry) -> None:
    """Exposes the timestamp of the last successful apt update."""
    g = Gauge(
        "apt_package_cache_timestamp_seconds",
        "Apt update last run time",
        registry=registry,
    )
    stamp_file = None
    try:
        apt_pkg.init_config()
        # Prefer the official periodic update stamp file if it exists.
        periodic_stamp = "/var/lib/apt/periodic/update-success-stamp"
        if (
            apt_pkg.config.find_b("APT::Periodic::Update-Package-Lists", "0") != "0"
            and os.path.isfile(periodic_stamp)
        ):
            stamp_file = periodic_stamp
        else:
            # Fallback to the partial directory mtime as a less accurate indicator.
            stamp_file = "/var/lib/apt/lists/partial"

        g.set(os.stat(stamp_file).st_mtime)
    except FileNotFoundError:
        # This is a common case if apt update has never run; not an error.
        sys.stderr.write(f"Warning: Timestamp file not found: {stamp_file}\n")
    except OSError as e:
        # This indicates a more serious issue, like a permissions error.
        sys.stderr.write(f"Warning: Could not read timestamp file {stamp_file}: {e}\n")


def _write_reboot_required(registry: CollectorRegistry) -> None:
    """Exposes a metric indicating if a reboot is required."""
    g = Gauge(
        "node_reboot_required",
        "Node reboot is required for software updates",
        registry=registry,
    )
    g.set(float(os.path.isfile("/run/reboot-required")))


def main() -> int:
    """Main entry point for the script."""
    try:
        # Explicitly open the cache to catch errors early.
        # The 'progress' argument is omitted for non-interactive use.
        cache = apt.cache.Cache()
        cache.open()
    except apt.cache.LockingFailedException as e:
        sys.stderr.write(
            f"Error: Failed to lock apt cache. Is another apt process running? {e}\n"
        )
        return 1
    except SystemError as e:
        sys.stderr.write(
            f"Error: Failed to initialize apt cache. Check permissions and configuration. {e}\n"
        )
        return 1

    registry = CollectorRegistry()
    _write_pending_upgrades(registry, cache)
    _write_held_upgrades(registry, cache)
    _write_autoremove_pending(registry, cache)
    _write_cache_timestamps(registry)
    _write_reboot_required(registry)

    # Print the metrics to standard output.
    print(generate_latest(registry).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
