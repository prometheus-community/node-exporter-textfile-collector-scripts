#!/usr/bin/env python3

"""
Description: #TODO: short version

#TODO: long version

#TODO: example

    #TODO: code of the example

#TODO: additional information

Dependencies: #TODO: add if needed

Authors: Gabriele Puliti <gabriele.puliti@suse.com>
         Bernd Shubert <bschubert@suse.com>
"""

import argparse
import subprocess
import sys

from collections.abc import Sequence

def print_pending_updates(data, all_info):
    def print_more(package):
        repository = "repository=\"" + package['Repository'] + "\""
        package_name = "package-name=\"" + package['Name'] + "\""
        available_version = "available-version=\"" + package['Available Version'] + "\""
        print("zypper_update_pending{" + repository + ","
            + package_name + "," + available_version + "} 1")
    def print_less(package):
        repository = "repository=\"" + package['Repository'] + "\""
        package_name = "package-name=\"" + package['Name'] + "\""
        print("zypper_update_pending{" + repository + "," + package_name + "} 1")

    if all_info:
        print_info = print_more
    else:
        print_info = print_less

    if len(data) == 0:
        print('zypper_update_pending{repository="",package-name="",available-version=""} 0')
    else:
        for line in data:
            print_info(line)

def print_updates_sum(data):
    if len(data) == 0:
        print('zypper_update_pending_total{total} 0')
    else:
        print("zypper_update_pending_total{total} " + str(len(data)))

def print_pending_patches(data, all_info):
    def print_more(package):
        repository = "repository=\"" + package['Repository'] + "\""
        package_name = "pach-name=\"" + package['Name'] + "\""
        category = "category=\"" + package['Category'] + "\""
        severity = "severity=\"" + package['Severity'] + "\""
        interactive = "interactive=\"" + package['Interactive'] + "\""
        status = "status=\"" + package['Status'] + "\""
        print("zypper_patch_pending{" + repository + ","
            + package_name + "," + category + ","
            + severity + "," + interactive + ","
            + status + "} 1")
    def print_less(package):
        repository = "repository=\"" + package['Repository'] + "\""
        package_name = "pach-name=\"" + package['Name'] + "\""
        interactive = "interactive=\"" + package['Interactive'] + "\""
        status = "status=\"" + package['Status'] + "\""
        print("zypper_patch_pending{" + repository + ","
            + package_name + "," + interactive + ","
            + status + "} 1")

    if all_info:
        print_info = print_more
    else:
        print_info = print_less

    if len(data) == 0:
        print('zypper_patch_pending{repository="",patch-name="",category="",severity="",interactive="",status""} 0')
    else:
        for line in data:
            print_info(line)

def get_patches_sum(zypper_output):
    return None

def get_pending_security_patches(zypper_output):
    return None

def get_pending_security_important_patches(zypper_output):
    return None

def get_pending_reboot_patches(zypper_output):
    return None

def get_zypper_version(zypper_output):
    return None

def get_orphan_packages(zypper_output):
    return None

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
        ['cat', 'testlu.txt'],
        #['/usr/bin/zypper', '--quiet', 'lu'],
        stdout=subprocess.PIPE,
        check=False
    ).stdout.decode('utf-8')
    data_zypper_lu = __extract_lu_data(raw_zypper_lu)

    raw_zypper_lp = subprocess.run(
        ['cat', 'testlp.txt'],
        #['/usr/bin/zypper', '--quiet', 'lp'],
        stdout=subprocess.PIPE,
        check=False
    ).stdout.decode('utf-8')
    data_zypper_lp = __extract_lp_data(raw_zypper_lp)

    print('# HELP zypper_update_pending zypper package update available from repository. (0 = not available, 1 = available)')
    print('# TYPE zypper_update_pending gauge')
    print_pending_updates(data_zypper_lu, args.all_info)

    print('# HELP zypper_updates_pending_total zypper packages updates available in total')
    print('# TYPE zypper_updates_pending_total counter')
    print_updates_sum(data_zypper_lu)

    print('# HELP zypper_patch_pending zypper patch available from repository. (0 = not available, 1 = available)')
    print('# TYPE zypper_patch_pending gauge')
    print_pending_patches(data_zypper_lp, args.all_info)

    sys.exit()

    # zypper_lp_quiet_tail_n3="$(/usr/bin/zypper --quiet lp | sed -E '/(^$|^Repository|^---)/d'| sed '/|/!d')"
    # zypper_version="$(/usr/bin/zypper -V)"
    # zypper_orphan_packages="$(zypper --quiet pa --orphaned | tail -n +3)"

    print('# HELP zypper_patches_pending_total zypper patches available total')
    print('# TYPE zypper_patches_pending_total counter')
    get_patches_sum(zypper_lp_quiet_tail_n3)

    print('# HELP zypper_patches_pending_security_total zypper patches available with category security total')
    print('# TYPE zypper_patches_pending_security_total counter')
    get_pending_security_patches(zypper_lp_quiet_tail_n3)

    print('# HELP zypper_patches_pending_security_important_total zypper patches available with category security severity important total')
    print('# TYPE zypper_patches_pending_security_important_total counter')
    get_pending_security_important_patches(zypper_lp_quiet_tail_n3)

    print('# HELP zypper_patches_pending_reboot_total zypper patches available which require reboot total')
    print('# TYPE zypper_patches_pending_reboot_total counter')
    get_pending_reboot_patches(zypper_lp_quiet_tail_n3)

    # TODO:
        #if [[ -x /usr/bin/needs-restarting ]]
        #    print('# HELP node_reboot_required Node require reboot to active installed updates or patches. (0 = not needed, 1 = needed)')
        #    print('# TYPE node_reboot_required gauge')
        #    if /usr/bin/needs-restarting -r >/dev/null 2>&1; then
        #        print('node_reboot_required 0')
        #    else
        #        print('node_reboot_required 1')

    print('# HELP zypper_version zypper installed package version')
    print('# TYPE zypper_version gauges')
    get_zypper_version("$zypper_version")

    print('# HELP zypper_package_orphan zypper packages with no update source (orphaned)')
    print('# TYPE zypper_package_orphan gauges')
    get_orphan_packages("$zypper_orphan_packages")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
