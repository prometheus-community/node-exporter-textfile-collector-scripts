#!/usr/bin/env python3

"""
Description: Expose metrics from needrestart.

This script runs needrestart in batch mode. It will never ask for input
and will never restart or upgrade anything.

Dependencies: python >= 3.5, python3-prometheus-client, needrestart

Authors: RomainMou
"""

import time
import subprocess
from collections import Counter
from enum import Enum

from prometheus_client import (
    CollectorRegistry,
    Gauge,
    generate_latest,
)


class KernelStatus(Enum):
    UNKNOWN = 0
    CURRENT = 1
    ABI_UPGRADE = 2
    VERSION_UPGRADE = 3


class MicroCodeStatus(Enum):
    UNKNOWN = 0
    CURRENT = 1
    OBSOLETE = 2


class NeedRestartData:
    def __init__(self, needrestart_output):
        # Some default value
        self.timestamp = int(time.time())
        self.version = None
        self.kernel_status = None
        self.microcode_status = None
        self.kernel_current_version = ""
        self.kernel_expected_version = ""
        self.microcode_current_version = ""
        self.microcode_expected_version = ""
        needrestart_counter = Counter()

        # Parse the cmd output
        for line in needrestart_output.splitlines():
            key, value = line.split(": ", maxsplit=1)
            if key == "NEEDRESTART-VER":
                self.version = value
            # Kernel informations
            elif key == "NEEDRESTART-KCUR":
                self.kernel_current_version = value
            elif key == "NEEDRESTART-KEXP":
                self.kernel_expected_version = value
            elif key == "NEEDRESTART-KSTA":
                self.kernel_status = KernelStatus(int(value))
            # Microcode informations
            elif key == "NEEDRESTART-UCCUR":
                self.microcode_current_version = value
            elif key == "NEEDRESTART-UCEXP":
                self.microcode_expected_version = value
            elif key == "NEEDRESTART-UCSTA":
                self.microcode_status = MicroCodeStatus(int(value))
            # Count the others
            else:
                needrestart_counter.update({key})

        self.services_count = needrestart_counter["NEEDRESTART-SVC"]
        self.containers_count = needrestart_counter["NEEDRESTART-CONT"]
        self.sessions_count = needrestart_counter["NEEDRESTART-SESS"]


def write_timestamp(registry, needrestart_data):
    g = Gauge(
        "needrestart_timestamp_seconds",
        "information about the version and when it was last run",
        labelnames=["version"],
        registry=registry,
    )
    g.labels(needrestart_data.version).set(needrestart_data.timestamp)


def write_kernel(registry, needrestart_data):
    if needrestart_data.kernel_status:
        e = Gauge(
            "needrestart_kernel_status_info",
            "information about the kernel status",
            labelnames=["current", "expected"],
            registry=registry,
        )
        e.labels(
            needrestart_data.kernel_current_version,
            needrestart_data.kernel_expected_version,
        ).set(needrestart_data.kernel_status.value)


def write_microcode(registry, needrestart_data):
    if needrestart_data.microcode_status:
        e = Gauge(
            "needrestart_microcode_status_info",
            "information about the microcode status",
            labelnames=["current", "expected"],
            registry=registry,
        )
        e.labels(
            needrestart_data.microcode_current_version,
            needrestart_data.microcode_expected_version,
        ).set(needrestart_data.microcode_status.value)


def write_services(registry, needrestart_data):
    g = Gauge(
        "needrestart_services_total",
        "number of services requiring a restart",
        registry=registry,
    )
    g.set(needrestart_data.services_count)


def write_containers(registry, needrestart_data):
    g = Gauge(
        "needrestart_containers_total",
        "number of containers requiring a restart",
        registry=registry,
    )
    g.set(needrestart_data.containers_count)


def write_sessions(registry, needrestart_data):
    g = Gauge(
        "needrestart_sessions_total",
        "number of sessions requiring a restart",
        registry=registry,
    )
    g.set(needrestart_data.sessions_count)


def main():
    registry = CollectorRegistry()

    needrestart_output = subprocess.run(
        ["needrestart", "-b"], capture_output=True, text=True
    ).stdout
    needrestart_data = NeedRestartData(needrestart_output)

    write_timestamp(registry, needrestart_data)
    write_kernel(registry, needrestart_data)
    write_microcode(registry, needrestart_data)
    write_services(registry, needrestart_data)
    write_containers(registry, needrestart_data)
    write_sessions(registry, needrestart_data)

    print(generate_latest(registry).decode(), end="")


if __name__ == "__main__":
    main()
