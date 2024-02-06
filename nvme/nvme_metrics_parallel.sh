#!/usr/bin/env bash

# Script to capture NVME drives smart metrics using GNU parallel
#
# Dependencies:
# - nvme-cli 1.16
# - jq 1.6-6
# - parallel 20190922-1
#
# Based on code from
# - https://github.com/prometheus-community/node-exporter-textfile-collector-scripts/blob/master/nvme/nvme_metrics.sh
#
# Example Grafana dashboard:
# - https://github.com/prometheus-community/node-exporter-textfile-collector-scripts/blob/master/nvme/nvme_metrics_dashboard.json
#
# Author: Davide Obbi <davide.obbi@e4company.com>

set -eu

# Ensure predictable numeric / date formats, etc.
export LC_ALL=C

# Check if we are root
if [[ "${EUID}" -ne 0 ]]; then
  echo "${0##*/}: Please run as root!" >&2
  exit 1
fi

# Check if programs are installed
if ! command -v nvme >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1 || ! command -v parallel >/dev/null 2>&1 ; then
  echo "${0##*/}: nvme-cli nor jq nor parallel are not installed. Aborting." >&2
  exit 1
fi

output_format_awk="$(
  cat <<'OUTPUTAWK'
BEGIN { v = "" }
v != $1 {
  print "# HELP nvme_" $1 " SMART metric " $1;
  if ($1 ~ /_total$/)
    print "# TYPE nvme_" $1 " counter";
  else
    print "# TYPE nvme_" $1 " gauge";
  v = $1
}
{print "nvme_" $0}
OUTPUTAWK
)"

format_output() {
  sort | awk -F'{' "${output_format_awk}"
}

# Get the nvme-cli version
nvme_version="$(nvme version | awk '$1 == "nvme" {print $3}')"
echo "nvmecli{version=\"${nvme_version}\"} 1" | format_output

get_data() {
  json_check="$(nvme smart-log -o json "${1}")"
  disk="${1##*/}"

  # The temperature value in JSON is in Kelvin, we want Celsius
  value_temperature="$(echo "${json_check}" | jq '.temperature - 273')"
  echo "temperature_celsius{device=\"${disk}\"} ${value_temperature}"

  value_available_spare="$(echo "${json_check}" | jq '.avail_spare / 100')"
  echo "available_spare_ratio{device=\"${disk}\"} ${value_available_spare}"

  value_available_spare_threshold="$(echo "${json_check}" | jq '.spare_thresh / 100')"
  echo "available_spare_threshold_ratio{device=\"${disk}\"} ${value_available_spare_threshold}"

  value_percentage_used="$(echo "${json_check}" | jq '.percent_used / 100')"
  echo "percentage_used_ratio{device=\"${disk}\"} ${value_percentage_used}"

  value_critical_warning="$(echo "${json_check}" | jq '.critical_warning')"
  echo "critical_warning_total{device=\"${disk}\"} ${value_critical_warning}"

  value_media_errors="$(echo "${json_check}" | jq -r '.media_errors')"
  echo "media_errors_total{device=\"${disk}\"} ${value_media_errors}"

  value_num_err_log_entries="$(echo "${json_check}" | jq -r '.num_err_log_entries')"
  echo "num_err_log_entries_total{device=\"${disk}\"} ${value_num_err_log_entries}"

  value_power_cycles="$(echo "${json_check}" | jq -r '.power_cycles')"
  echo "power_cycles_total{device=\"${disk}\"} ${value_power_cycles}"

  value_power_on_hours="$(echo "${json_check}" | jq -r '.power_on_hours')"
  echo "power_on_hours_total{device=\"${disk}\"} ${value_power_on_hours}"

  value_controller_busy_time="$(echo "${json_check}" | jq -r '.controller_busy_time')"
  echo "controller_busy_time_seconds{device=\"${disk}\"} ${value_controller_busy_time}"

  value_data_units_written="$(echo "${json_check}" | jq -r '.data_units_written')"
  echo "data_units_written_total{device=\"${disk}\"} ${value_data_units_written}"

  value_data_units_read="$(echo "${json_check}" | jq -r '.data_units_read')"
  echo "data_units_read_total{device=\"${disk}\"} ${value_data_units_read}"

  value_host_read_commands="$(echo "${json_check}" | jq -r '.host_read_commands')"
  echo "host_read_commands_total{device=\"${disk}\"} ${value_host_read_commands}"

  value_host_write_commands="$(echo "${json_check}" | jq -r '.host_write_commands')"
  echo "host_write_commands_total{device=\"${disk}\"} ${value_host_write_commands}"

  value_unsafe_shutdowns="$(echo "${json_check}" | jq -r '.unsafe_shutdowns')"
  echo "unsafe_shutdowns_total{device=\"${disk}\"} ${value_unsafe_shutdowns}"

  value_endurance_grp_critical_warning_summary="$(echo "${json_check}" | jq -r '.endurance_grp_critical_warning_summary')"
  echo "endurance_grp_critical_warning_summary{device=\"${disk}\"} ${value_endurance_grp_critical_warning_summary}"

}

export -f get_data
export HOME="/tmp"

nvme list -o json | jq -r '.Devices | .[].DevicePath' | parallel get_data | format_output
