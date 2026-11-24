#!/usr/bin/env bash
#
# Expose UFS (Universal Flash Storage) health as Prometheus metrics.
#
# UFS devices have no SMART. Their wear and end-of-life state is reported in
# the UFS health descriptor, which the Linux ufshcd driver exposes in sysfs
# under the host controller device (e.g. /sys/devices/platform/soc@0/1d84000.ufshc):
#
#   health_descriptor/life_time_estimation_a  wear of type A memory (SLC)  -> type="a"
#   health_descriptor/life_time_estimation_b  wear of type B memory (MLC/TLC) -> type="b"
#   health_descriptor/eol_info                pre-EOL status of reserved blocks
#   critical_health                           critical health exception count
#
# Common on phones, ARM SBCs and some laptops.
#
# Usage: ufs_health.sh | sponge /var/lib/node_exporter/ufs_health.prom

set -eu

# Escape a value for use inside a Prometheus label.
escape() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  printf '%s' "$s"
}

# Read a sysfs attribute, empty if missing or unreadable.
read_attr() {
  cat "$1" 2>/dev/null || true
}

# Convert a hex (0x..) or decimal sysfs value to decimal, empty if not a number.
to_dec() {
  case $1 in
    0x* | 0X*) [[ ${1:2} =~ ^[0-9a-fA-F]+$ ]] && printf '%d' "$((16#${1:2}))" ;;
    *) [[ $1 =~ ^[0-9]+$ ]] && printf '%d' "$1" ;;
  esac
  return 0
}

# UFS host controllers are the parents of SCSI hosts that have a health descriptor.
hosts=()
for scsi_host in /sys/class/scsi_host/host*; do
  [ -e "$scsi_host/device" ] || continue
  hba=$(readlink -f "$scsi_host/device/..")
  [ -d "$hba/health_descriptor" ] && hosts+=("$hba")
done

[ "${#hosts[@]}" -gt 0 ] || exit 0

# metric <name> <help> <sysfs path relative to the controller>
metric() {
  local name=$1 help=$2 attr=$3 hba value
  echo "# HELP ufs_${name} ${help}"
  echo "# TYPE ufs_${name} gauge"
  for hba in "${hosts[@]}"; do
    value=$(to_dec "$(read_attr "$hba/$attr")")
    [ -n "$value" ] || continue
    echo "ufs_${name}{device=\"$(escape "${hba##*/}")\"} ${value}"
  done
}

echo "# HELP ufs_life_time_estimation Wear in 10% steps: 1 = 0-10% of rated life used, 10 = 90-100%, 11 = exceeded, 0 = not reported. type a = SLC, b = MLC/TLC."
echo "# TYPE ufs_life_time_estimation gauge"
for hba in "${hosts[@]}"; do
  for type in a b; do
    value=$(to_dec "$(read_attr "$hba/health_descriptor/life_time_estimation_${type}")")
    [ -n "$value" ] || continue
    echo "ufs_life_time_estimation{device=\"$(escape "${hba##*/}")\",type=\"${type}\"} ${value}"
  done
done

metric eol_info \
  "Pre-EOL information: 0 = not reported, 1 = normal, 2 = warning (80% of reserved blocks used), 3 = urgent (90%)." \
  health_descriptor/eol_info
metric critical_health \
  "Number of critical health exceptions reported by the device since boot." \
  critical_health

echo "# HELP ufs_device_info UFS device identification."
echo "# TYPE ufs_device_info gauge"
for hba in "${hosts[@]}"; do
  manufacturer=$(read_attr "$hba/string_descriptors/manufacturer_name")
  product=$(read_attr "$hba/string_descriptors/product_name")
  revision=$(read_attr "$hba/string_descriptors/product_revision")
  spec=$(read_attr "$hba/device_descriptor/specification_version")
  printf 'ufs_device_info{device="%s",manufacturer="%s",product="%s",revision="%s",specification_version="%s"} 1\n' \
    "$(escape "${hba##*/}")" "$(escape "$manufacturer")" "$(escape "$product")" \
    "$(escape "$revision")" "$(escape "$spec")"
done
