#!/usr/bin/env python3
#
# Description: Extract NTPd metrics from ntpq -np.
# Author: Ben Kochie <superq@gmail.com>

import re
import subprocess
import sys

# NTP peers status, with no DNS lookups.
ntpq_cmd = ['ntpq', '-np']
ntpq_rv_cmd = ['ntpq', '-c', 'rv 0 offset,sys_jitter,rootdisp,rootdelay']

# Regex to match all of the fields in the output of ntpq -np
metrics_fields = [
    r'^(?P<status>.)(?P<remote>[\w\.]+)',
    r'(?P<refid>[\w\.]+)',
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


# Print metrics in Prometheus format.
def print_prometheus(metric, values):
    print("# HELP ntpd_%s NTPd metric for %s" % (metric, metric))
    print("# TYPE ntpd_%s gauge" % (metric))
    for labels in values:
        if labels is None:
            print("ntpd_%s %f" % (metric, values[labels]))
        else:
            print("ntpd_%s{%s} %f" % (metric, labels, values[labels]))


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
    peer_status_metrics = {}
    delay_metrics = {}
    offset_metrics = {}
    jitter_metrics = {}
    for line in ntpq.split('\n'):
        metric_match = parse_line(line)
        if metric_match is None:
            continue
        remote = metric_match.group('remote')
        refid = metric_match.group('refid')
        stratum = metric_match.group('stratum')
        remote_type = remote_types[metric_match.group('type')]
        common_labels = "remote=\"%s\",reference=\"%s\"" % (remote, refid)
        peer_labels = "%s,stratum=\"%s\",type=\"%s\"" % (common_labels, stratum, remote_type)

        peer_status_metrics[peer_labels] = float(status_types[metric_match.group('status')])
        delay_metrics[common_labels] = float(metric_match.group('delay'))
        offset_metrics[common_labels] = float(metric_match.group('offset'))
        jitter_metrics[common_labels] = float(metric_match.group('jitter'))

    print_prometheus('peer_status', peer_status_metrics)
    print_prometheus('delay_milliseconds', delay_metrics)
    print_prometheus('offset_milliseconds', offset_metrics)
    print_prometheus('jitter_milliseconds', jitter_metrics)

    ntpq_rv = get_output(ntpq_rv_cmd)
    for metric in ntpq_rv.split(','):
        metric_name, metric_value = metric.strip().split('=')
        print_prometheus(metric_name, {None: float(metric_value)})


# Go go go!
if __name__ == "__main__":
    main(sys.argv[1:])
