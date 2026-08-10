#!/usr/bin/env python3
#
# Description: Process borgmatic json output to collect backup metrics
# Usage:
# 1. Run "borgmatic --verbosity -1 --syslog-verbosity -1 --json > borgmatic.json"
# 2. Run "borgmatic_metrics.py borgmatic.json | sponge /var/lib/node_exporter/borgmatic.prom"
#

import json
import datetime
import sys


METRIC_PREFIX = "borgmatic_backup_"


def __fill_metric(metrics, name, labels, value, timestamp=None):
    real_name = f"{METRIC_PREFIX}{name}"
    if real_name not in metrics:
        metrics.update({real_name: []})

    metric = {}
    metric.update({"labels": labels})
    metric.update({"value": value})
    if timestamp is not None:
        metric.update({"timestamp": timestamp})

    metrics[real_name].append(metric)


def __print_metrics(metrics, metrics_meta):
    for metric in metrics:
        metric_description = metrics_meta[metric]["help"]
        print(f"# HELP {metric} {metric_description}")

        metric_type = metrics_meta[metric]["type"]
        print(f"# TYPE {metric} {metric_type}")

        for entry in metrics[metric]:
            __labels3 = entry["labels"].items()
            __labels2 = [(k, f'"{v}"') for k, v in __labels3]
            __labels1 = ["=".join(x) for x in __labels2]
            labels = ",".join(__labels1)
            value = entry["value"]
            time = entry["timestamp"]
            print(f"{metric}{{{labels}}} {value} {time}")


def process_borgmatic_results(results):
    metrics = {}
    metrics_meta = {
        f"{METRIC_PREFIX}success": {
            "type": "gauge",
            "help": "Whether a borgmatic operation succeeded.",
        },
        f"{METRIC_PREFIX}duration_seconds": {
            "type": "gauge",
            "help": "Duration of a borgmatic operation.",
        },
        f"{METRIC_PREFIX}latest_archive_files": {
            "type": "gauge",
            "help": "Number of files within latest backuped archive.",
        },
        f"{METRIC_PREFIX}latest_archive_original_size_bytes": {
            "type": "gauge",
            "help": "Original size of a latest backup archive.",
        },
        f"{METRIC_PREFIX}latest_archive_compressed_size_bytes": {
            "type": "gauge",
            "help": "Compressed size of a latest backup archive.",
        },
        f"{METRIC_PREFIX}latest_archive_deduplicated_size_bytes": {
            "type": "gauge",
            "help": "Deduplicated size of a latest backup archive.",
        },
    }

    for entry in results:
        if not all(
            x in entry
            for x in ["archive", "cache", "encryption", "repository"]
        ):
            # skip invalid objects within array of borgmatic response
            continue

        labels = {
            "repository_id": entry["repository"]["id"],
        }

        # converted from seconds to milliseconds
        metric_timestamp = int(
            datetime.datetime.strptime(
                entry["archive"]["end"], "%Y-%m-%dT%H:%M:%S.%f"
            ).timestamp()
            * 1000
        )

        metric_success = int(
            entry["archive"]["end"] == entry["repository"]["last_modified"]
        )
        __fill_metric(
            metrics, "success", labels, metric_success, metric_timestamp
        )

        metric_duration_seconds = float(entry["archive"]["duration"])
        __fill_metric(
            metrics,
            "duration_seconds",
            labels,
            metric_duration_seconds,
            metric_timestamp,
        )

        metric_latest_archive_files = int(entry["archive"]["stats"]["nfiles"])
        __fill_metric(
            metrics,
            "latest_archive_files",
            labels,
            metric_latest_archive_files,
            metric_timestamp,
        )

        metric_latest_archive_original_size_bytes = int(
            entry["archive"]["stats"]["original_size"]
        )
        __fill_metric(
            metrics,
            "latest_archive_original_size_bytes",
            labels,
            metric_latest_archive_original_size_bytes,
            metric_timestamp,
        )

        metric_latest_archive_compressed_size_bytes = int(
            entry["archive"]["stats"]["compressed_size"]
        )
        __fill_metric(
            metrics,
            "latest_archive_compressed_size_bytes",
            labels,
            metric_latest_archive_compressed_size_bytes,
            metric_timestamp,
        )

        metric_latest_archive_deduplicated_size_bytes = int(
            entry["archive"]["stats"]["deduplicated_size"]
        )
        __fill_metric(
            metrics,
            "latest_archive_deduplicated_size_bytes",
            labels,
            metric_latest_archive_deduplicated_size_bytes,
            metric_timestamp,
        )

    __print_metrics(metrics, metrics_meta)


if __name__ == "__main__":
    results = []

    if len(sys.argv) != 2:
        print(
            f"{sys.argv[0]}: You must specify ONLY full path to the file "
            "with borgmatic output in json format."
        )
        sys.exit(-1)

    with open(sys.argv[1], "r") as f:
        results = json.load(f)

    process_borgmatic_results(results)
