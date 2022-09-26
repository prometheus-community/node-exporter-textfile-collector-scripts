#!/usr/bin/env bash
# Script informed by the collectd monitoring script for smartmontools (using smartctl)
# by Samuel B. <samuel_._behan_(at)_dob_._sk> (c) 2012
# source at: http://devel.dob.sk/collectd-scripts/

# TODO: This probably needs to be a little more complex.  The raw numbers can have more
#       data in them than you'd think.
#       http://arstechnica.com/civis/viewtopic.php?p=22062211

# Formatting done via shfmt -i 2
# https://github.com/mvdan/sh

parse_smartctl_attributes_awk="$(
  cat <<'SMARTCTLAWK'
$1 ~ /^ *[0-9]+$/ && $2 ~ /^[a-zA-Z0-9_-]+$/ {
  gsub(/-/, "_");
  printf "%s_value{%s,smart_id=\"%s\"} %d\n", $2, labels, $1, $4
  printf "%s_worst{%s,smart_id=\"%s\"} %d\n", $2, labels, $1, $5
  printf "%s_threshold{%s,smart_id=\"%s\"} %d\n", $2, labels, $1, $6
  printf "%s_raw_value{%s,smart_id=\"%s\"} %e\n", $2, labels, $1, $10
}
SMARTCTLAWK
)"

smartmon_attrs="$(
  cat <<'SMARTMONATTRS'
airflow_temperature_cel
command_timeout
current_pending_sector
end_to_end_error
erase_fail_count
g_sense_error_rate
hardware_ecc_recovered
host_reads_32mib
host_reads_mib
host_writes_32mib
host_writes_mib
load_cycle_count
media_wearout_indicator
nand_writes_1gib
offline_uncorrectable
power_cycle_count
power_on_hours
program_fail_cnt_total
program_fail_count
raw_read_error_rate
reallocated_event_count
reallocated_sector_ct
reported_uncorrect
runtime_bad_block
sata_downshift_count
seek_error_rate
spin_retry_count
spin_up_time
start_stop_count
temperature_case
temperature_celsius
temperature_internal
total_lbas_read
total_lbas_written
udma_crc_error_count
unsafe_shutdown_count
unused_rsvd_blk_cnt_tot
wear_leveling_count
workld_host_reads_perc
workld_media_wear_indic
workload_minutes
SMARTMONATTRS
)"
smartmon_attrs="$(echo "${smartmon_attrs}" | xargs | tr ' ' '|')"

# We should not hardcode the smartctl binary path,
# instead for those OS that does not follow the
# same default installation path, we should add it here.
os_detect() {
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                smartctl="/usr/sbin/smartctl"
        elif [[ "$OSTYPE" == "freebsd"* ]]; then
                smartctl="/usr/local/sbin/smartctl"
        else
                smartctl="/usr/sbin/smartctl"
        fi
}
os_detect

parse_smartctl_attributes() {
  local disk="$1"
  local disk_type="$2"
  local labels="disk=\"${disk}\",type=\"${disk_type}\""
  sed 's/^ \+//g' |
    awk -v labels="${labels}" "${parse_smartctl_attributes_awk}" 2>/dev/null |
    tr '[:upper:]' '[:lower:]' |
    grep -E "(${smartmon_attrs})"
}

