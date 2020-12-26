#!/usr/bin/env python
#
# Prometheus exporter for Areca controllers
#
# Tested with: ARC-188x
#
# (c) 2020, Nuno Tavares <n.tavares@portavita.eu>
#

# NOTE: other info that is maybe worth parsing in the future (such as array status)
#
# CLI> vsf info
#   # Name             Raid Name       Level   Capacity Ch/Id/Lun  State
# ===============================================================================
#   1 OS               OS              Raid1+0 2000.0GB 00/00/00   Normal
#   2 EBS-Volumeset    EBS             Raid5   10000.0GB 00/00/01   Normal
#   3 S3-WALRUS        S3-Walrus       Raid5   10000.0GB 00/00/02   Normal
# ===============================================================================
# GuiErrMsg<0x00>: Success.
#
# CLI> rsf info
#  #  Name             Disks TotalCap  FreeCap MinDiskCap         State
# ===============================================================================
#  1  OS                   2 4000.0GB    0.0GB   2000.0GB         Normal
#  2  EBS                  6 12000.0GB    0.0GB   2000.0GB         Normal
#  3  S3-Walrus            6 12000.0GB    0.0GB   2000.0GB         Normal
# ===============================================================================
# GuiErrMsg<0x00>: Success.





"""Prometheus exporter for Areca RAID controller that support the cli64."""

import os
import re
import sys
from optparse import OptionParser
import copy


try:
    from subprocess import Popen, PIPE, STDOUT
except ImportError:
    # Perhaps you are using a version of python older than 2.4?
    exit_error("CLI Parser error: Failed to import subprocess module.")

__version__ = '0.1.0'

METRICS = {}
METRIC_PREFIX = 'arc_cli'

def exit_error(msg):
    print(METRIC_PREFIX + "_cli_error{message=\"" + str(msg) + "\"}\t1")
    sys.exit(1)

def exit_clean():
    global METRICS
    for mk, mv in METRICS.items():
        print(METRIC_PREFIX + '_' + mk + "\t" + str(mv))
    sys.exit(0)

def add_metric(metric, labels, value):
    global METRICS
    labelstrs = []
    for lk,lv in labels.items():
        labelstrs += [ lk + '="' + str(lv) + '"' ]
    labelstr = ','.join(labelstrs)
    METRICS[metric + '{' + labelstr + '}'] = str(value)


if os.geteuid() != 0:
    exit_error("You must be root to run this plugin")

BIN = None

DRIVE_MEMBERSHIP = {}

def _set_cli_binary():
    """ set the path to the twcli binary"""
    global BIN
    BIN = '/usr/sbin/cli64'

