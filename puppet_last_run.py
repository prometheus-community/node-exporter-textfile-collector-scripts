#!/usr/bin/env python3
"""
Export Puppet agent last run summary as Prometheus text-format metrics.

Reads /opt/puppetlabs/puppet/public/last_run_summary.yaml (override with --file)
and writes metrics to stdout, suitable for the node_exporter textfile collector.

Usage:
    puppet_last_run.py [--file PATH] [--timing-metrics] [--namespace puppet]

Output:
    Prometheus text format metrics to stdout.

Error handling:
    If the last_run_summary.yaml file cannot be read or parsed, an error message
    is printed to stderr and the script emits puppet_last_run_summary_available=0.
"""

import argparse
import logging
import os
import sys

import yaml
from prometheus_client import CollectorRegistry, Gauge, Info, generate_latest

__doc__ = "Collect Puppet last run summary info as Prometheus text-format metrics."
__version__ = "0.1.0"

DEFAULT_FILE = "/opt/puppetlabs/puppet/public/last_run_summary.yaml"
APP_KEYS = ["run_mode", "initial_environment", "converged_environment"]

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def to_number(value):
    """Return value if it is an int or float, but not a bool.

    Booleans are rejected because bool is a subclass of int in Python.
    Return None for all other types.
    """
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    return value


def load_summary(path):
    """Read and parse the Puppet last_run_summary.yaml file.

    Returns a tuple of (parsed_data, mtime_seconds).  mtime is kept as a
    float to preserve sub-second precision from the filesystem.
    """
    mtime = os.stat(path).st_mtime
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise TypeError("unexpected file content")
    return data, mtime


def collect_file_metrics(registry, namespace, base, available, mtime=None):
    """Collect metrics about the last run summary file itself."""
    available_g = Gauge(
        f"{namespace}_last_run_summary_available",
        "Whether the Puppet last run summary was read and parsed.",
        APP_KEYS,
        registry=registry,
    )
    available_g.labels(**base).set(available)

    if mtime is None:
        return

    mtime_g = Gauge(
        f"{namespace}_last_run_summary_mtime_seconds",
        "Modification time of the last run summary file, in seconds since the epoch.",
        APP_KEYS,
        registry=registry,
    )
    mtime_g.labels(**base).set(mtime)


def collect_time_metrics(registry, namespace, base, data, timing_metrics):
    """Collect metrics from the time section of the summary."""
    time_section = data.get("time") or {}

    last_run = to_number(time_section.get("last_run"))
    if last_run is not None:
        ts = Gauge(
            f"{namespace}_last_run_timestamp_seconds",
            "Time of the last Puppet run, in seconds since the epoch.",
            APP_KEYS,
            registry=registry,
        )
        ts.labels(**base).set(last_run)

    total_time = to_number(time_section.get("total"))
    if total_time is not None:
        total = Gauge(
            f"{namespace}_total_run_time_seconds",
            "Total time spent in the last Puppet run, in seconds.",
            APP_KEYS,
            registry=registry,
        )
        total.labels(**base).set(total_time)

    if not timing_metrics:
        return

    time_g = Gauge(
        f"{namespace}_time_seconds",
        "Time spent in each Puppet run phase, in seconds.",
        APP_KEYS + ["resource"],
        registry=registry,
    )
    for key, value in sorted(time_section.items()):
        if key in ("last_run", "total"):
            continue
        number = to_number(value)
        if number is not None:
            time_g.labels(**base, resource=key).set(number)


def collect_version_info(registry, namespace, base, data):
    """Collect Puppet agent and catalog configuration versions as an info metric."""
    version = data.get("version") or {}
    info = Info(
        f"{namespace}_version",
        "Puppet agent and catalog configuration versions.",
        registry=registry,
    )
    info.info(
        {
            **base,
            "config_version": str(version.get("config", "")),
            "puppet_version": str(version.get("puppet", "")),
        }
    )


def collect_resource_and_event_metrics(registry, namespace, base, data):
    """Collect resources and events counts by state or type."""
    for section, doc in (
        ("resources", "Number of resources by state in the last Puppet run."),
        ("events", "Number of events by type in the last Puppet run."),
    ):
        g = Gauge(
            f"{namespace}_{section}",
            doc,
            APP_KEYS + ["state"],
            registry=registry,
        )
        for key, value in sorted((data.get(section) or {}).items()):
            number = to_number(value)
            if number is not None:
                g.labels(**base, state=key).set(number)

    changes = to_number((data.get("changes") or {}).get("total"))
    if changes is not None:
        changes_g = Gauge(
            f"{namespace}_changes",
            "Number of changes in the last Puppet run.",
            APP_KEYS,
            registry=registry,
        )
        changes_g.labels(**base).set(changes)


def main(args):
    registry = CollectorRegistry()

    try:
        data, mtime = load_summary(args.file)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        logger.error("cannot read %s: %s", args.file, exc)
        base = {k: "" for k in APP_KEYS}
        collect_file_metrics(registry, args.namespace, base, available=0)
        print(generate_latest(registry).decode(), end="")
        return 0

    application = data.get("application")
    if not isinstance(application, dict):
        application = {}
    base = {k: str(application.get(k) or "") for k in APP_KEYS}

    collect_file_metrics(registry, args.namespace, base, available=1, mtime=mtime)
    collect_time_metrics(registry, args.namespace, base, data, args.timing_metrics)
    collect_version_info(registry, args.namespace, base, data)
    collect_resource_and_event_metrics(registry, args.namespace, base, data)

    print(generate_latest(registry).decode(), end="")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect Puppet last run summary info as Prometheus text-format metrics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--file", default=DEFAULT_FILE, help="last_run_summary.yaml path")
    parser.add_argument(
        "--timing-metrics",
        action="store_true",
        help="also export per-phase durations (puppet_time_seconds)",
    )
    parser.add_argument("--namespace", default="puppet", help="metric name prefix")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()
    sys.exit(main(args))
