#!/usr/bin/env python3

"""
NVMe device metrics textfile collector.
Requires nvme-cli package.

Formatted with Black:
$ black -l 100 nvme_metrics.py
"""

import json
import os
import re
import sys
import subprocess

# Disable automatic addition of _created series. Must be set before importing prometheus_client.
os.environ["PROMETHEUS_DISABLE_CREATED_SERIES"] = "true"

from prometheus_client import CollectorRegistry, Counter, Gauge, Info, generate_latest  # noqa: E402

registry = CollectorRegistry()
namespace = "nvme"

metrics = {
    # fmt: off
    "nvmecli": Info(
        "nvmecli",
        "nvme-cli tool information",
        ["version"], namespace=namespace, registry=registry,
    ),

    # Controller-specific (e.g. "nvme0") metrics
    "avail_spare": Gauge(
        "available_spare_ratio",
        "Device available spare ratio",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "controller_busy_time": Counter(
        "controller_busy_time_seconds",
        "Device controller busy time in seconds",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "controller_info": Info(
        "controller",
        "Controller information",
        ["controller", "model", "firmware", "serial", "transport"], namespace=namespace,
        registry=registry,
    ),
    "critical_warning": Gauge(
        "critical_warning",
        "Device critical warning bitmap field",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "data_units_read": Counter(
        "data_units_read_total",
        "Number of 512-byte data units read by host, reported in thousands",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "data_units_written": Counter(
        "data_units_written_total",
        "Number of 512-byte data units written by host, reported in thousands",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "host_read_commands": Counter(
        "host_read_commands_total",
        "Device read commands from host",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "host_write_commands": Counter(
        "host_write_commands_total",
        "Device write commands from host",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "media_errors": Counter(
        "media_errors_total",
        "Device media errors total",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "num_err_log_entries": Counter(
        "num_err_log_entries_total",
        "Device error log entry count",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "percent_used": Gauge(
        "percentage_used_ratio",
        "Device percentage used ratio",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "power_cycles": Counter(
        "power_cycles_total",
        "Device number of power cycles",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "power_on_hours": Counter(
        "power_on_hours_total",
        "Device power-on hours",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "spare_thresh": Gauge(
        "available_spare_threshold_ratio",
        "Device available spare threshold ratio",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "temperature": Gauge(
        "temperature_celsius",
        "Device temperature in degrees Celsius",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "unsafe_shutdowns": Counter(
        "unsafe_shutdowns_total",
        "Device number of unsafe shutdowns",
        ["controller"], namespace=namespace, registry=registry,
    ),

    # Namespace-specific (e.g. "nvme0n1") metrics
    "physical_size": Gauge(
        "physical_size_bytes",
        "Device size in bytes",
        ["device"], namespace=namespace, registry=registry,
    ),
    "sector_size": Gauge(
        "sector_size_bytes",
        "Device sector size in bytes",
        ["device"], namespace=namespace, registry=registry,
    ),
    "used_bytes": Gauge(
        "used_bytes",
        "Device used size in bytes",
        ["device"], namespace=namespace, registry=registry,
    ),
    # fmt: on
}


def exec_nvme(*args):
    """
    Execute nvme CLI tool with specified arguments and return captured stdout result. Set LC_ALL=C
    in child process environment so that the nvme tool does not perform any locale-specific number
    or date formatting, etc.
    """
    cmd = ["nvme", *args]
    return subprocess.check_output(cmd, stderr=subprocess.PIPE, env=dict(os.environ, LC_ALL="C"))


def exec_nvme_json(*args):
    """
    Execute nvme CLI tool with specified arguments and return parsed JSON output.
    """
    # Note: nvme-cli v2.11 effectively introduced a breaking change by forcing JSON output to always
    # be verbose. Older versions of nvme-cli optionally produced verbose output if the --verbose
    # flag was specified. In order to avoid having to handle two different JSON schemas, always
    # add the --verbose flag.
    output = exec_nvme(*args, "--output-format", "json", "--verbose")
    return json.loads(output)


def main():
    match = re.match(r"^nvme version (\S+)", exec_nvme("version").decode())
    if match:
        cli_version = match.group(1)
    else:
        cli_version = "unknown"
    metrics["nvmecli"].labels(cli_version)

    device_list = exec_nvme_json("list")

    for device in device_list["Devices"]:
        for subsys in device["Subsystems"]:
            for ctrl in subsys["Controllers"]:
                ctrl_dev = ctrl["Controller"]

                metrics["controller_info"].labels(
                    ctrl_dev,
                    ctrl["ModelNumber"],
                    ctrl["Firmware"],
                    ctrl["SerialNumber"].strip(),
                    ctrl["Transport"],
                )

                for ns in ctrl["Namespaces"]:
                    device_name = ns["NameSpace"]

                    metrics["sector_size"].labels(device_name).set(ns["SectorSize"])
                    metrics["physical_size"].labels(device_name).set(ns["PhysicalSize"])
                    metrics["used_bytes"].labels(device_name).set(ns["UsedBytes"])

                # Most SSDs (perhaps _all_ consumer grade SSDs) only contain a single namespace.
                # Fetch the device global SMART log by omitting any --namespace-id flag.
                smart_log = exec_nvme_json("smart-log", os.path.join("/dev", ctrl["Controller"]))

                # Various counters in the NVMe specification are 128-bit, which would have to
                # discard resolution if converted to a JSON number (i.e., float64_t). Instead,
                # nvme-cli marshals them as strings. As such, they need to be explicitly cast to int
                # or float when using them in Counter metrics.
                metrics["data_units_read"].labels(ctrl_dev).inc(int(smart_log["data_units_read"]))
                metrics["data_units_written"].labels(ctrl_dev).inc(
                    int(smart_log["data_units_written"])
                )
                metrics["host_read_commands"].labels(ctrl_dev).inc(
                    int(smart_log["host_read_commands"])
                )
                metrics["host_write_commands"].labels(ctrl_dev).inc(
                    int(smart_log["host_write_commands"])
                )
                metrics["avail_spare"].labels(ctrl_dev).set(smart_log["avail_spare"] / 100)
                metrics["spare_thresh"].labels(ctrl_dev).set(smart_log["spare_thresh"] / 100)
                metrics["percent_used"].labels(ctrl_dev).set(smart_log["percent_used"] / 100)
                metrics["critical_warning"].labels(ctrl_dev).set(
                    smart_log["critical_warning"]["value"]
                )
                metrics["media_errors"].labels(ctrl_dev).inc(int(smart_log["media_errors"]))
                metrics["num_err_log_entries"].labels(ctrl_dev).inc(
                    int(smart_log["num_err_log_entries"])
                )
                metrics["power_cycles"].labels(ctrl_dev).inc(int(smart_log["power_cycles"]))
                metrics["power_on_hours"].labels(ctrl_dev).inc(int(smart_log["power_on_hours"]))
                metrics["controller_busy_time"].labels(ctrl_dev).inc(
                    int(smart_log["controller_busy_time"])
                )
                metrics["unsafe_shutdowns"].labels(ctrl_dev).inc(int(smart_log["unsafe_shutdowns"]))

                # NVMe reports temperature in kelvins; convert it to degrees Celsius.
                metrics["temperature"].labels(ctrl_dev).set(smart_log["temperature"] - 273)


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERROR: script requires root privileges", file=sys.stderr)
        sys.exit(1)

    # Check if nvme-cli is installed
    try:
        exec_nvme()
    except FileNotFoundError:
        print("ERROR: nvme-cli is not installed. Aborting.", file=sys.stderr)
        sys.exit(1)

    try:
        main()
    except Exception as e:
        print("ERROR: {}".format(e), file=sys.stderr)
        sys.exit(1)

    print(generate_latest(registry).decode(), end="")