parse_smartctl_scsi_attributes() {
  local disk="$1"
  local disk_type="$2"
  local labels="disk=\"${disk}\",type=\"${disk_type}\""
  while read -r line; do
    attr_type="$(echo "${line}" | tr '=' ':' | cut -f1 -d: | sed 's/^ \+//g' | tr ' ' '_')"
    attr_value="$(echo "${line}" | tr '=' ':' | cut -f2 -d: | sed 's/^ \+//g')"

    case "${line}" in
      # -x additional scsi attributes
      *"Reserved [0x0]"*)
        attr_type="Reserved_00"
        ((reserved_00++))
        ;;
      *"Require Write or Reassign Blocks command"*)
        attr_type="Require_Write_or_Reassign_Blocks_command"
        ((require_write_or_reassign_blocks_command++))
        ;;
      *"Successfully reassigned"*)
        attr_type="Successfully_reassigned"
        ((successfully_reassigned++))
        ;;
      *"Reserved [0x3]"*)
        attr_type="Reserved_03"
        ((reserved_03++))
        ;;
      *"Reassignment by disk failed"*)
        attr_type="Reassigned_by_disk_failed"
        ((reassigned_by_disk_failed++))
        ;;
      *"Recovered via rewrite in-place"*)
        attr_type="Recovered_via_rewrite_in_place"
        ((recovered_via_rewrite_in_place++))
        ;;
      *"Reassigned by app, has valid data"*)
        attr_type="Reassigned_by_app_has_valid_data"
        ((reassigned_by_app_has_valid_data++))
        ;;
      *"Reassigned by app, has no valid data"*)
        attr_type="Reassigned_by_app_has_no_valid_data"
        ((reassigned_by_app_has_no_valid_data++))
        ;;
      *"Unsuccessfully reassigned by app"*)
        attr_type="Unsuccessfully_reassigned_by_app"
        ((unsuccessfully_reassigned_by_app++))
        ;;
      # BMS status
      *"no scans active"*)
        attr_type="no_scans_active"
        attr_value="1"
        ;;
      *"scan is active"*)
        attr_type="scan_is_active"
        attr_value="1"
        ;;
      *"pre-scan is active"*)
        attr_type="pre_scan_is_active"
        attr_value="1"
        ;;
      *"halted due to fatal error"*)
        attr_type="halted_due_to_fatal_error"
        attr_value="1"
        ;;
      *"halted due to a vendor specific pattern of error"*)
        attr_type="halted_due_to_a_vendor_specific_pattern_of_error"
        attr_value="1"
        ;;
      *"halted due to medium formatted without P-List"*)
        attr_type="halted_due_to_medium_formatted_without_p_list"
        attr_value="1"
        ;;
      *"halted - vendor specific cause"*)
        attr_type="halted_vendor_specific_cause"
        attr_value="1"
        ;;
      *"halted due to temperature out of range"*)
        attr_type="halted_due_to_temperature_out_of_range"
        attr_value="1"
        ;;
      *"waiting until BMS interval timer expires"*)
        attr_type="waiting_until_bms_interval_timer_expires"
        attr_value="1"
        ;;
    esac

    case "${attr_type}" in
    number_of_hours_powered_up_) power_on="$(echo "${attr_value}" | awk '{ printf "%e\n", $1 }')" ;;
    Current_Drive_Temperature) temp_cel="$(echo "${attr_value}" | cut -f1 -d' ' | awk '{ printf "%e\n", $1 }')" ;;
    Blocks_sent_to_initiator_) lbas_read="$(echo "${attr_value}" | awk '{ printf "%e\n", $1 }')" ;;
    Blocks_received_from_initiator_) lbas_written="$(echo "${attr_value}" | awk '{ printf "%e\n", $1 }')" ;;
    Accumulated_start-stop_cycles) power_cycle="$(echo "${attr_value}" | awk '{ printf "%e\n", $1 }')" ;;
    Elements_in_grown_defect_list) grown_defects="$(echo "${attr_value}" | awk '{ printf "%e\n", $1 }')" ;;
    # -x scsi extra attributes
    # Reference: https://www.smartmontools.org/static/doxygen/scsiprint_8cpp.html#a595f28c7e1b92059bac5bdbeef928bfc
    Reserved_00) res_00="$(echo '${reserved_00}')" ;;
    Require_Write_or_Reassign_Blocks_command) req_write_or_reassign_blocks_command="$(echo '${require_write_or_reassign_blocks_command}')" ;;
    Successfully_reassigned) success_reassigned="$(echo '${successfully_reassigned}')" ;;
    Reserved_03) res_03="$(echo '${reserved_03}')" ;;
    Reassigned_by_disk_failed) reass_by_disk_failed="$(echo '${reassigned_by_disk_failed}')" ;;
    Recovered_via_rewrite_in_place) rec_viarewrite_in_place="$(echo '${recovered_via_rewrite_in_place}')" ;;
    Reassigned_by_app_has_valid_data) reass_by_app_has_valid_data="$(echo '${reassigned_by_app_has_valid_data}')" ;;
    Reassigned_by_app_has_no_valid_data) reass_by_app_has_no_valid_data="$(echo '${reassigned_by_app_has_no_valid_data}')" ;;
    Unsuccessfully_reassigned_by_app) unsu_reassigned_by_app="$(echo '${unsuccessfully_reassigned_by_app}')" ;;
    # -x BMS status
    # Reference: https://www.smartmontools.org/static/doxygen/scsiprint_8cpp.html#a390e02ad61129f5f2ea1c3b2cb1c41ed
    no_scans_active) n_scans_active="$(echo "${attr_value}")" ;;
    scan_is_active) sc_is_active="$(echo "${attr_value}")" ;;
    pre_scan_is_active) pr_scan_is_active="$(echo "${attr_value}")" ;;
    halted_due_to_fatal_error) ha_due_to_fatal_error="$(echo "${attr_value}")" ;;
    halted_due_to_a_vendor_specific_pattern_of_error) ha_due_to_a_vendor_specific_pattern_of_error="$(echo "${attr_value}")" ;;
    halted_due_to_medium_formatted_without_p_list) ha_due_to_medium_formatted_without_p_list="$(echo "${attr_value}")" ;;
    halted_vendor_specific_cause) ha_vendor_specific_cause="$(echo "${attr_value}")" ;;
    halted_due_to_temperature_out_of_range) ha_due_to_temperature_out_of_range="$(echo "${attr_value}")" ;;
    waiting_until_bms_interval_timer_expires) wa_until_bms_interval_timer_expires="$(echo "${attr_value}")" ;;
    esac
  done
  [ -n "$power_on" ] && echo "power_on_hours_raw_value{${labels},smart_id=\"9\"} ${power_on}"
  [ -n "$temp_cel" ] && echo "temperature_celsius_raw_value{${labels},smart_id=\"194\"} ${temp_cel}"
  [ -n "$lbas_read" ] && echo "total_lbas_read_raw_value{${labels},smart_id=\"242\"} ${lbas_read}"
  [ -n "$lbas_written" ] && echo "total_lbas_written_raw_value{${labels},smart_id=\"242\"} ${lbas_written}"
  [ -n "$power_cycle" ] && echo "power_cycle_count_raw_value{${labels},smart_id=\"12\"} ${power_cycle}"
  [ -n "$grown_defects" ] && echo "grown_defects_count_raw_value{${labels},smart_id=\"12\"} ${grown_defects}"
  # -x scsi extra attributes
  [ -n "$res_00" ] && echo "reserved_00{${labels}} ${reserved_00}"
  [ -n "$req_write_or_reassign_blocks_command" ] && echo "require_write_or_reassign_blocks_command{${labels}} ${require_write_or_reassign_blocks_command}"
  [ -n "$success_reassigned" ] && echo "successfully_reassigned{${labels}} ${successfully_reassigned}"
  [ -n "$res_03" ] && echo "reserved_03{${labels}} ${reserved_03}"
  [ -n "$reass_by_disk_failed" ] && echo "reassignment_by_disk_failed{${labels}} ${reassigned_by_disk_failed}"
  [ -n "$rec_viarewrite_in_place" ] && echo "recovered_via_rewrite_in_place{${labels}} ${recovered_via_rewrite_in_place}"
  [ -n "$reass_by_app_has_valid_data" ] && echo "reassigned_by_app_has_valid_data{${labels}} ${reassigned_by_app_has_valid_data}"
  [ -n "$reass_by_app_has_no_valid_data" ] && echo "reassigned_by_app_has_no_valid_data{${labels}} ${reassigned_by_app_has_no_valid_data}"
  [ -n "$unsu_reassigned_by_app" ] && echo "unsuccessfully_reassigned_by_app{${labels}} ${unsuccessfully_reassigned_by_app}"
  # -x BMS status
  [ -n "$n_scans_active" ] && echo "no_scans_active{${labels}} ${n_scans_active}"
  [ -n "$sc_is_active" ] && echo "scan_is_active{${labels}} ${sc_is_active}"
  [ -n "$pr_scan_is_active" ] && echo "pre_can_is_active{${labels}} ${pr_scan_is_active}"
  [ -n "$ha_due_to_fatal_error" ] && echo "halted_due_to_fatal_error{${labels}} ${ha_due_to_fatal_error}"
  [ -n "$ha_due_to_a_vendor_specific_pattern_of_error" ] && echo "halted_due_to_a_vendor_specific_pattern_of_error{${labels}} ${ha_due_to_a_vendor_specific_pattern_of_error}"
  [ -n "$ha_due_to_medium_formatted_without_p_list" ] && echo "halted_due_to_medium_formatted_without_p_list{${labels}} ${ha_due_to_medium_formatted_without_p_list}"
  [ -n "$ha_vendor_specific_cause" ] && echo "halted_vendor_specific_cause{${labels}} ${ha_vendor_specific_cause}"
  [ -n "$ha_due_to_temperature_out_of_range" ] && echo "halted_due_to_temperature_out_of_range{${labels}} ${ha_due_to_temperature_out_of_range}"
  [ -n "$wa_until_bms_interval_timer_expires" ] && echo "waiting_until_bms_interval_timer_expires{${labels}} ${wa_until_bms_interval_timer_expires}"

}