def run(cmd, stripOutput=True):
    """runs a system command and returns stripped output"""
    if not cmd:
        exit_error("internal python error - no cmd supplied for %s utility" % BIN)

    #print('debug: run() called for: %s' % cmd)
    try:
        process = Popen([BIN, cmd], stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    except OSError as error:
        error = str(error)
        if error == "No such file or directory":
            exit_error("Cannot find %s utility '%s'" % (BIN, BIN))
        else:
            exit_error("error trying to run %s utility - %s" % (BIN, error))

    if process.poll():
        exit_error("%s utility process ended prematurely" % BIN)

    try:
        stdout, stderr = process.communicate("") #"exit\n")
    except OSError as error:
        exit_error("unable to communicate with %s utility - %s" % (BIN, error))


    if not stdout:
        exit_error("No output from %s utility" % BIN)

    #print('stdout: ' + str(stdout))

    output = str(stdout).split("\n")
    # strip command prompt, since we're running an interactive CLI shell
    output[0] = re.sub(r'CLI> ', '', output[0])

    if output[-1] == "Error: Please check the (arcmsr & sg) drivers are installed properly.":
        exit_error("No ARC controllers were found on this machine")

    # For some reason, exiting the CLI with 'exit' gives a return code of 255 (?)
    if process.returncode not in [0,255]:
        stderr = str(stdout).replace("\n"," ")
        exit_error("cli utility returned an exit code of %s - %s" % (process.returncode, stderr))

    if stripOutput:
        return output[2:-2]

    return output


def collect_volume_sets(controller, verbosity):
    VSF_DETAILS = {
        'Volume Set Name':     { 'label': 'name',            'parser': None },
        'Raid Set Name':       { 'label': 'rset',            'parser': None },
        'Volume Capacity':     { 'label': 'capacity',        'parser': _parse_discard_units },
        'Raid Level':          { 'label': 'rlevel',          'parser': None },
        'Stripe Size':         { 'label': 'stripe',          'parser': None },
        'Volume State':        { 'metric': 'volume_state',   'parser': _parse_state },
    }
    volume_lines = run('vsf info')
    for volume_line in volume_lines:
        volume_line = volume_line.split()
        if len(volume_line)<=0:
            continue
        volume = volume_line[0]
        if len(volume_line)<=4:
            continue
        collect_details('vsf info vol=%s' % volume, VSF_DETAILS, 'volumeset_info', { "controller": controller, 'vol': volume }, verbosity)


def collect_raid_sets(controller, verbosity):
    global DRIVE_MEMBERSHIP
    RSF_DETAILS = {
        'Raid Set Name':        { 'label': 'name',           'parser': None },
        'Raid Set State':       { 'metric': 'raidset_state', 'parser': _parse_state },
        'Member Disk Channels': { 'return': '',              'parser': _parse_raidset_members },
    }
    rset_lines = run('rsf info')
    for rset_line in rset_lines:
        rset_line = rset_line.split()
        if len(rset_line)<=0:
            continue
        rset = rset_line[0]
        if len(rset_line)<=4:
            continue
        rset_members = collect_details('rsf info raid=%s' % rset, RSF_DETAILS, 'raidset_info', { "controller": controller, 'rset': rset }, verbosity)
        DRIVE_MEMBERSHIP[rset] = rset_members
    if verbosity >= 1:
        print('[d] Will be using DRIVE_MEMBERSHIP = %s' % DRIVE_MEMBERSHIP)

def _parse_discard_units(val):
    result = re.split('(\d+)(.*)$', val)
    return result[1]

def _parse_state(val):
    if val in ['NORMAL', 'Normal']:
        return 1
    return 0

def _parse_raidset_members(val):
    return val.split('.')

"""Generic function to parse key = value lists, based on a detailsMap which
   selects the fields to parse. injectedLabels is just baseline labels to be included.
   Note that the map may list both labels to append to a catchall 'metric', or individual
   metrics, whose name overrides 'metric' and will contain injectedLabels."""

def collect_details(cmd, detailsMap, metric, injectedLabels, verbosity):
    lines = run(cmd, False)
    labels = copy.copy(injectedLabels)
    ret_value = None
    for line in lines:
        #print('collect_details: parsing: %s' % line)
        fields = line.split(':', 1)
        if len(fields) <= 1:
            continue
        k = fields[0].strip()
        v = fields[1].strip()
        if k in detailsMap.keys():
            if detailsMap[k]['parser']:
                v = detailsMap[k]['parser'](v)
            # if this field is meant for a separate metric, do it
            if 'metric' in detailsMap[k]:
                add_metric(detailsMap[k]['metric'], injectedLabels, v)
            elif 'return' in detailsMap[k]:
                ret_value = v
            else:
                labels[detailsMap[k]['label']] = v
    add_metric(metric, labels, 1)
    return ret_value

def get_controller():
    # Hardcoding controller. I /think/ you get a list of controllers when
    # running command 'main':
    #  S  #   Name       Type             Interface
    # ==================================================
    # [*] 1   ARC-1880   Raid Controller  PCI
    # ==================================================
    # ... but I won't bother that much. Maybe someone else can add this.
    controller=1
    run('set curctrl=%d' % controller)
    return controller



def collect_controller(controller, verbosity):
    CTRL_DETAILS = {
        'Firmware Version':     { 'label': 'firmware',    'parser': None },
        'BOOT ROM Version':     { 'label': 'boot_rom',    'parser': None },
        'Serial Number':        { 'label': 'serial',      'parser': None },
        'Controller Name':      { 'label': 'model',      'parser': None },
    }
    collect_details('sys info', CTRL_DETAILS, 'controller_info', { "controller": controller }, verbosity)
    collect_hw_info(controller, verbosity)

def get_drive_membership(drive_line):
    global DRIVE_MEMBERSHIP
    # if collect_raidsets has not run, then we don't have a cache at all
    if len(DRIVE_MEMBERSHIP.keys())<=0:
        return None
    enc = int(drive_line[1])
    slot = int(drive_line[3])
    cachelabel = 'E{0}S{1}'.format(enc, slot)
    for rset in DRIVE_MEMBERSHIP.keys():
        if cachelabel in DRIVE_MEMBERSHIP[rset]:
            return rset
    return 'GHS'


def collect_drives(controller, verbosity):
    DRIVE_DETAILS = {
        'Device Type':          { 'label': 'type',                'parser': None },
        #'Device Location':      { 'label': 'location',            'parser': None },
        'Model Name':           { 'label': 'model',               'parser': None },
        'Serial Number':        { 'label': 'serial',              'parser': None },
        'Firmware Rev.':        { 'label': 'firmware',            'parser': None },
        'Disk Capacity':        { 'label': 'capacity',            'parser': _parse_discard_units },
        'Media Error Count':    { 'metric': 'disk_media_errors', 'parser': None },
        'Device State':         { 'metric': 'disk_state',        'parser': _parse_state },
        'Timeout Count':        { 'metric': 'disk_timeout_count','parser': None },
        'Device Temperature':   { 'metric': 'disk_temp',          'parser': _parse_discard_units },
    }
    drive_lines = run('disk info')
    for drive_line in drive_lines:
        drive_line = drive_line.split()
        if len(drive_line)<=0:
            continue
        drive = drive_line[0]
        if len(drive_line)<=4:
            continue
        if drive_line[3] in ['N.A.']:
            continue
        if drive_line[2] in ['EXTP'] and drive_line[4] in ['N.A.']:
            continue
        membership = get_drive_membership(drive_line)
        std_labels = { "controller": controller, 'drive': drive}
        if membership:
            std_labels['rset'] = membership
        collect_details('disk info drv=%s' % drive, DRIVE_DETAILS, 'disk_info', std_labels, verbosity)


def collect_hw_info(controller, verbosity):
    HW_DETAILS = {
        'CPU Temperature':      { 'metric': 'cpu_temp',    'parser': _parse_discard_units },
        'Controller Temp.':     { 'metric': 'ctrl_temp',   'parser': _parse_discard_units },
        'Battery Status':       { 'metric': 'bbu_status',  'parser': _parse_discard_units },
    }
    collect_details('hw info', HW_DETAILS, 'hw_info', { "controller": controller }, verbosity)

def main():
    """Parses command line options and calls the function to
    test the arrays/drives"""

    parser = OptionParser()


    parser.add_option( "-a",
                       "--arrays",
                       action="store_true",
                       dest="arrays",
                       help="Test the arrays")

    parser.add_option( "-d",
                       "--drives",
                       action="store_true",
                       dest="drives",
                       help="Test the drives.")

    parser.add_option( "-v",
                       "--verbose",
                       action="count",
                       dest="verbosity",
                       help="Verbose mode. Good for testing plugin.")

    parser.add_option( "-V",
                       "--version",
                       action="store_true",
                       dest="version",
                       help="Print version number and exit")

    parser.add_option( "-I",
                       "--info",
                       action="store_true",
                       dest="incl_info",
                       help="Include hardware info")

    (options, args) = parser.parse_args()

    if args:
        parser.print_help()
        sys.exit(1)

    if options.version:
        print(__version__)
        sys.exit(0)

    if not options.drives and not options.arrays and not options.incl_info:
        print("ERROR: No action requested.\n")
        parser.print_help()
        sys.exit(1)

    _set_cli_binary()

    controller = get_controller()

    try:
        if options.incl_info:
            collect_controller(controller, options.verbosity)

        if options.arrays:
            collect_volume_sets(controller, options.verbosity)
            collect_raid_sets(controller, options.verbosity)

        if options.drives:
            collect_drives(controller, options.verbosity)
    except Exception as e:
        exit_error('Exception: ' + str(e))

    exit_clean()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Caught Control-C...")
        sys.exit(1)
