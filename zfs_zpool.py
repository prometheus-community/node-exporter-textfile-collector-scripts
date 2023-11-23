#!/usr/bin/env python3
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import reduce
from prometheus_client import CollectorRegistry, Gauge, generate_latest

ZPOOL_METADATA_LABELS = ('health', 'version', 'readonly', 'ashift', 'autoreplace', 'failmode')


def zpool_metadata(registry: CollectorRegistry):
    metric = Gauge('zpool', 'Constant metric with metadata about the zpool',
                   labelnames=['zpool_name', *ZPOOL_METADATA_LABELS], namespace='zfs', registry=registry)
    cmd = ('zpool', 'list', '-H', '-o', 'name,' + ','.join(ZPOOL_METADATA_LABELS))
    for constant_labels in run_tabular(cmd):
        metric.labels(*constant_labels)


def run(cmd: tuple[str, ...]):
    popen = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, env=dict(os.environ, LC_ALL='C')
    )

    if popen.stdout is None:
        return

    for stdout_line in iter(popen.stdout.readline, ''):
        if stdout_line == b'':
            break
        yield stdout_line.decode('utf-8')

    return_code = popen.wait()
    if return_code > 0:
        raise subprocess.CalledProcessError(return_code, cmd)


def run_tabular(cmd):
    for line in run(cmd):
        yield line.strip().split('\t')


ZPOOL_INFO_METRICS = (
    ('size', 'Total size of the storage pool', 'bytes'),
    ('free', 'The amount of free space available in the pool', 'bytes'),
    ('freeing', 'The amount of space waiting to be reclaimed from destroyed filesystems or snapshots', 'bytes'),
    ('dedupratio', 'The deduplication ratio', ''),
    ('fragmentation', 'The amount of fragmentation in the pool', '')
)


def zpool_info(registry: CollectorRegistry):
    cmd = ('zpool', 'list', '-Hp', '-o', 'name,' + ','.join([column_name for (column_name, *_) in ZPOOL_INFO_METRICS]))
    metrics = {}
    for columns in run_tabular(cmd):
        for (idx, (column_name, doc, unit)) in enumerate(ZPOOL_INFO_METRICS, 1):
            if column_name not in metrics:
                metrics[column_name] = Gauge(f'zpool_{column_name}', documentation=doc, unit=unit, namespace='zfs',
                                             registry=registry,
                                             labelnames=['pool_name'])
            metrics[column_name].labels((columns[0])).set(float(columns[idx]))


DATASET_METADATA_LABELS = ['type', 'creation', 'mounted', 'mounted', 'checksum', 'compression', 'readonly',
                           'version', 'dedup', 'volblocksize']

DATASET_TYPES = ('filesystem', 'volume')


def dataset_metadata(registry: CollectorRegistry):
    cmd = ('zfs', 'list', '-Hp', '-t', ','.join(DATASET_TYPES), '-o', 'name,' + ','.join(DATASET_METADATA_LABELS))
    metric = Gauge('dataset', documentation='Constant metric with metadata about the zfs dataset', namespace='zfs',
                   registry=registry, labelnames=['dataset_name', *DATASET_METADATA_LABELS])
    for columns in run_tabular(cmd):
        metric.labels(*columns).set(1)


DATASET_INFO_METRICS = (
    ('used', 'The amount of space consumed by this dataset and all its descendents', 'bytes'),
    ('available', 'The amount of space available to the dataset and all its children', 'bytes'),
    ('referenced',
     'The amount of data that is accessible by this dataset, which may or may not be shared with other datasets in the pool',
     'bytes'),
    ('compressratio',
     'For non-snapshots, the compression ratio achieved for the used space of this dataset, expressed as a multiplier',
     ''),
    ('reservation', 'The minimum amount of space guaranteed to a dataset and its descendants', 'bytes'),
    ('refreservation', 'The minimum amount of space guaranteed to a dataset, not including its descendents', 'bytes'),
    ('volsize', 'For volumes, specifies the logical size of the volume', 'bytes')
)


