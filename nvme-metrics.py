#!/usr/bin/env python3

# Description: Extract NVME device metrics from `nvme list` and `nvme-cli smartlog`.
# Author: Georgi Valkov <georgi.t.valkov@gmail.com>

import json
import textwrap
import subprocess
import collections


def run_nvme(*args):
    cmd = ["nvme", *args, "-o", "json"]
    out = subprocess.check_output(cmd)
    return json.loads(out)


labels_config = [
    ("DevicePath", "device"),
    ("Firmware", "firmware"),
    ("SerialNumber", "serial"),
    ("ModelNumber", "model"),
    ("SectorSize", "sector_size"),
]

series_config = [
    ("temperature", "temperature_celsius", lambda x: int(x) - 273),
    ("critical_warning", "critical_warning_value", int),
    ("avail_spare", "avail_spare_percent", lambda x: int(x) / 100),
    ("spare_thresh", "spare_thresh_percent", lambda x: int(x) / 100),
    ("percent_used", "percent_used", int),
    ("data_units_read", "data_units_read", int),
    ("data_units_written", "data_units_written", int),
    ("host_read_commands", "host_read_commands", int),
    ("host_write_commands", "host_write_commands", int),
    ("controller_busy_time", "controller_busy_time_minutes", int),
    ("power_cycles", "power_cycles_count", int),
    ("power_on_hours", "power_on_hours", int),
    ("unsafe_shutdowns", "unsafe_shutdowns", int),
    ("media_errors", "media_errors", int),
    ("num_err_log_entries", "num_err_log_entries", int),
    ("warning_temp_time", "warning_temp_time", int),
    ("critical_comp_time", "critical_comp_time", int),
]

# Help messages copied or derived from the NVME spec (page 90):
# https://nvmexpress.org/wp-content/uploads/NVM-Express-1_2a.pdf
series_help = {
    "temperature_celsius": ("gauge", """
        Composite temperature of the controller and namespaces associated with
        controller."""),

    "critical_warning_value": ("gauge", """
        Controller state warnings. Each bit is a critical warning type and multiple
        bits may be set."""),

    "avail_spare_percent": ("gauge", """
        Contains a normalized percentage (0.0 to 1.0) of the remaining spare
        capacity available."""),

    "spare_thresh_percent": ("gauge", """
        When avail_spare_percent falls below this threshold, an asynchronous event
        completion may occur."""),

    "percent_used": ("gauge", """
        Vendor specific estimate of the drive's life, based on the actual usage and
        the vendor's prediction. A value of 100 indicates that the estimated
        endurance the drive has been consumed, but may not indicate a failure. The
        value is allowed to exceed 100. Percentages greater than 254 shall be
        represented as 255. This value shall be updated once per power-on hour (when
        the controller is not in a sleep state."""),

    "data_units_read": ("gauge", """
        Number of 512 byte data units the host has read from the controller; this
        value does not include metadata. This value is reported in thousands (i.e. a
        value of 1 corresponds to 1000 units of 512 bytes read) and is rounded up.
        When the LBA size is a value other than 512 bytes, the controller shall
        convert the amount of data read to 512 byte units."""),

    "data_units_written": ("gauge", """
        Number of 512 byte data units the host has written to the controller; this
        value does not include metadata. This value is reported in thousands (i.e. a
        value of 1 corresponds to 1000 units of 512 bytes written) and is rounded
        up. When the LBA size is a value other than 512 bytes, the controller shall
        convert the amount of data written to 512 byte units."""),

    "host_read_commands": ("gauge", "Number of read commands completed by the controller."),

    "host_write_commands": ("gauge", "Number of write commands completed by the controller."),

    "controller_busy_time_minutes": ("gauge", """
        Time in minutes the controller is busy with I/O commands. The controller is
        busy when there is a command outstanding to an I/O queue."""),

    "power_cycles_count": ("counter", "Number of power cycles."),

    "power_on_hours": ("counter", """
        Number of power-on hours. This may not include time that the controller was
        powered and in a non-operational power state."""),

    "unsafe_shutdowns": ("counter", """
        Number of unsafe shutdowns. This count is incremented when a shutdown
        notification (CC.SHN) is not received prior to loss of power."""),

    "media_errors": ("counter", """
        Number of occurrences where the controller detected an unrecoverable data
        integrity error. Errors such as uncorrectable ECC, CRC checksum failure, or
        LBA tag mismatch are included in this field."""),

    "num_err_log_entries": ("counter", """
        Number of Error Information log entries over the life of the controller"""),

    "warning_temp_time": ("gauge", """
        Time in minutes that the controller is operational and the
        temperature_celsius field is greater than or equal to the Warning Composite
        Temperature Threshold (WCTEMP) field and less than the Critical Composite
        Temperature Threshold (CCTEMP) field."""),

    "critical_comp_time": ("gauge", """
        Time in minutes that the controller is operational and the
        temperature_celsius field is greater the Critical Composite Temperature
        Threshold (CCTEMP) field"""),

    "physical_size_bytes": ("gauge", "Drive size in bytes"),
    "used_bytes": ("gauge", "Used space in bytes"),
    "maximum_lba_count": ("gauge", "Maximum number of Logical Block Units"),
    "sector_size_bytes": ("gauge", "Sector size in bytes"),
}


series = collections.defaultdict(list)
for device_json in run_nvme("list")["Devices"]:
    device_path = device_json["DevicePath"]

    labels = {}
    for key, label in labels_config:
        labels[label] = device_json[key]

    data = run_nvme("smart-log", device_path)

    for key, name, func in series_config:
        series[name].append((labels, func(data[key])))

    series["physical_size_bytes"].append((labels, int(device_json["PhysicalSize"])))
    series["used_bytes"].append((labels, int(device_json["UsedBytes"])))
    series["maximum_lba_count"].append((labels, int(device_json["MaximumLBA"])))


for name in series:
    help_msg = textwrap.dedent(series_help[name][1]).strip().replace("\n", " ")
    print("# HELP nvme_%s %s" % (name, help_msg))
    print("# TYPE nvme_%s %s" % (name, series_help[name][0]))

    for labels, value in series[name]:
        labels = ",".join('%s="%s"' % kv for kv in labels.items())
        line = "nvme_%s{%s} %s" % (name, labels, value)
        print(line)
