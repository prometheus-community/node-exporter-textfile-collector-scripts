#!/usr/bin/env python3
#
# Description: Gather metrics from Chrony NTP.
#

import math
import subprocess
import sys

from prometheus_client import CollectorRegistry, Gauge, generate_latest, Info


SOURCE_STATUS_LABELS = {
    "*": "synchronized (system peer)",
    "+": "synchronized",
    "?": "unreachable",
    "x": "Falseticker",
    "-": "reference clock",
}

SOURCE_MODE_LABELS = {
    '^': "server",
    '=': "peer",
    "#": "reference clock",
}


def chronyc(*args, check=True):
    """Chrony client wrapper

    Returns:
       (str) Data piped to stdout by the chrony subprocess.
    """
    return subprocess.run(
        ['chronyc', *args], stdout=subprocess.PIPE, check=check
    ).stdout.decode('utf-8').rstrip()


def chronyc_tracking():
    return chronyc('-c', 'tracking').split(',')


def chronyc_sources():
    lines = chronyc('-c', 'sources').split('\n')

    return [line.split(',') for line in lines]


def chronyc_sourcestats():
    lines = chronyc('-c', 'sourcestats').split('\n')

    return [line.split(',') for line in lines]


def tracking_metrics(registry):
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


def sources_metrics(registry):
    chrony_sources = chronyc_sources()

    peer = Info('chrony_source_peer',
                'Peer information',
                registry=registry)
    poll = Gauge('chrony_source_poll_rate_seconds',
                 'The rate at which the source is being polled',
                 ['ref_host'],
                 registry=registry)
    reach = Gauge('chrony_source_reach_register',
                  'The source reachability register',
                  ['ref_host'],
                  registry=registry)
    received = Gauge('chrony_source_last_received_seconds',
                     'Number of seconds ago the last sample was received from the source',
                     ['ref_host'],
                     registry=registry)
    original = Gauge('chrony_source_original_offset_seconds',
                     'The adjusted offset between ' +
                     'the local clock and the source',
                     ['ref_host'],
                     registry=registry)
    measured = Gauge('chrony_source_measured_offset_seconds',
                     'The actual measured offset between ' +
                     'the local clock and the source',
                     ['ref_host'],
                     registry=registry)
    margin = Gauge('chrony_source_offset_margin_seconds',
                   'The error margin in the offset measurement between ' +
                   'the local clock and the source',
                   ['ref_host'],
                   registry=registry)

    for source in chrony_sources:
        if len(source) != 10:
            print("ERROR: Unable to parse chronyc sources CSV", file=sys.stderr)
            sys.exit(1)

        mode = source[0]
        status = source[1]
        ref_host = source[2]
        stratum = source[3]
        rate = float(source[4])

        if status not in SOURCE_STATUS_LABELS:
            print("ERROR: Invalid chrony source status '%s'" % status, file=sys.stderr)
            sys.exit(1)

        if mode not in SOURCE_MODE_LABELS:
            print("ERROR: Invalid chrony source mode '%s'" % mode, file=sys.stderr)
            sys.exit(1)

        peer.info({
            'ref_host': ref_host,
            'stratum': stratum,
            'mode': SOURCE_MODE_LABELS[mode],
            'status': SOURCE_STATUS_LABELS[status],
        })
        poll.labels(ref_host).set(math.pow(2.0, rate))
        reach.labels(ref_host).set(source[5])
        received.labels(ref_host).set(source[6])
        original.labels(ref_host).set(source[7])
        measured.labels(ref_host).set(source[8])
        margin.labels(ref_host).set(source[9])


def sourcestats_metrics(registry):
    chrony_sourcestats = chronyc_sourcestats()

    samples = Gauge('chrony_source_sample_points',
                    'The number of sample points currently being retained for the server',
                    ['ref_host'],
                    registry=registry)
    residuals = Gauge('chrony_source_residual_runs',
                      'The number of runs of residuals having the same ' +
                      'sign following the last regression',
                      ['ref_host'],
                      registry=registry)
    span = Gauge('chrony_source_sample_interval_span_seconds',
                 'The interval between the oldest and newest samples',
                 ['ref_host'],
                 registry=registry)
    frequency = Gauge('chrony_source_frequency_ppm',
                      'The estimated residual frequency for the server',
                      ['ref_host'],
                      registry=registry)
    skew = Gauge('chrony_source_frequency_skew_ppm',
                 'The estimated error bounds on the residual frequency estimation',
                 ['ref_host'],
                 registry=registry)
    stddev = Gauge('chrony_source_std_dev_seconds',
                   'The estimated sample standard deviation.',
                   ['ref_host'],
                   registry=registry)

    for source in chrony_sourcestats:
        if len(source) != 8:
            print("ERROR: Unable to parse chronyc sourcestats CSV", file=sys.stderr)
            sys.exit(1)

        ref_host = source[0]

        samples.labels(ref_host).set(source[1])
        residuals.labels(ref_host).set(source[2])
        span.labels(ref_host).set(source[3])
        frequency.labels(ref_host).set(source[4])
        skew.labels(ref_host).set(source[5])
        stddev.labels(ref_host).set(source[6])


def main():
    registry = CollectorRegistry()

    tracking_metrics(registry)
    sources_metrics(registry)
    sourcestats_metrics(registry)
    print(generate_latest(registry).decode("utf-8"), end='')


if __name__ == "__main__":
    main()
