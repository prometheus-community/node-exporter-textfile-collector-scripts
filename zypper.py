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

from collections.abc import Sequence


def __print_package_info(package, fields, prefix, filters=None):
    filters = filters or {}
    check = all(package.get(k) == v for k, v in filters.items())

    if check:
        field_str = ",".join([f'{name}="{package[field]}"' for field, name in fields])
        print(f"{prefix}{{{field_str}}} 1")


def __print_pending_data(data, all_info, fields_more, fields_less, prefix, filters=None):
    if all_info:
        fields = fields_more
    else:
        fields = fields_less

    if len(data) == 0:
        field_str = ",".join([f'{name}=""' for _, name in fields])
        print(f"{prefix}{{{field_str}}} 0")
    else:
        for package in data:
            __print_package_info(package, fields, prefix, filters)


def print_pending_updates(data, all_info, filters=None):
    fields_more = [("Repository", "repository"), ("Name", "package-name"),
                   ("Available Version", "available-version")]
    fields_less = [("Repository", "repository"), ("Name", "package-name")]
    prefix = "zypper_update_pending"

    __print_pending_data(data, all_info, fields_more, fields_less, prefix, filters)


def print_pending_patches(data, all_info, filters=None):
    fields_more = [
        ("Repository", "repository"), ("Name", "patch-name"), ("Category", "category"),
        ("Severity", "severity"), ("Interactive", "interactive"), ("Status", "status")
    ]
    fields_less = [
        ("Repository", "repository"), ("Name", "patch-name"),
        ("Interactive", "interactive"), ("Status", "status")
    ]
    prefix = "zypper_patch_pending"

    __print_pending_data(data, all_info, fields_more, fields_less, prefix, filters)


def print_orphaned_packages(data):
    fields = [
        ("Name", "package"), ("Version", "installed-version")
    ]
    prefix = "zypper_package_orphan"

    __print_pending_data(data, True, fields, None, prefix, None)


def __print_data_sum(data, prefix, filters=None):
    filters = filters or {}
    if len(data) == 0:
        print(prefix + "{total} 0")
    else:
        gauge = 0
        for package in data:
            check = all(package.get(k) == v for k, v in filters.items())
            if check:
                gauge += 1
        print(prefix + "{total} " + str(gauge))


def print_updates_sum(data, filters=None):
    prefix = "zypper_updates_pending_total"

    __print_data_sum(data, prefix, filters)


def print_patches_sum(data, prefix="zypper_patches_pending_total", filters=None):
    __print_data_sum(data, prefix, filters)


def print_reboot_required():
    needs_restarting_path = '/usr/bin/needs-restarting'
    is_path_ok = os.path.isfile(needs_restarting_path) and os.access(needs_restarting_path, os.X_OK)

    if is_path_ok:
        result = subprocess.run(
            [needs_restarting_path, '-r'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False)

        print('# HELP node_reboot_required Node require reboot to activate installed updates or '\
            'patches. (0 = not needed, 1 = needed)')
        print('# TYPE node_reboot_required gauge')
        if result.returncode == 0:
            print('node_reboot_required 0')
        else:
            print('node_reboot_required 1')


def print_zypper_version():
    result = subprocess.run(
        ['/usr/bin/zypper', '-V'],
        stdout=subprocess.PIPE,
        check=False).stdout.decode('utf-8')

    print("zypper_version " + result.split()[1])


def __extract_lu_data(raw: str):
    raw_lines = raw.splitlines()[2:]
    extracted_data = []

    for line in raw_lines:
        parts = [part.strip() for part in line.split('|')]
        if len(parts) >= 5:
            extracted_data.append({
                "Repository": parts[1],
                "Name": parts[2],
                "Current Version": parts[3],
                "Available Version": parts[4],
                "Arch": parts[5]
            })

    return extracted_data


def __extract_lp_data(raw: str):
    raw_lines = raw.splitlines()[2:]
    extracted_data = []

    for line in raw_lines:
        parts = [part.strip() for part in line.split('|')]
        if len(parts) >= 5:
            extracted_data.append({
                "Repository": parts[0],
                "Name": parts[1],
                "Category": parts[2],
                "Severity": parts[3],
                "Interactive": parts[4],
                "Status": parts[5]
            })

    return extracted_data


def __extract_orphaned_data(raw: str):
    raw_lines = raw.splitlines()[2:]
    extracted_data = []

    for line in raw_lines:
        parts = [part.strip() for part in line.split('|')]
        if len(parts) >= 5:
            extracted_data.append({
                "Name": parts[3],
                "Version": parts[4]
            })

    return extracted_data


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

    raw_zypper_lu = subprocess.run(
        ['/usr/bin/zypper', '--quiet', 'lu'],
        stdout=subprocess.PIPE,
        check=False
    ).stdout.decode('utf-8')
    data_zypper_lu = __extract_lu_data(raw_zypper_lu)

    raw_zypper_lp = subprocess.run(
        ['/usr/bin/zypper', '--quiet', 'lp'],
        stdout=subprocess.PIPE,
        check=False
    ).stdout.decode('utf-8')
    data_zypper_lp = __extract_lp_data(raw_zypper_lp)

    raw_zypper_orphaned = subprocess.run(
        ['/usr/bin/zypper', '--quiet', 'pa', '--orphaned'],
        stdout=subprocess.PIPE,
        check=False
    ).stdout.decode('utf-8')
    data_zypper_orphaned = __extract_orphaned_data(raw_zypper_orphaned)

    print('# HELP zypper_update_pending zypper package update available from repository. (0 = not '\
          'available, 1 = available)')
    print('# TYPE zypper_update_pending gauge')
    print_pending_updates(data_zypper_lu, args.all_info)

    print('# HELP zypper_updates_pending_total zypper packages updates available in total')
    print('# TYPE zypper_updates_pending_total counter')
    print_updates_sum(data_zypper_lu)

    print('# HELP zypper_patch_pending zypper patch available from repository. (0 = not available '\
          ', 1 = available)')
    print('# TYPE zypper_patch_pending gauge')
    print_pending_patches(data_zypper_lp, args.all_info)

    print('# HELP zypper_patches_pending_total zypper patches available total')
    print('# TYPE zypper_patches_pending_total counter')
    print_patches_sum(data_zypper_lp)

    print('# HELP zypper_patches_pending_security_total zypper patches available with category '\
          'security total')
    print('# TYPE zypper_patches_pending_security_total counter')
    print_patches_sum(data_zypper_lp,
                      prefix="zypper_patches_pending_security_total",
                      filters={'Category': 'security'})

    print('# HELP zypper_patches_pending_security_important_total zypper patches available with '\
          'category security severity important total')
    print('# TYPE zypper_patches_pending_security_important_total counter')
    print_patches_sum(data_zypper_lp,
                      prefix="zypper_patches_pending_security_important_total",
                      filters={'Category': 'security', 'Severity': 'important'})

    print('# HELP zypper_patches_pending_reboot_total zypper patches available which require '\
          'reboot total')
    print('# TYPE zypper_patches_pending_reboot_total counter')
    print_patches_sum(data_zypper_lp,
                      prefix="zypper_patches_pending_reboot_total",
                      filters={'Interactive': 'reboot'})

    print_reboot_required()

    print('# HELP zypper_version zypper installed package version')
    print('# TYPE zypper_version gauges')
    print_zypper_version()

    print('# HELP zypper_package_orphan zypper packages with no update source (orphaned)')
    print('# TYPE zypper_package_orphan gauges')
    print_orphaned_packages(data_zypper_orphaned)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
