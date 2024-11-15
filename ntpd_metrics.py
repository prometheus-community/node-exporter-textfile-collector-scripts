#!/usr/bin/env python3
#
# Description: Extract NTPd metrics from ntpq -np.
# Author: Ben Kochie <superq@gmail.com>

import re
import subprocess
import sys
from prometheus_client import CollectorRegistry, Gauge, generate_latest

# NTP peers status, with no DNS lookups.
ntpq_cmd = ['ntpq', '-np', '-W', '255']
ntpq_rv_cmd = ['ntpq', '-c', 'rv 0 offset,sys_jitter,rootdisp,rootdelay']

# Regex to match all of the fields in the output of ntpq -np
metrics_fields = [
    r'^(?P<status>.)(?P<remote>[\w\.:]+)',
    r'(?P<refid>[\w\.:]+)',
    r'(?P<stratum>\d+)',
    r'(?P<type>\w)',
    r'(?P<when>\d+)',
    r'(?P<poll>\d+)',
    r'(?P<reach>\d+)',
    r'(?P<delay>\d+\.\d+)',
    r'(?P<offset>-?\d+\.\d+)',
    r'(?P<jitter>\d+\.\d+)',
]
metrics_re = r'\s+'.join(metrics_fields)

# Remote types
# http://support.ntp.org/bin/view/Support/TroubleshootingNTP
remote_types = {
    'l': 'local',
    'u': 'unicast',
    'm': 'multicast',
    'b': 'broadcast',
    '-': 'netaddr',
}

# Status codes:
# http://www.eecis.udel.edu/~mills/ntp/html/decode.html#peer
status_types = {
    ' ': 0,
    'x': 1,
    '.': 2,
    '-': 3,
    '+': 4,
    '#': 5,
    '*': 6,
    'o': 7,
}


# Run the ntpq command.
def get_output(command):
    try:
        output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
    return output.decode()


# Parse raw ntpq lines.
def parse_line(line):
    if re.match(r'\s+remote\s+refid', line):
        return None
    if re.match(r'=+', line):
        return None
    if re.match(r'.+\.(LOCL|POOL)\.', line):
        return None
    if re.match(r'^$', line):
        return None
    return re.match(metrics_re, line)


# Main function
def main(argv):
    ntpq = get_output(ntpq_cmd)

    namespace = 'ntpd'
    registry = CollectorRegistry()
    peer_status = Gauge('peer_status', 'NTPd metric for peer_status',
                        ['remote', 'reference', 'stratum', 'type'],
                        namespace=namespace, registry=registry)
    delay_ms = Gauge('delay_milliseconds', 'NTPd metric for delay_milliseconds',
                     ['remote', 'reference'], namespace=namespace, registry=registry)
    offset_ms = Gauge('offset_milliseconds', 'NTPd metric for offset_milliseconds',
                      ['remote', 'reference'], namespace=namespace, registry=registry)
    jitter_ms = Gauge('jitter_milliseconds', 'NTPd metric for jitter_milliseconds',
                      ['remote', 'reference'], namespace=namespace, registry=registry)

    for line in ntpq.split('\n'):
        metric_match = parse_line(line)
        if metric_match is None:
            continue
        remote = metric_match.group('remote')
        refid = metric_match.group('refid')
        stratum = metric_match.group('stratum')
        remote_type = remote_types[metric_match.group('type')]

        peer_status.labels(remote, refid, stratum, remote_type).set(
            status_types[metric_match.group('status')]
        )
        delay_ms.labels(remote, refid).set(metric_match.group('delay'))
        offset_ms.labels(remote, refid).set(metric_match.group('offset'))
        jitter_ms.labels(remote, refid).set(metric_match.group('jitter'))

    ntpq_rv = get_output(ntpq_rv_cmd)
    for metric in ntpq_rv.split(','):
        metric_name, metric_value = metric.strip().split('=')
        g = Gauge(metric_name, 'NTPd metric for {}'.format(metric_name), [],
                  namespace=namespace, registry=registry)
        g.set(metric_value)

    print(generate_latest(registry).decode(), end='')


# Go go go!
if __name__ == "__main__":
    main(sys.argv[1:])
