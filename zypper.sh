#!/usr/bin/env bash
#
# Description: Expose metrics from zypper updates and patches.
# Author: Bernd Schubert <bschubert@suse.com>
# Contributer: Gabriele Puliti <gabriele.puliti@suse.com>
# Based on yum.sh by Slawomir Gonet <slawek@otwiera.cz>

#set -o errexit # exit on first error, doesn't work on all test systems
set -o nounset # fail if unset variables
set -o pipefail # reflect exit status

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
  echo """Usage: zypper.sh [OPTION]
This is an script to extract monitoring values for the zypper package

It work only with root permission!

Available options:
    -l, --less    Extract only the necessary
    -m, --more    Extract everything (this is the default value)

Examples:
 zypper.sh --less
 zypper.sh -m
"""
  exit
fi

# Check if we are root
if [ "$EUID" -ne 0 ]; then
  echo "${0##*/}: Please run as root!" >&2
  exit 1
fi

filter_pending_updates='
BEGIN {
    FS=" \\| ";  # set field separator to " | "
}

NR {
    # Extract and format repository, package-name, and available version
    repository = $2
    package_name = $3
    available_version = $5

    # Remove trailing whitespace
    gsub(/[[:space:]]+$/, "", repository)
    gsub(/[[:space:]]+$/, "", package_name)
    gsub(/[[:space:]]+$/, "", available_version)

    # Print the output in the required format
    if (output_format == "-l" || output_format == "--less")
      printf "zypper_update_pending{repository=\"%s\",package-name=\"%s\"} 1\n", repository, package_name
    else if (output_format == "-m" || output_format == "--more")
      printf "zypper_update_pending{repository=\"%s\",package-name=\"%s\",available-version=\"%s\"} 1\n", repository, package_name, available_version 
}
'

filter_pending_patches='
BEGIN {
    FS=" \\| ";  # set field separator to " | "
}

NR {
    # Extract and format repository, patch_name, category, severity, interactive and status
    repository = $1
    patch_name = $2
    category = $3
    severity = $4
    interactive = $5
    status = $6

    # Remove trailing whitespace
    gsub(/[[:space:]]+$/, "", repository)
    gsub(/[[:space:]]+$/, "", patch_name)
    gsub(/[[:space:]]+$/, "", category)
    gsub(/[[:space:]]+$/, "", severity)
    gsub(/[[:space:]]+$/, "", interactive)
    gsub(/[[:space:]]+$/, "", status)

    # Print the output in the required format
    if (output_format == "-l" || output_format == "--less")
      printf "zypper_patch_pending{repository=\"%s\",patch-name=\"%s\",interactive=\"%s\",status=\"%s\"} 1\n", repository, patch_name, interactive, status
    else if (output_format == "-m" || output_format == "--more")
      printf "zypper_patch_pending{repository=\"%s\",patch-name=\"%s\",category=\"%s\",severity=\"%s\",interactive=\"%s\",status=\"%s\"} 1\n", repository, patch_name, category, severity, interactive, status
}
'

filter_orphan_packages='
BEGIN {
    FS=" \\| ";  # set field separator to " | "
}

NR {
    # Extract and format package, and installed version
    package = $3
    installed_version = $5

    # Remove trailing whitespace
    gsub(/[[:space:]]+$/, "", package)
    gsub(/[[:space:]]+$/, "", installed_version)

    # Print the output in the required format
    printf "zypper_package_orphan{package=\"%s\",installed-version=\"%s\"} 1\n", package, installed_version
}
'

get_pending_updates() {
  if [ -z "$1" ]; then 
    echo 'zypper_update_pending{repository="",package-name="",available-version=""} 0'
  else
    echo "$1" |
      awk -v output_format=$2 "$filter_pending_updates" 
  fi
}

get_updates_sum() {
  { 
    if [ -z "$1" ]; then 
      echo "0"
    else
      echo "$1" | 
        wc -l
    fi
  } |
  awk '{print "zypper_updates_pending_total{total} "$1}' 
}

get_pending_patches() {
  if [ -z "$1" ]; then 
    echo 'zypper_patch_pending{repository="",patch-name="",category="",severity="",interactive="",status=""} 0'
  else
    echo "$1" |
      awk -v output_format=$2 "$filter_pending_patches"
  fi
}

