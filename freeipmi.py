#!/usr/bin/env python3
"""
Script to collect IPMI metrics and expose them as Prometheus text-format metrics.

This is a oneshot local-only textfile collector that wraps FreeIPMI tools.

Collectors:
  - ipmi: ipmi-sensors (temperature, voltage, fan, generic sensors)
  - dcmi: ipmi-dcmi (power consumption)
  - chassis: ipmi-chassis (power state)
  - bmc: bmc-info (BMC device info)

Usage:
    python freeipmi.py [--help]

Output:
    Prometheus text format metrics to stdout

Error handling:
    - Exits silently if no IPMI device found
    - Logs errors to stderr without polluting metrics output
    - Returns exit code 0 on success, 1 on error
"""

import argparse
import csv
import logging
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from prometheus_client import CollectorRegistry, Gauge, generate_latest

__doc__ = "Collect IPMI metrics and expose them as Prometheus text-format metrics."
__version__ = "0.1.0"

namespace_default = "node_ipmi"

IPMI_DEVICES = ["/dev/ipmi0", "/dev/ipmi/0", "/dev/ipmidev/0"]
LABELS = ["id", "name", "type"]

# Configure logging for stderr only
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def get_metrics(registry, namespace):
    """Get or create metrics in the given registry.

    Args:
        registry: CollectorRegistry to register metrics with
        namespace: Namespace prefix for metric names

    Returns:
        Dict of metric objects
    """
    metrics = {}

    # Sensor state + value pairs
    for sensor_type in ["temperature", "fan", "voltage", "power"]:
        metrics[f"{sensor_type}_state"] = Gauge(
            f"{namespace}_{sensor_type}_state",
            f"{sensor_type.capitalize()} sensor state (0=nominal, 1=warning, 2=critical, NaN=N/A)",
            LABELS,
            registry=registry,
        )
        if sensor_type == "temperature":
            metrics["temperature_celsius"] = Gauge(
                f"{namespace}_{sensor_type}_celsius",
                f"{sensor_type.capitalize()} sensor value in degrees Celsius",
                LABELS,
                registry=registry,
            )
        elif sensor_type == "fan":
            metrics[f"{sensor_type}_speed_rpm"] = Gauge(
                f"{namespace}_{sensor_type}_speed_rpm",
                f"{sensor_type.capitalize()} sensor value in RPM",
                LABELS,
                registry=registry,
            )
        elif sensor_type == "voltage":
            metrics[f"{sensor_type}_volts"] = Gauge(
                f"{namespace}_{sensor_type}_volts",
                f"{sensor_type.capitalize()} sensor value in Volts",
                LABELS,
                registry=registry,
            )
        elif sensor_type == "power":
            metrics[f"{sensor_type}_watts"] = Gauge(
                f"{namespace}_{sensor_type}_watts",
                f"{sensor_type.capitalize()} sensor value in Watts",
                LABELS,
                registry=registry,
            )

    # Generic sensor state + value (for unknown unit types)
    metrics["sensor_state"] = Gauge(
        f"{namespace}_sensor_state",
        "Generic sensor state (0=nominal, 1=warning, 2=critical, NaN=N/A)",
        LABELS + ["sensor_type"],
        registry=registry,
    )
    metrics["sensor_value"] = Gauge(
        f"{namespace}_sensor_value",
        "Generic sensor value",
        LABELS + ["sensor_type", "unit"],
        registry=registry,
    )

    # Discrete/binary sensors
    metrics["discrete_state"] = Gauge(
        f"{namespace}_discrete_state",
        "Discrete sensor state (1=asserted, 0=deasserted)",
        LABELS + ["state_name", "sensor_type"],
        registry=registry,
    )

    # DCMI power consumption
    metrics["dcmi_power_consumption_current_watts"] = Gauge(
        f"{namespace}_dcmi_power_consumption_current_watts",
        "DCMI current power consumption in Watts",
        [],
        registry=registry,
    )
    metrics["dcmi_power_consumption_average_watts"] = Gauge(
        f"{namespace}_dcmi_power_consumption_average_watts",
        "DCMI rolling average power consumption in Watts",
        ["interval_seconds"],
        registry=registry,
    )

    # Chassis power state
    metrics["chassis_power_state"] = Gauge(
        f"{namespace}_chassis_power_state",
        "Chassis power state (1=on, 0=off)",
        [],
        registry=registry,
    )

    # BMC info (constant metric with labels)
    metrics["bmc_info"] = Gauge(
        f"{namespace}_bmc_info",
        "BMC device info (1=valid)",
        ["firmware_revision", "manufacturer_id", "system_firmware_version"],
        registry=registry,
    )

    return metrics