parse_smartctl_info() {
  local -i smart_available=0 smart_enabled=0 smart_healthy=
  local disk="$1" disk_type="$2"
  local model_family='' device_model='' serial_number='' fw_version='' vendor='' product='' revision='' lun_id=''
  while read -r line; do
    info_type="$(echo "${line}" | cut -f1 -d: | tr ' ' '_')"
    info_value="$(echo "${line}" | cut -f2- -d: | sed 's/^ \+//g' | sed 's/"/\\"/')"
    case "${info_type}" in
    Model_Family) model_family="${info_value}" ;;
    Device_Model) device_model="${info_value}" ;;
    Serial_Number) serial_number="${info_value}" ;;
    Firmware_Version) fw_version="${info_value}" ;;
    Vendor) vendor="${info_value}" ;;
    Product) product="${info_value}" ;;
    Revision) revision="${info_value}" ;;
    Logical_Unit_id) lun_id="${info_value}" ;;
    esac
    if [[ "${info_type}" == 'SMART_support_is' ]]; then
      case "${info_value:0:7}" in
      Enabled) smart_available=1; smart_enabled=1 ;;
      Availab) smart_available=1; smart_enabled=0 ;;
      Unavail) smart_available=0; smart_enabled=0 ;;
      esac
    fi
    if [[ "${info_type}" == 'SMART_overall-health_self-assessment_test_result' ]]; then
      case "${info_value:0:6}" in
      PASSED) smart_healthy=1 ;;
      *) smart_healthy=0 ;;
      esac
    elif [[ "${info_type}" == 'SMART_Health_Status' ]]; then
      case "${info_value:0:2}" in
      OK) smart_healthy=1 ;;
      *) smart_healthy=0 ;;
      esac
    fi
  done
  echo "device_info{disk=\"${disk}\",type=\"${disk_type}\",vendor=\"${vendor}\",product=\"${product}\",revision=\"${revision}\",lun_id=\"${lun_id}\",model_family=\"${model_family}\",device_model=\"${device_model}\",serial_number=\"${serial_number}\",firmware_version=\"${fw_version}\"} 1"
  echo "device_smart_available{disk=\"${disk}\",type=\"${disk_type}\"} ${smart_available}"
  echo "device_smart_enabled{disk=\"${disk}\",type=\"${disk_type}\"} ${smart_enabled}"
  [[ "${smart_healthy}" != "" ]] && echo "device_smart_healthy{disk=\"${disk}\",type=\"${disk_type}\"} ${smart_healthy}"
}