def dataset_metrics(registry: CollectorRegistry):
    cmd = ('zfs', 'list', '-Hp', '-t', ','.join(DATASET_TYPES), '-o',
           'name,' + ','.join([col for (col, *_) in DATASET_INFO_METRICS]))
    metrics = {}
    for columns in run_tabular(cmd):
        for (idx, (col, doc, unit)) in enumerate(DATASET_INFO_METRICS, 1):
            if col not in metrics:
                metrics[col] = Gauge(f'dataset_{col}', documentation=doc, unit=unit, registry=registry,
                                     labelnames=['dataset_name'],
                                     namespace='zfs')

            if columns[idx] == '-':
                continue

            metrics[col].labels((columns[0])).set(float(columns[idx].rstrip('x')))


@dataclass
class ZpoolConfig:
    name: str
    path: list[str]
    state: str
    read: int | None = None
    write: int | None = None
    checksum: int | None = None
    comment: str | None = None
    is_spare: bool = False
    indent: int = 0
    leading_whitespace: str = ''


@dataclass
class ZpoolScan:
    at: datetime
    duration: timedelta
    corrected: int


@dataclass
class ZpoolStatus:
    name: str
    state: str
    configs: list[ZpoolConfig]
    scrub: ZpoolScan | None = None
    resilvering: ZpoolScan | None = None

def zpool_status(registry: CollectorRegistry):
    cmd = ('zpool', 'status', '-p')
    metrics = {}

    for status in zpool_status_parse('\n'.join(list(run(cmd)))):
        if 'status' not in metrics:
            metrics['status'] = Gauge('zpool_status', 'The status of the zpool', labelnames=['zpool_name', 'state'],
                                      namespace='zfs', registry=registry)
        metrics['status'].labels(status.name, status.state).set(1)

        if status.scrub:
            scan_metrics('scrub', metrics, registry, status.scrub)

        if status.resilvering:
            scan_metrics('resilvering', metrics, registry, status.resilvering)

        for config in status.configs:
            if 'vdev_info' not in metrics:
                metrics['vdev_info'] = Gauge('zpool_vdev_info', 'Information about the vdevs in a zpool',
                                             labelnames=['zpool_name', 'vdev_name', 'path', 'state', 'read', 'write',
                                                         'checksum'],
                                             namespace='zfs', registry=registry)
            metrics['vdev_info'].labels(status.name, config.name, f'{config.path[0]}://{"/".join(config.path[1:])}',
                                        config.state,
                                        none_to_empty_string(config.read), none_to_empty_string(config.write),
                                        none_to_empty_string(config.checksum)).set(1)


def scan_metrics(activity: str, metrics: dict[str, Gauge], registry: CollectorRegistry, status: ZpoolStatus, scan: ZpoolScan):
    if f'{activity}_duration' not in metrics:
        metrics[f'{activity}_duration'] = Gauge(f'zpool_{activity}_duration',
                                                f'The duration of the latest zpool {activity} in seconds',
                                                labelnames=['zpool_name'], namespace='zfs', unit='seconds',
                                                registry=registry)
    metrics[f'{activity}_duration'].labels(status.name).set(scan.duration.total_seconds())
    if f'{activity}_corrected' not in metrics:
        metrics[f'{activity}_corrected'] = Gauge(f'zpool_{activity}_corrected',
                                                 f'The number of corrected bytes of the latest zpool {activity}',
                                                 labelnames=['zpool_name'], namespace='zfs',
                                                 unit='bytes',
                                                 registry=registry)
    metrics[f'{activity}_corrected'].labels(status.name).set(scan.corrected)
    if f'{activity}_time' not in metrics:
        metrics[f'{activity}_time'] = Gauge(f'zpool_{activity}_time',
                                            f'The timestamp of the latest zpool {activity}',
                                            labelnames=['zpool_name'], namespace='zfs', unit='seconds',
                                            registry=registry)
    metrics[f'{activity}_time'].labels(status.name).set(scan.at.timestamp())


def none_to_empty_string(value):
    return '' if value is None else value


