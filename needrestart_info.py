#!/usr/bin/env python3
#
#
# Description: Expose metrics from needrestart.
#
# This script runs needrestart in batch mode. It will never ask for input
# and will never restart or upgrade anything.
#
# Dependencies: python >= 3.5, python3-prometheus-client, needrestart
#
# Authors: RomainMou

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
    OBSELETE = 2


class NeedrestartParser:
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
        for line in needrestart_output.stdout.decode().splitlines():
            key, value = line.split(": ")
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


def _write_timestamp(registry, needrestart_data):
    g = Gauge(
        "needrestart_timestamp",
        "information about the version and when it was last run",
        labelnames=["version"],
        registry=registry,
    )
    g.labels(needrestart_data.version).set(needrestart_data.timestamp)


def _write_kernel(registry, needrestart_data):
    if needrestart_data.kernel_status:
        e = Gauge(
            "needrestart_kernel_status",
            "information about the kernel status",
            labelnames=["current", "expected"],
            registry=registry,
        )
        e.labels(
            needrestart_data.kernel_current_version,
            needrestart_data.kernel_expected_version,
        ).set(needrestart_data.kernel_status.value)


def _write_microcode(registry, needrestart_data):
    if needrestart_data.microcode_status:
        e = Gauge(
            "needrestart_microcode_status",
            "information about the microcode status",
            labelnames=["current", "expected"],
            registry=registry,
        )
        e.labels(
            needrestart_data.microcode_current_version,
            needrestart_data.microcode_expected_version,
        ).set(needrestart_data.microcode_status.value)


def _write_services(registry, needrestart_data):
    g = Gauge(
        "needrestart_services_count",
        "number of services requiring a restart",
        registry=registry,
    )
    g.set(needrestart_data.services_count)


def _write_containers(registry, needrestart_data):
    g = Gauge(
        "needrestart_containers_count",
        "number of containers requiring a restart",
        registry=registry,
    )
    g.set(needrestart_data.containers_count)


def _write_sessions(registry, needrestart_data):
    g = Gauge(
        "needrestart_sessions_count",
        "number of sessions requiring a restart",
        registry=registry,
    )
    g.set(needrestart_data.sessions_count)


def _main():
    registry = CollectorRegistry()
    needrestart_data = NeedrestartParser(
        subprocess.run(["needrestart", "-b"], stdout=subprocess.PIPE)
    )

    _write_timestamp(registry, needrestart_data)
    _write_kernel(registry, needrestart_data)
    _write_microcode(registry, needrestart_data)
    _write_services(registry, needrestart_data)
    _write_containers(registry, needrestart_data)
    _write_sessions(registry, needrestart_data)

    print(generate_latest(registry).decode(), end="")


if __name__ == "__main__":
    _main()
