#!/usr/bin/env python3
"""
Script to count the number of lun devices associated with device-mapper
slaves and expose a summary as Prometheus metrics.
"""

import os
import sys
import argparse
from prometheus_client import CollectorRegistry, Gauge, write_to_textfile

sysfs = "/sys/devices/"

def main(arguments):

    parser = argparse.ArgumentParser(description="detect lun devices associated with DM",
                                 epilog=__doc__)
    parser.add_argument("-f", "--prom-file",
                        default='/var/lib/prometheus/node-exporter/dmslave_info.prom',
                        help="Write prometheus metrics to specified file (default: %(default)s)")

    args = parser.parse_args(arguments)

    registry = CollectorRegistry()

    gauge_dm_info = Gauge('node_dmslave_info',
                          'Devicemapper slave information',
                          ['dm_device', 'lun_name'],
                          registry=registry)

    dm = [x for x in os.listdir(sysfs+'virtual/block/') if x.startswith('dm')]
    for dx in dm:
        dm_sd =  os.listdir(sysfs+'virtual/block/'+dx+'/slaves/')
        lun_count = len(dm_sd)
        if lun_count:
            for i in range(lun_count):
                gauge_dm_info.labels(dx, dm_sd[i]).set(lun_count)
        else:
                gauge_dm_info.labels(dx, " ").set(0)

    write_to_textfile(str(args.prom_file), registry)

if __name__ == "__main__":
    main(sys.argv[1:]) # pragma: no cover