# State mapping (from ipmi_exporter)
# 0 = nominal, 1 = warning, 2 = critical, NaN = N/A
STATE_MAP = {
    "nominal": 0,
    "warning": 1,
    "critical": 2,
    "n/a": float("nan"),
    "na": float("nan"),
}

# Unit mapping to (metric_prefix, metric_suffix)
UNIT_TO_METRIC = {
    "c": ("temperature", "celsius"),
    "degrees c": ("temperature", "celsius"),
    "degrees celsius": ("temperature", "celsius"),
    "v": ("voltage", "volts"),
    "volts": ("voltage", "volts"),
    "a": ("current", "amperes"),
    "amps": ("current", "amperes"),
    "amperes": ("current", "amperes"),
    "w": ("power", "watts"),
    "watts": ("power", "watts"),
    "rpm": ("fan", "speed_rpm"),
    "percent": ("percent", "ratio"),
    "%": ("percent", "ratio"),
}


def main(args):
    """Main entry point."""
    try:
        # Check for IPMI device availability
        if not any(os.path.exists(dev) for dev in IPMI_DEVICES):
            logger.debug("No IPMI device found. Exiting gracefully.")
            return 0

        # Create a fresh registry for each run
        registry = CollectorRegistry()
        metrics = get_metrics(registry, args.namespace)

        # Collect from each tool in parallel
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    collect_ipmi_sensors,
                    args.ipmi_sensors_path,
                    metrics,
                    args.namespace,
                    registry,
                ),
                executor.submit(
                    collect_dcmi_metrics,
                    args.ipmi_dcmi_path,
                    metrics,
                    args.namespace,
                    registry,
                ),
                executor.submit(
                    collect_chassis_metrics,
                    args.ipmi_chassis_path,
                    metrics,
                    args.namespace,
                    registry,
                ),
                executor.submit(
                    collect_bmc_info_metrics,
                    args.bmc_info_path,
                    metrics,
                    args.namespace,
                    registry,
                ),
            ]
            # Wait for all futures to complete
            for future in futures:
                future.result()

        print(generate_latest(registry).decode(), end="")
        return 0

    except Exception as e:  # noqa: BLE001
        logger.error("Fatal error: %s", e)
        return 1


def run_command(cmd):
    """Run a command and return stdout.

    Args:
        cmd: List of command arguments

    Returns:
        Decoded stdout output

    Raises:
        RuntimeError: If command fails
    """
    try:
        proc = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            check=True,
            timeout=60,
        )
        return proc.stdout.decode(errors="replace")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Command {' '.join(cmd)} timed out after 60 seconds")
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode(errors="replace")
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with exit code {e.returncode}: {stderr_msg}"
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Failed to run command {' '.join(cmd)}: {e}")


def parse_sensor_id(sensor_name, record_id):
    """Parse sensor ID from sensor data.

    Args:
        sensor_name: Sensor name
        record_id: Record ID from ipmi-sensors

    Returns:
        Sensor ID string
    """
    # Use record_id as primary ID if available
    if record_id and record_id.isdigit():
        return record_id

    # Try to extract numeric ID from sensor name (e.g., "CPU1" -> "1", "DIMMA1" -> "1")
    match = re.search(r"(\d+)", sensor_name)
    if match:
        return match.group(1)

    # Fallback: hash the name
    return str(hash(sensor_name) % 100000)


def collect_ipmi_sensors(ipmi_sensors_cmd, metrics, namespace, registry):
    """Collect sensor data from ipmi-sensors.

    Args:
        ipmi_sensors_cmd: Path to ipmi-sensors binary
        metrics: Dict of metric objects
        namespace: Metric namespace
        registry: CollectorRegistry
    """
    try:
        output = run_command(
            [
                ipmi_sensors_cmd,
                "--quiet-cache",
                "--comma-separated-output",
                "--no-header-output",
                "--entity-sensor-names",
                "--output-sensor-state",
                "--output-sensor-thresholds",
                "--non-abbreviated-units",
            ]
        )

        sensors = parse_sensors(output)

        for sensor in sensors:
            try:
                handle_sensor(sensor, metrics, namespace, registry)
            except (ValueError, KeyError) as e:
                logger.warning(
                    "Failed to process sensor %s (%s): %s",
                    sensor.get("name", "unknown"),
                    sensor.get("type", "unknown"),
                    e,
                )

    except RuntimeError as e:
        logger.error("Failed to collect ipmi-sensors data: %s", e)


