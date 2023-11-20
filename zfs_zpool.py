#!/usr/bin/env python3
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

from prometheus_client import CollectorRegistry, Gauge, generate_latest

ZPOOL_METADATA_LABELS = ("health", "version", "readonly", "ashift", "autoreplace", "failmode")


def zpool_metadata(registry):
    metric = Gauge("zpool", "Constant metric with metadata about the zpool",
                   labelnames=['zpool_name', *ZPOOL_METADATA_LABELS], namespace='zfs', registry=registry, )
    cmd = ('zpool', 'list', '-H', '-o', 'name,' + ",".join(ZPOOL_METADATA_LABELS))
    for constant_labels in run(cmd):
        metric.labels(*constant_labels).set(1)


def run(cmd):
    popen = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, env=dict(os.environ, LC_ALL="C")
    )
    for stdout_line in iter(popen.stdout.readline, ""):
        if stdout_line == b"":
            break
        yield stdout_line.strip().decode("utf-8").split("\t")

    return_code = popen.wait()
    if return_code > 0:
        raise subprocess.CalledProcessError(return_code, cmd)


ZPOOL_INFO_METRICS = (
    ("size", "Total size of the storage pool", "bytes"),
    ("free", "The amount of free space available in the pool", "bytes"),
    ("freeing", "The amount of space waiting to be reclaimed from destroyed filesystems or snapshots", "bytes"),
    ('dedupratio', "The deduplication ratio", ""),
    ("fragmentation", "The amount of fragmentation in the pool", "")
)


def zpool_info(registry):
    cmd = ('zpool', 'list', '-Hp', '-o', "name," + ','.join([col for (col, *_) in ZPOOL_INFO_METRICS]))
    metrics = {}
    for line in run(cmd):
        for (idx, (col, doc, unit)) in enumerate(ZPOOL_INFO_METRICS, 1):
            if col not in metrics:
                metrics[col] = Gauge(col, documentation=doc, unit=unit, namespace='zfs_zpool', registry=registry,
                                     labelnames=["zpool_name"])
            metrics[col].labels((line[0])).set(float(line[idx]))


DATASET_METADATA_LABELS = ("type", "creation", "mounted", "mountpoint", "checksum", "compression", "readonly",
                           "version", "dedup", "volblocksize")

DATASET_TYPES = ("filesystem", "volume")


def dataset_metadata(registry):
    cmd = ("zfs", "list", "-Hp", "-t", ",".join(DATASET_TYPES), "-o", "name," + ",".join(DATASET_METADATA_LABELS))
    metric = Gauge("dataset", documentation="Constant metric with metadata about the zfs dataset", namespace="zfs",
                   registry=registry, labelnames=["dataset_name", *DATASET_METADATA_LABELS])
    for line in run(cmd):
        metric.labels(*line).set(1)


DATASET_INFO_METRICS = (
    ("used", "The amount of space consumed by this dataset and all its descendents", "bytes"),
    ("available", "The amount of space available to the dataset and all its children", "bytes"),
    ("referenced",
     "The amount of data that is accessible by this dataset, which may or may not be shared with other datasets in the pool",
     "bytes"),
    ("compressratio",
     "For non-snapshots, the compression ratio achieved for the used space of this dataset, expressed as a multiplier",
     ""),
    ("reservation", "The minimum amount of space guaranteed to a dataset and its descendants", "bytes"),
    ("refreservation", "The minimum amount of space guaranteed to a dataset, not including its descendents", "bytes"),
    ("volsize", "For volumes, specifies the logical size of the volume", "bytes")
)


def dataset_metrics(registry):
    cmd = ("zfs", "list", "-Hp", "-t", ",".join(DATASET_TYPES), "-o", "name," + ",".join([col for (col, *_) in DATASET_INFO_METRICS]))
    metrics = {}
    for line in run(cmd):
        for (idx, (col, doc, unit)) in enumerate(DATASET_INFO_METRICS, 1):
            if col not in metrics:
                metrics[col] = Gauge(col, documentation=doc, unit=unit, registry=registry, labelnames=["dataset_name"],
                                     namespace="zfs_dataset")

            if line[idx] == "-":
                continue

            metrics[col].labels((line[0])).set(float(line[idx].rstrip("x")))


def main():
    registry = CollectorRegistry()

    funcs = (zpool_metadata, zpool_info, dataset_metadata, dataset_metrics)
    with ThreadPoolExecutor(max_workers=len(funcs)) as executor:
        for func in funcs:
            executor.submit(func, registry)

    print(generate_latest(registry).decode(), end="")


main()