output_format_awk="$(
  cat <<'OUTPUTAWK'
BEGIN { v = "" }
v != $1 {
  print "# HELP smartmon_" $1 " SMART metric " $1;
  print "# TYPE smartmon_" $1 " gauge";
  v = $1
}
{print "smartmon_" $0}
OUTPUTAWK
)"

format_output() {
  sort |
    awk -F'{' "${output_format_awk}"
}

# If the system is configured with multipath, we might end up having metrics of
# duplicated disks.
containsDisk() {
        local serial_to_compare="$1"
        shift
        local device_list_filter=("$@")

        for device in "${device_list_filter[@]}"; do
                device_serial=$(echo "$device" | cut -f3 -d'|')
                if [[ "$serial_to_compare" == "$device_serial" ]]; then
                        echo "1"
                        break
                fi
        done
}

# Create a list of unique disks
device_disk_list() {
        mapfile -t smartctl_device_list < <("$smartctl" --scan-open | awk '/^\/dev/{print $1 "|" $3}')

        for device in "${smartctl_device_list[@]}"; do
                disk="$(echo "${device}" | cut -f1 -d '|')"
                serial="$($smartctl -i "$disk" | tr -d ' ' | awk -F':' '/Serial/ {print $2}')"

                disk_check=$(containsDisk "${serial}" "${device_list[@]}")
                if [[ ! $disk_check -eq "1" ]]; then
                        device_list+=( "${device}|${serial}" )
                fi
        done
}