def parse_sensors(output):
    """Parse ipmi-sensors CSV output into a list of sensor dicts.

    CSV columns: Record ID, Sensor Name, Sensor Type, State, Reading, Units,
                 Lower NR, Lower C, Lower NC, Upper NC, Upper C, Upper NR, Sensor Event.
    """
    sensors = []
    reader = csv.reader(output.splitlines())
    for row in reader:
        if len(row) < 6:
            continue
        record_id, sensor_name, sensor_type, state, reading, units = row[:6]
        sensor_event = row[12] if len(row) > 12 else ""
        if not sensor_name:
            continue
        # Discrete/non-numeric sensors: N/A reading and N/A units, but have event
        if reading.lower() == "n/a" and units.lower() == "n/a":
            if sensor_event:
                # This is a discrete sensor with state event
                sensors.append(
                    {
                        "id": record_id,
                        "name": sensor_name,
                        "type": sensor_type,
                        "state": state,
                        "value": reading,
                        "unit": "discrete",
                        "event": sensor_event,
                    }
                )
            continue
        # Skip other N/A readings (sensors with no numeric value)
        if reading.lower() == "n/a":
            continue
        sensors.append(
            {
                "id": record_id,
                "name": sensor_name,
                "type": sensor_type,
                "state": state,
                "value": reading,
                "unit": units.lower(),
            }
        )
    return sensors


def handle_sensor(sensor, metrics, namespace, registry):
    """Translate a parsed sensor into Prometheus metrics."""
    sensor_id = parse_sensor_id(sensor["name"], sensor.get("id", ""))
    sensor_name = sensor["name"]
    sensor_type = sensor["type"]

    unit = sensor["unit"]
    state = STATE_MAP.get(sensor["state"].lower(), float("nan"))

    if unit == "discrete":
        # Discrete sensor - extract event/state
        event = sensor.get("event", "")
        state_name = event or sensor["state"] or "none"
        state_names = state_name.strip("'\"").split("' '")
        for state in state_names:
            state = state.lower()
            # discrete_state has labels: id, name, type, state_name, sensor_type
            metrics["discrete_state"].labels(
                sensor_id, sensor_name, sensor_type, state, sensor_type
            ).set(1)
    elif unit in UNIT_TO_METRIC:
        # Known unit type - use specific metric
        metric_prefix, metric_suffix = UNIT_TO_METRIC[unit]
        try:
            value = float(sensor["value"])
            # The metric name is metric_prefix + metric_suffix
            metric_name = f"{metric_prefix}_{metric_suffix}"
            if metric_name in metrics:
                metrics[metric_name].labels(sensor_id, sensor_name, sensor_type).set(value)
            # Also set the specific state metric (e.g., fan_state, voltage_state)
            state_metric_name = f"{metric_prefix}_state"
            if state_metric_name in metrics:
                metrics[state_metric_name].labels(sensor_id, sensor_name, sensor_type).set(state)
        except (ValueError, TypeError):
            logger.warning("Invalid value '%s' for sensor %s", sensor["value"], sensor_name)
            return
    else:
        # Unknown unit - use generic sensor_value
        unit_clean = re.sub(r"[^a-z0-9_]", "_", unit)[:20]
        try:
            value = float(sensor["value"])
            # sensor_value has labels: id, name, type, sensor_type, unit
            metrics["sensor_value"].labels(
                sensor_id, sensor_name, sensor_type, sensor_type, unit_clean
            ).set(value)
        except (ValueError, TypeError):
            logger.warning("Invalid value '%s' for sensor %s", sensor["value"], sensor_name)
            return

    # Always set sensor_state for all sensors
    metrics["sensor_state"].labels(sensor_id, sensor_name, sensor_type, sensor_type).set(state)


