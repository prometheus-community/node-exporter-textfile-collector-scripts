#!/usr/bin/env python3
#
# Description: Gather metrics from Chrony NTP.
#

import subprocess
import sys

from prometheus_client import CollectorRegistry, Gauge, generate_latest


def chronyc(*args, check=True):
    """Chrony client wrapper

    Returns:
       (str) Data piped to stdout by the chrony subprocess.
    """
    return subprocess.run(
        ['chronyc', *args], stdout=subprocess.PIPE, check=check
    ).stdout.decode('utf-8')


def chronyc_tracking():
    return chronyc('-c', 'tracking').split(',')


def main():
    registry = CollectorRegistry()
    chrony_tracking = chronyc_tracking()

    if len(chrony_tracking) != 14:
        print("ERROR: Unable to parse chronyc tracking CSV", file=sys.stderr)
        sys.exit(1)

    g = Gauge('chrony_tracking_reference_info',
              'The stratum of the current preferred source',
              ['ref_id', 'ref_host'],
              registry=registry)
    g.labels(chrony_tracking[0], chrony_tracking[1]).set(1)

    g = Gauge('chrony_tracking_stratum',
              'The stratum of the current preferred source',
              registry=registry)
    g.set(chrony_tracking[2])

    g = Gauge('chrony_tracking_system_offset_seconds',
              'The current estimated drift of system time from true time',
              registry=registry)
    g.set(chrony_tracking[4])

    g = Gauge('chrony_tracking_last_offset_seconds',
              'The estimated local offset on the last clock update.',
              registry=registry)
    g.set(chrony_tracking[5])

    g = Gauge('chrony_tracking_root_dispersion_seconds',
              'The absolute bound on the computer’s clock accuracy',
              registry=registry)
    g.set(chrony_tracking[5])

    print(generate_latest(registry).decode("utf-8"), end='')


if __name__ == "__main__":
    main()