smartctl_version="$("${smartctl}" -V | head -n1 | awk '$1 == "smartctl" {print $2}')"

echo "smartctl_version{version=\"${smartctl_version}\"} 1" | format_output

if [[ "$(expr "${smartctl_version}" : '\([0-9]*\)\..*')" -lt 6 ]]; then
  exit
fi

# Get an unique list of disks in case they are in multipath
device_disk_list
for device in "${device_list[@]}"; do
  disk="$(echo "${device}" | cut -f1 -d'|')"
  type="$(echo "${device}" | cut -f2 -d'|')"
  active=1
  echo "smartctl_run{disk=\"${disk}\",type=\"${type}\"}" "$(TZ=UTC date '+%s')"
  # Check if the device is in a low-power mode
  "${smartctl}" -n standby -d "${type}" "${disk}" > /dev/null || active=0
  echo "device_active{disk=\"${disk}\",type=\"${type}\"}" "${active}"
  # Skip further metrics to prevent the disk from spinning up
  test ${active} -eq 0 && continue
  # Get the SMART information and health
  "${smartctl}" -i -H -d "${type}" "${disk}" | parse_smartctl_info "${disk}" "${type}"
  # Get the SMART attributes
  case ${type} in
  sat) "${smartctl}" -A -d "${type}" "${disk}" | parse_smartctl_attributes "${disk}" "${type}" ;;
  sat+megaraid*) "${smartctl}" -A -d "${type}" "${disk}" | parse_smartctl_attributes "${disk}" "${type}" ;;
  scsi) "${smartctl}" -A -x -d "${type}" "${disk}" | parse_smartctl_scsi_attributes "${disk}" "${type}" ;;
  megaraid*) "${smartctl}" -A -d "${type}" "${disk}" | parse_smartctl_scsi_attributes "${disk}" "${type}" ;;
  nvme*) "${smartctl}" -A -d "${type}" "${disk}" | parse_smartctl_scsi_attributes "${disk}" "${type}" ;;
  *)
      (>&2 echo "disk type is not sat, scsi, nvme or megaraid but ${type}")
    exit
    ;;
  esac
done | format_output
