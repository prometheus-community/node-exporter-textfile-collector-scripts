#!/usr/bin/env python3
"""
Script to parse StorCLI's JSON output and expose MegaRAID health as Prometheus metrics.

Tested against StorCLI 'Ver 1.14.12 Nov 25, 2014'.
                   and '007.1108.0000.0000 July 17, 2019'

StorCLI reference manual: https://docs.broadcom.com/docs/12352476

Advanced Software Options (ASO) not exposed as metrics currently.

JSON key abbreviations used by StorCLI are documented in the standard command output, i.e. when the
trailing 'J' is omitted from the command.

Formatting done with Black:
$ black -l 100 storcli.py
"""

import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime

from prometheus_client import CollectorRegistry, Gauge, generate_latest

__doc__ = "Parse StorCLI's JSON output and expose MegaRAID health as Prometheus metrics."
__version__ = "0.1.0"

storcli_path = ""
namespace = "megaraid"
registry = CollectorRegistry()

metrics = {
    # fmt: off
    "ctrl_info": Gauge(
        "controller_info",
        "MegaRAID controller info",
        ["controller", "model", "serial", "fwversion"], namespace=namespace, registry=registry,
    ),
    "ctrl_temperature": Gauge(
        "temperature",
        "MegaRAID controller temperature",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_healthy": Gauge(
        "healthy",
        "MegaRAID controller healthy",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_degraded": Gauge(
        "degraded",
        "MegaRAID controller degraded",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_failed": Gauge(
        "failed",
        "MegaRAID controller failed",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_time_difference": Gauge(
        "time_difference",
        "MegaRAID time difference",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "bbu_healthy": Gauge(
        "battery_backup_healthy",
        "MegaRAID battery backup healthy",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "bbu_temperature": Gauge(
        "bbu_temperature",
        "MegaRAID battery backup temperature",
        ["controller", "bbuidx"], namespace=namespace, registry=registry,
    ),
    "cv_temperature": Gauge(
        "cv_temperature",
        "MegaRAID CacheVault temperature",
        ["controller", "cvidx"], namespace=namespace, registry=registry,
    ),
    "ctrl_sched_patrol_read": Gauge(
        "scheduled_patrol_read",
        "MegaRAID scheduled patrol read",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_ports": Gauge(
        "ports",
        "MegaRAID ports",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_physical_drives": Gauge(
        "physical_drives",
        "MegaRAID physical drives",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_drive_groups": Gauge(
        "drive_groups",
        "MegaRAID drive groups",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "ctrl_virtual_drives": Gauge(
        "virtual_drives",
        "MegaRAID virtual drives",
        ["controller"], namespace=namespace, registry=registry,
    ),
    "vd_info": Gauge(
        "vd_info",
        "MegaRAID virtual drive info",
        ["controller", "DG", "VG", "name", "cache", "type", "state"],
        namespace=namespace, registry=registry,
    ),
    "pd_shield_counter": Gauge(
        "pd_shield_counter",
        "MegaRAID physical drive shield counter",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_media_errors": Gauge(
        "pd_media_errors",
        "MegaRAID physical drive media errors",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_other_errors": Gauge(
        "pd_other_errors",
        "MegaRAID physical drive other errors",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_predictive_errors": Gauge(
        "pd_predictive_errors",
        "MegaRAID physical drive predictive errors",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_smart_alerted": Gauge(
        "pd_smart_alerted",
        "MegaRAID physical drive SMART alerted",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_link_speed": Gauge(
        "pd_link_speed_gbps",
        "MegaRAID physical drive link speed in Gbps",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_device_speed": Gauge(
        "pd_device_speed_gbps",
        "MegaRAID physical drive device speed in Gbps",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_commissioned_spare": Gauge(
        "pd_commissioned_spare",
        "MegaRAID physical drive commissioned spare",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_emergency_spare": Gauge(
        "pd_emergency_spare",
        "MegaRAID physical drive emergency spare",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    "pd_info": Gauge(
        "pd_info",
        "MegaRAID physical drive info",
        [
            "controller",
            "enclosure",
            "slot",
            "disk_id",
            "interface",
            "media",
            "model",
            "DG",
            "state",
            "firmware",
            "serial",
        ],
        namespace=namespace, registry=registry,
    ),
    "pd_temp": Gauge(
        "pd_temp_celsius",
        "MegaRAID physical drive temperature in degrees Celsius",
        ["controller", "enclosure", "slot"], namespace=namespace, registry=registry,
    ),
    # fmt: on
}


def main(args):
    """main"""
    global storcli_path
    storcli_path = args.storcli_path
    data = get_storcli_json("/cALL show all J")

    try:
        # All the information is collected underneath the Controllers key
        data = data["Controllers"]

        for controller in data:
            response = controller["Response Data"]

            handle_common_controller(response)
            if response["Version"]["Driver Name"] == "megaraid_sas":
                handle_megaraid_controller(response)
            elif response["Version"]["Driver Name"] == "mpt3sas":
                handle_sas_controller(response)
    except KeyError:
        pass

    print(generate_latest(registry).decode(), end="")


def handle_common_controller(response):
    controller_index = response["Basics"]["Controller"]

    metrics["ctrl_info"].labels(
        controller_index,
        response["Basics"]["Model"],
        response["Basics"]["Serial Number"],
        response["Version"]["Firmware Version"],
    ).set(1)

    # Older boards don't have this sensor at all ("Temperature Sensor for ROC" : "Absent")
    for key in ["ROC temperature(Degree Celcius)", "ROC temperature(Degree Celsius)"]:
        if key in response["HwCfg"]:
            metrics["ctrl_temperature"].labels(controller_index).set(response["HwCfg"][key])
            break


def handle_sas_controller(response):
    controller_index = response["Basics"]["Controller"]

    metrics["ctrl_healthy"].labels(controller_index).set(
        response["Status"]["Controller Status"] == "OK"
    )
    metrics["ctrl_ports"].labels(controller_index).set(response["HwCfg"]["Backend Port Count"])

    try:
        # The number of physical disks is half of the number of items in this dict. Every disk is
        # listed twice - once for basic info, again for detailed info.
        metrics["ctrl_physical_drives"].labels(controller_index).set(
            len(response["Physical Device Information"].keys()) / 2
        )
    except AttributeError:
        pass

    for key, basic_disk_info in response["Physical Device Information"].items():
        if "Detailed Information" in key:
            continue
        create_metrics_of_physical_drive(
            basic_disk_info[0], response["Physical Device Information"], controller_index
        )


def handle_megaraid_controller(response):
    controller_index = response["Basics"]["Controller"]

    if response["Status"]["BBU Status"] != "NA":
        # BBU Status Optimal value is 0 for normal, 8 for charging.
        metrics["bbu_healthy"].labels(controller_index).set(
            response["Status"]["BBU Status"] in [0, 8, 4096]
        )

    metrics["ctrl_degraded"].labels(controller_index).set(
        response["Status"]["Controller Status"] == "Degraded"
    )
    metrics["ctrl_failed"].labels(controller_index).set(
        response["Status"]["Controller Status"] == "Failed"
    )
    metrics["ctrl_healthy"].labels(controller_index).set(
        response["Status"]["Controller Status"] == "Optimal"
    )
    metrics["ctrl_ports"].labels(controller_index).set(response["HwCfg"]["Backend Port Count"])
    metrics["ctrl_sched_patrol_read"].labels(controller_index).set(
        "hrs" in response["Scheduled Tasks"]["Patrol Read Reoccurrence"]
    )

    for cvidx, cvinfo in enumerate(response.get("Cachevault_Info", [])):
        if "Temp" in cvinfo:
            metrics["cv_temperature"].labels(controller_index, cvidx).set(
                cvinfo["Temp"].replace("C", "")
            )

    for bbuidx, bbuinfo in enumerate(response.get("BBU_Info", [])):
        if "Temp" in bbuinfo:
            metrics["bbu_temperature"].labels(controller_index, bbuidx).set(
                bbuinfo["Temp"].replace("C", "")
            )

    system_time = datetime.strptime(
        response["Basics"]["Current System Date/time"], "%m/%d/%Y, %H:%M:%S"
    )
    controller_time = datetime.strptime(
        response["Basics"]["Current Controller Date/Time"], "%m/%d/%Y, %H:%M:%S"
    )
    if system_time and controller_time:
        metrics["ctrl_time_difference"].labels(controller_index).set(
            abs(system_time - controller_time).seconds
        )

    # Make sure it doesn't crash if it's a JBOD setup
    if "Drive Groups" in response:
        metrics["ctrl_drive_groups"].labels(controller_index).set(response["Drive Groups"])
        metrics["ctrl_virtual_drives"].labels(controller_index).set(response["Virtual Drives"])

        for virtual_drive in response["VD LIST"]:
            vd_position = virtual_drive.get("DG/VD")
            if vd_position:
                drive_group, volume_group = vd_position.split("/")[:2]
            else:
                drive_group, volume_group = -1, -1

            metrics["vd_info"].labels(
                controller_index,
                drive_group,
                volume_group,
                virtual_drive["Name"],
                virtual_drive["Cache"],
                virtual_drive["TYPE"],
                virtual_drive["State"],
            ).set(1)

    metrics["ctrl_physical_drives"].labels(controller_index).set(response["Physical Drives"])

    if response["Physical Drives"] > 0:
        data = get_storcli_json("/cALL/eALL/sALL show all J")
        drive_info = data["Controllers"][controller_index]["Response Data"]
    for physical_drive in response["PD LIST"]:
        create_metrics_of_physical_drive(physical_drive, drive_info, controller_index)


def create_metrics_of_physical_drive(physical_drive, detailed_info_array, controller_index):
    enclosure, slot = physical_drive.get("EID:Slt").split(":")[:2]

    if enclosure == " ":
        drive_identifier = "Drive /c{0}/s{1}".format(controller_index, slot)
        enclosure = ""
    else:
        drive_identifier = "Drive /c{0}/e{1}/s{2}".format(controller_index, enclosure, slot)

    try:
        info = detailed_info_array[drive_identifier + " - Detailed Information"]
        state = info[drive_identifier + " State"]
        attributes = info[drive_identifier + " Device attributes"]
        settings = info[drive_identifier + " Policies/Settings"]

        if state["Shield Counter"] != "N/A":
            metrics["pd_shield_counter"].labels(controller_index, enclosure, slot).set(
                state["Shield Counter"]
            )
        if state["Media Error Count"] != "N/A":
            metrics["pd_media_errors"].labels(controller_index, enclosure, slot).set(
                state["Media Error Count"]
            )
        if state["Other Error Count"] != "N/A":
            metrics["pd_other_errors"].labels(controller_index, enclosure, slot).set(
                state["Other Error Count"]
            )
        if state["Predictive Failure Count"] != "N/A":
            metrics["pd_predictive_errors"].labels(controller_index, enclosure, slot).set(
                state["Predictive Failure Count"]
            )
        metrics["pd_smart_alerted"].labels(controller_index, enclosure, slot).set(
            state["S.M.A.R.T alert flagged by drive"] == "Yes"
        )
        if attributes["Link Speed"] != "Unknown":
            metrics["pd_link_speed"].labels(controller_index, enclosure, slot).set(
                attributes["Link Speed"].split(".")[0]
            )
        if attributes["Device Speed"] != "Unknown":
            metrics["pd_device_speed"].labels(controller_index, enclosure, slot).set(
                attributes["Device Speed"].split(".")[0]
            )
        metrics["pd_commissioned_spare"].labels(controller_index, enclosure, slot).set(
            settings["Commissioned Spare"] == "Yes"
        )
        metrics["pd_emergency_spare"].labels(controller_index, enclosure, slot).set(
            settings["Emergency Spare"] == "Yes"
        )

        # Model, firmware version and serial number may be space-padded, so strip() them.
        metrics["pd_info"].labels(
            controller_index,
            enclosure,
            slot,
            physical_drive["DID"],
            physical_drive["Intf"],
            physical_drive["Med"],
            physical_drive["Model"].strip(),
            physical_drive["DG"],
            physical_drive["State"],
            attributes["Firmware Revision"].strip(),
            attributes["SN"].strip(),
        ).set(1)

        if "Drive Temperature" in state and state["Drive Temperature"] != "N/A":
            metrics["pd_temp"].labels(controller_index, enclosure, slot).set(
                state["Drive Temperature"].split("C")[0].strip()
            )
    except KeyError:
        pass


def get_storcli_json(storcli_args):
    """Get storcli output in JSON format."""
    # Check if storcli is installed and executable
    if not (os.path.isfile(storcli_path) and os.access(storcli_path, os.X_OK)):
        raise SystemExit(1)

    storcli_cmd = [storcli_path]
    storcli_cmd.extend(shlex.split(storcli_args))
    storcli_cmd.append("nolog")

    proc = subprocess.Popen(
        storcli_cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, _ = proc.communicate()
    data = json.loads(stdout.decode())

    if data["Controllers"][0]["Command Status"]["Status"] != "Success":
        raise SystemExit(1)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--storcli_path",
        default="/opt/MegaRAID/storcli/storcli64",
        help="path to StorCLI binary",
    )
    parser.add_argument("--version", action="version", version="%(prog)s {0}".format(__version__))

    args = parser.parse_args()
    main(args)