def zpool_status_parse(content: str) -> list[ZpoolStatus]:
    statuses: list[ZpoolStatus] = []

    for status in re.findall(r'^\s*pool:\s+(?:.+(?=^\s*pool:\s+)|.+\Z)', content, re.MULTILINE | re.DOTALL):
        matched_pairs: list[tuple[str, str]] = re.findall(r'^\s*(\w+):\s*(.+?(?=^\s*\w+:)|.*\Z)', status,
                                                          re.MULTILINE | re.DOTALL)
        matches = dict([(key, value.strip()) for key, value in matched_pairs])

        configs = re.findall(
            r'^([\t ]*)(\S+)(?:[\t ]+(\S+)(?:[\t ]+(\S+)[\t ]+(\S+)[\t ]+(\S+)(?:[\t ]+([^\n]+))?)?)?$',
            matches.get('config', ''), re.MULTILINE | re.DOTALL)

        if len(configs) == 0:
            continue

        configs = [ZpoolConfig(
            name=config[1].strip(),
            path=[],
            state=config[2].strip(),
            read=int(config[3]) if config[3] != '' else None,
            write=int(config[4]) if config[4] != '' else None,
            checksum=int(config[5]) if config[5] != '' else None,
            comment=config[6] if config[6] != '' else None,
            leading_whitespace=config[0],
        ) for config in configs[1:]]

        configs = reduce(
            lambda acc, config: acc + [
                replace(config, is_spare=config.name == 'spares' or (acc[-1].is_spare if len(acc) > 0 else False))],
            configs, [])

        # Size the indentation of each line and strip, remove headlines
        configs = [replace(config, indent=int(len(config.leading_whitespace) / 2)) for config in configs]

        # Normalize names
        configs = [replace(config, name=config.comment[4:].split('/')[-1] if str(config.comment).startswith(
            'was ') else config.name) for config in configs]

        offset = configs[0].indent

        # Accumulate path hierarchy based on indent size
        configs = reduce(
            lambda acc, config: acc + [replace(
                config,
                path=[*(acc[-1].path[0:config.indent - offset] if len(acc) > 0 else []), config.name])], configs,
            [])

        configs = [replace(config, indent=0, leading_whitespace='') for config in configs if config.name != 'spares']

        scrub = None
        resilvering = None
        scan = re.match(
            r'(?P<activity>scrub repaired|resilvered) (?P<corrected>\S+) in (?P<duration>\S+) with (\d+) errors on (?P<at>.+)$',
            matches.get('scan', ''))
        if scan:
            scan_info = ZpoolScan(
                at=datetime.strptime(scan.group('at'), '%a %b %d %H:%M:%S %Y'),
                duration=parse_time_duration(scan.group('duration')),
                corrected=parse_si_unit(scan.group('corrected'))
            )
            if scan.group('activity') == 'scrub repaired':
                scrub = scan_info
            elif scan.group('activity') == 'resilvered':
                resilvering = scan_info

        statuses.append(ZpoolStatus(
            name=matches.get('pool', ''),
            state=matches.get('state', ''),
            configs=list(configs),
            scrub=scrub,
            resilvering=resilvering
        ))

    return statuses


SI_UNITS = {
    'B': 0,
    'K': 1,
    'M': 2,
    'G': 3,
    'T': 4,
    'P': 5,
    'E': 6,
    'Z': 7,
    'Y': 8
}


def parse_si_unit(value: str):
    if value.isdecimal():
        return round(float(value))
    return round(float(value[:-1]) * (1024 ** SI_UNITS[value[-1].upper()]))


TIME_UNITS = {
    's': 'seconds',
    'm': 'minutes',
    'h': 'hours',
    'd': 'days',
    'w': 'weeks',
    'y': 'years'
}


def parse_time_duration(value: str):
    delta = timedelta(seconds=0)
    if ':' in value:
        for p, n in enumerate(value.split(':')[::-1]):
            unit = list(TIME_UNITS.values())[p]
            delta += timedelta(**{unit: int(n)})
        return delta

    num = 0
    for c in value:
        if c.isdecimal():
            num = num * 10 + int(c)
        else:
            delta += timedelta(**{TIME_UNITS[c]: num})
            num = 0
    return delta


def main():
    registry = CollectorRegistry()

    funcs = (zpool_metadata, zpool_info, dataset_metadata, dataset_metrics, zpool_status)
    with ThreadPoolExecutor(max_workers=len(funcs)) as executor:
        for func in funcs:
            executor.submit(func, registry)

    print(generate_latest(registry).decode(), end='')


main()
