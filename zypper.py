#!/usr/bin/env python3

"""
Description: Expose metrics from zypper updates and patches.

The script can take 2 arguments: `--more` and `--less`.
The selection of the arguments change how many informations are going to be printed.

The `--more` is by default.

Examples:

    zypper.py --less
    zypper.py -m

Authors: Gabriele Puliti <gabriele.puliti@suse.com>
         Bernd Shubert <bschubert@suse.com>
"""

import argparse
import subprocess
import os
import sys

from collections.abc import Sequence
from prometheus_client import CollectorRegistry, Gauge, Info, generate_latest

REGISTRY = CollectorRegistry()
NAMESPACE = "zypper"


def __print_pending_data(data, fields, info, filters=None):
    filters = filters or {}

    if len(data) == 0:
        field_str = ",".join([f'{name}=""' for _, name in fields])
        info.info({field_str: '0'})
    else:
        for package in data:
            check = all(package.get(k) == v for k, v in filters.items())
            if check:
                field_str = ",".join([f'{name}="{package[field]}"' for field, name in fields])
                info.info({field_str: '1'})


def print_pending_updates(data, all_info, filters=None):
    if all_info:
        fields = [("Repository", "repository"), ("Name", "package-name"),
                   ("Available Version", "available-version")]
    else:
        fields = [("Repository", "repository"), ("Name", "package-name")]
    prefix = "zypper_update_pending"
    description = "zypper package update available from repository. (0 = not available, 1 = available)"
    info = Info(prefix, description)

    __print_pending_data(data, fields, info, filters)


def print_pending_patches(data, all_info, filters=None):
    if all_info:
        fields = [
            ("Repository", "repository"), ("Name", "patch-name"), ("Category", "category"),
            ("Severity", "severity"), ("Interactive", "interactive"), ("Status", "status")
        ]
    else:
        fields = [
            ("Repository", "repository"), ("Name", "patch-name"),
            ("Interactive", "interactive"), ("Status", "status")
        ]
    prefix = "zypper_patch_pending"
    description = "zypper patch available from repository. (0 = not available , 1 = available)"
    info = Info(prefix, description)

    __print_pending_data(data, fields, info, filters)


def print_orphaned_packages(data, filters=None):
    fields = [
        ("Name", "package"), ("Version", "installed-version")
    ]
    prefix = "zypper_package_orphan"
    description = "zypper packages with no update source (orphaned)"
    info = Info(prefix, description)

    __print_pending_data(data, fields, info, filters)


def print_data_sum(data, prefix, description, filters=None):
    gauge = Gauge(prefix,
                description,
                namespace=NAMESPACE,
                registry=REGISTRY)
    filters = filters or {}
    if len(data) == 0:
        gauge.set(0)
    else:
        for package in data:
            check = all(package.get(k) == v for k, v in filters.items())
            if check:
                gauge.inc()


def print_reboot_required():
    needs_restarting_path = '/usr/bin/needs-restarting'
    is_path_ok = os.path.isfile(needs_restarting_path) and os.access(needs_restarting_path, os.X_OK)

    if is_path_ok:
        prefix = "node_reboot_required"
        description = "Node require reboot to activate installed updates or patches. (0 = not needed, 1 = needed)"
        info = Info(prefix, description)
        result = subprocess.run(
            [needs_restarting_path, '-r'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False)
        if result.returncode == 0:
            info.info({"node_reboot_required": "0"})
        else:
            info.info({"node_reboot_required": "1"})


def print_zypper_version():
    result = subprocess.run(
        ['/usr/bin/zypper', '-V'],
        stdout=subprocess.PIPE,
        check=False).stdout.decode('utf-8')
    info = Info("zypper_version", "zypper installed package version")

    info.info({"zypper_version": result.split()[1]})


def __extract_data(raw, fields):
    raw_lines = raw.splitlines()[2:]
    extracted_data = []

    for line in raw_lines:
        parts = [part.strip() for part in line.split('|')]
        if len(parts) >= max(fields.values()) + 1:
            extracted_data.append({
                field: parts[index] for field, index in fields.items()
            })

    return extracted_data


def stdout_zypper_command(command):
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(f"zypper returned exit code {result.returncode}: {result.stderr}")

    return result.stdout.decode('utf-8')


def extract_lu_data(raw: str):
    fields = {
        "Repository": 1,
        "Name": 2,
        "Current Version": 3,
        "Available Version": 4,
        "Arch": 5
    }

    return __extract_data(raw, fields)


def extract_lp_data(raw: str):
    fields = {
        "Repository": 0,
        "Name": 1,
        "Category": 2,
        "Severity": 3,
        "Interactive": 4,
        "Status": 5
    }

    return __extract_data(raw, fields)


def extract_orphaned_data(raw: str):
    fields = {
        "Name": 3,
        "Version": 4
    }

    return __extract_data(raw, fields)


def __parse_arguments(argv):
    parser = argparse.ArgumentParser()

    parser.add_mutually_exclusive_group(required=False)
    parser.add_argument(
        "-m",
        "--more",
        dest="all_info",
        action='store_true',
        help="Print all the package infos",
    )
    parser.add_argument(
        "-l",
        "--less",
        dest="all_info",
        action='store_false',
        help="Print less package infos",
    )
    parser.set_defaults(all_info=True)

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = __parse_arguments(argv)
    data_zypper_lu = extract_lu_data(
        stdout_zypper_command(['/usr/bin/zypper', '--quiet', 'lu'])
    )
    data_zypper_lp = extract_lp_data(
        stdout_zypper_command(['/usr/bin/zypper', '--quiet', 'lp'])
    )
    data_zypper_orphaned = extract_orphaned_data(
        stdout_zypper_command(['/usr/bin/zypper', '--quiet', 'pa', '--orphaned'])
    )

    print_pending_updates(data_zypper_lu,
                          args.all_info)
    print_data_sum(data_zypper_lu,
                   "zypper_updates_pending_total",
                   "zypper packages updates available in total")
    print_pending_patches(data_zypper_lp,
                          args.all_info)
    print_data_sum(data_zypper_lp,
                   "zypper_patches_pending_total",
                   "zypper patches available total")
    print_data_sum(data_zypper_lp,
                   "zypper_patches_pending_security_total",
                   "zypper patches available with category security total",
                   filters={'Category': 'security'})
    print_data_sum(data_zypper_lp,
                   "zypper_patches_pending_security_important_total",
                   "zypper patches available with category security severity important total",
                   filters={'Category': 'security', 'Severity': 'important'})
    print_data_sum(data_zypper_lp,
                   "zypper_patches_pending_reboot_total",
                   "zypper patches available which require reboot total",
                   filters={'Interactive': 'reboot'})
    print_reboot_required()
    print_zypper_version()
    print_orphaned_packages(data_zypper_orphaned)

    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        sys.exit(1)

    print(generate_latest(REGISTRY).decode(), end="")