get_pending_security_patches() {
  { 
    if [ -z "$1" ]; then 
      echo "0"
    else
      echo "$1" | 
        grep "| security" |
        wc -l
    fi
  } |
  awk '{print "zypper_patches_pending_security_total "$1}'
}

get_pending_security_important_patches() {
  { 
    if [ -z "$1" ]; then 
      echo "0"
    else
      echo "$1" | 
        grep "| security" |
        grep important |
        wc -l
    fi
  } |
  awk '{print "zypper_patches_pending_security_important_total "$1}'
}

get_pending_reboot_patches() {
  { 
    if [ -z "$1" ]; then 
      echo "0"
    else
      echo "$1" | 
        grep reboot | 
        wc -l 
    fi
  } |
  awk '{print "zypper_patches_pending_reboot_total "$1}'
}

get_patches_sum() {
  { 
    if [ -z "$1" ]; then 
      echo "0"
    else
      echo "$1" |
        wc -l 
    fi
  } |
  awk '{print "zypper_patches_pending_total "$1}'
}

get_zypper_version() {
  echo "$1" |
  awk '{print "zypper_version "$2}'
}

get_orphan_packages() {
  if [ -z "$1" ]; then 
    echo 'zypper_package_orphan{package="",installed-version=""} 0'
  else
    echo "$1" |
      awk "$filter_orphan_packages"
  fi
}

main() {
  # If there are no paramenter passed then use the more format
  if [ $# -eq 0 ]; then
    output_format="--more"
  else
    output_format="$1"
  fi

  zypper_lu_quiet_tail_n3="$(/usr/bin/zypper --quiet lu | tail -n +3)"
  zypper_lp_quiet_tail_n3="$(/usr/bin/zypper --quiet lp | sed -E '/(^$|^Repository|^---)/d'| sed '/|/!d')"
  zypper_version="$(/usr/bin/zypper -V)"
  zypper_orphan_packages="$(zypper --quiet pa --orphaned | tail -n +3)"

  echo '# HELP zypper_update_pending zypper package update available from repository. (0 = not available, 1 = available)'
  echo '# TYPE zypper_update_pending gauge'
  get_pending_updates "$zypper_lu_quiet_tail_n3" "$output_format"

  echo '# HELP zypper_updates_pending_total zypper packages updates available in total'
  echo '# TYPE zypper_updates_pending_total counter'
  get_updates_sum "$zypper_lu_quiet_tail_n3"

  echo '# HELP zypper_patch_pending zypper patch available from repository. (0 = not available, 1 = available)'
  echo '# TYPE zypper_patch_pending gauge'
  get_pending_patches "$zypper_lp_quiet_tail_n3" "$output_format"

  echo '# HELP zypper_patches_pending_total zypper patches available total'
  echo '# TYPE zypper_patches_pending_total counter'
  get_patches_sum "$zypper_lp_quiet_tail_n3"

  echo '# HELP zypper_patches_pending_security_total zypper patches available with category security total'
  echo '# TYPE zypper_patches_pending_security_total counter'
  get_pending_security_patches "$zypper_lp_quiet_tail_n3"

  echo '# HELP zypper_patches_pending_security_important_total zypper patches available with category security severity important total'
  echo '# TYPE zypper_patches_pending_security_important_total counter'
  get_pending_security_important_patches "$zypper_lp_quiet_tail_n3"

  echo '# HELP zypper_patches_pending_reboot_total zypper patches available which require reboot total'
  echo '# TYPE zypper_patches_pending_reboot_total counter'
  get_pending_reboot_patches "$zypper_lp_quiet_tail_n3"

  if [[ -x /usr/bin/needs-restarting ]]; then
    echo '# HELP node_reboot_required Node require reboot to active installed updates or patches. (0 = not needed, 1 = needed)'
    echo '# TYPE node_reboot_required gauge'
    if /usr/bin/needs-restarting -r >/dev/null 2>&1; then
      echo 'node_reboot_required 0'
    else
      echo 'node_reboot_required 1'
    fi
  fi

  echo '# HELP zypper_version zypper installed package version'
  echo '# TYPE zypper_version gauge'
  get_zypper_version "$zypper_version"

  echo '# HELP zypper_package_orphan zypper packages with no update source (orphaned) '
  echo '# TYPE zypper_package_orphan gauge'
  get_orphan_packages "$zypper_orphan_packages"
}

main "$@"