def collect_dcmi_metrics(ipmi_dcmi_cmd, metrics, namespace, registry):
    """Collect DCMI metrics from ipmi-dcmi.

    Args:
        ipmi_dcmi_cmd: Path to ipmi-dcmi binary
        metrics: Dict of metric objects
        namespace: Metric namespace
        registry: CollectorRegistry
    """
    try:
        # Get enhanced system power statistics
        output = run_command([ipmi_dcmi_cmd, "--get-enhanced-system-power-statistics"])

        # Parse power readings
        current_power = None
        interval_power = {}
        current_interval = None

        for line in output.splitlines():
            # Track the interval
            match = re.search(r"Time Period\s+(\d+)\s+(Seconds|Milliseconds)", line)
            if match:
                val = int(match.group(1))
                unit = match.group(2).lower()
                if unit == "milliseconds":
                    val = val / 1000.0
                current_interval = int(val)
                continue

            # Parse current power
            match = re.search(r"Current Power\s*:\s*(\d+(?:\.\d+)?)\s*W", line, re.IGNORECASE)
            if match and current_interval is not None:
                current_power = float(match.group(1))
                interval_power[current_interval] = current_power
                continue

            # Parse average power
            match = re.search(r"Average Power\s*:\s*(\d+(?:\.\d+)?)\s*W", line, re.IGNORECASE)
            if match and current_interval is not None:
                avg_power = float(match.group(1))
                interval_power[current_interval] = avg_power

        # Set current power
        if current_power is not None:
            metrics["dcmi_power_consumption_current_watts"].set(current_power)

        # Set rolling average power for each interval
        for interval, power in interval_power.items():
            metrics["dcmi_power_consumption_average_watts"].labels(str(int(interval))).set(power)

    except RuntimeError as e:
        logger.debug("Failed to collect DCMI metrics: %s", e)


def collect_chassis_metrics(ipmi_chassis_cmd, metrics, namespace, registry):
    """Collect chassis status metrics from ipmi-chassis.

    Args:
        ipmi_chassis_cmd: Path to ipmi-chassis binary
        metrics: Dict of metric objects
        namespace: Metric namespace
        registry: CollectorRegistry
    """
    try:
        output = run_command([ipmi_chassis_cmd, "--get-chassis-status"])

        power_on = False

        for line in output.splitlines():
            line = line.strip()
            if "System Power" in line and ":" in line:
                value = line.split(":")[1].strip().lower()
                power_on = value == "on"

        metrics["chassis_power_state"].set(1 if power_on else 0)

    except RuntimeError as e:
        logger.debug("Failed to collect chassis metrics: %s", e)


def collect_bmc_info_metrics(bmc_info_cmd, metrics, namespace, registry):
    """Collect BMC device and channel info metrics from bmc-info.

    Args:
        bmc_info_cmd: Path to bmc-info binary
        metrics: Dict of metric objects
        namespace: Metric namespace
        registry: CollectorRegistry
    """
    try:
        output = run_command([bmc_info_cmd, "--always-prefix"])

        # Strip localhost: prefix and parse
        device_info = {}
        for line in output.splitlines():
            line = line.strip()
            line = line.removeprefix("localhost: ")
            if ":" in line:
                key, value = line.split(":", 1)
                device_info[key.strip()] = value.strip()

        # Get BMC info
        firmware_revision = device_info.get("Firmware Revision", "N/A")
        manufacturer_id = device_info.get("Manufacturer ID", "N/A")
        system_firmware = device_info.get("System Firmware Version", "N/A")

        # BMC info metric (constant 1 with labels)
        metrics["bmc_info"].labels(firmware_revision, manufacturer_id, system_firmware).set(1)

    except RuntimeError as e:
        logger.debug("Failed to collect BMC info metrics: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--ipmi-sensors-path",
        default="/usr/sbin/ipmi-sensors",
        help="path to ipmi-sensors binary",
    )
    parser.add_argument(
        "--ipmi-dcmi-path",
        default="/usr/sbin/ipmi-dcmi",
        help="path to ipmi-dcmi binary",
    )
    parser.add_argument(
        "--ipmi-chassis-path",
        default="/usr/sbin/ipmi-chassis",
        help="path to ipmi-chassis binary",
    )
    parser.add_argument(
        "--bmc-info-path",
        default="/usr/sbin/bmc-info",
        help="path to bmc-info binary",
    )
    parser.add_argument(
        "--namespace",
        default=namespace_default,
        help="Prometheus metric namespace prefix",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    args = parser.parse_args()
    sys.exit(main(args))
