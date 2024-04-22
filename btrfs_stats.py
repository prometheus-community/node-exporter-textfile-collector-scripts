#!/usr/bin/env python3

# Collect per-device btrfs filesystem errors. Designed to work on Debian and Centos 6 and later.
# Requires btrfs-progs package to be installed.
#
# Consider using node_exporter's built-in btrfs collector instead of this script.

import glob
import os.path
import re
import subprocess
from prometheus_client import CollectorRegistry, Gauge, generate_latest


DEVICE_PATTERN = re.compile(r"^\[([^\]]+)\]\.(\S+)\s+(\d+)$")


def get_btrfs_mount_points():
    """List all btrfs mount points.

    Yields:
        (string) filesystem mount points.
    """
    with open("/proc/mounts") as f:
        for line in f:
            parts = line.split()
            if parts[2] == "btrfs":
                yield parts[1]


def get_btrfs_errors(mountpoint):
    """Get per-device errors for a btrfs mount point.

    Args:
        mountpoint: (string) path to a mount point.

    Yields:
        (device, error_type, error_count) tuples, where:
            device: (string) path to block device.
            error_type: (string) type of btrfs error.
            error_count: (int) number of btrfs errors of a given type.
    """
    p = subprocess.Popen(["btrfs", "device", "stats", mountpoint],
                         stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("btrfs returned exit code %d" % p.returncode)
    for line in stdout.splitlines():
        if not line:
            continue
        # Sample line:
        # [/dev/vdb1].flush_io_errs   0
        m = DEVICE_PATTERN.match(line.decode("utf-8"))
        if not m:
            raise RuntimeError("unexpected output from btrfs: '%s'" % line)
        yield m.group(1), m.group(2), int(m.group(3))


def btrfs_error_metrics(registry):
    """Collect btrfs error metrics."""
    g = Gauge('errors_total', 'number of btrfs errors',
              ['mountpoint', 'device', 'type'],
              namespace='node_btrfs', registry=registry)

    for mountpoint in get_btrfs_mount_points():
        for device, error_type, error_count in get_btrfs_errors(mountpoint):
            g.labels(mountpoint, device, error_type).set(error_count)


def btrfs_allocation_metrics(registry):
    """Collect btrfs allocation metrics."""
    metric_to_filename = {
        'size_bytes': 'total_bytes',
        'used_bytes': 'bytes_used',
        'reserved_bytes': 'bytes_reserved',
        'pinned_bytes': 'bytes_pinned',
        'disk_size_bytes': 'disk_total',
        'disk_used_bytes': 'disk_used',
    }

    metrics = {}
    for m, f in metric_to_filename.items():
        metrics[m] = Gauge(m, 'btrfs allocation data ({})'.format(f),
                           ['fs', 'type'],
                           namespace='node_btrfs', subsystem='allocation', registry=registry)

    for alloc in glob.glob("/sys/fs/btrfs/*/allocation"):
        fs = os.path.basename(os.path.dirname(alloc))
        for type_ in ('data', 'metadata', 'system'):
            for m, f in metric_to_filename.items():
                filename = os.path.join(alloc, type_, f)
                with open(filename) as f:
                    value = int(f.read().strip())
                    metrics[m].labels(fs, type_).set(value)


if __name__ == "__main__":
    registry = CollectorRegistry()
    btrfs_error_metrics(registry)
    btrfs_allocation_metrics(registry)
    print(generate_latest(registry).decode(), end='')
