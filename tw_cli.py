#!/usr/bin/env python
#
# Prometheus exporter for 3ware RAID controllers
#
# Half of it based on "Nagios Plugin for 3ware RAID" from "Hari Sekhon",
# Ref: http://github.com/harisekhon/nagios-plugins
# ... with additions for full info (-I) gathering
#
# (c) 2019, Nuno Tavares <n.tavares@portavita.eu>
#
# You can find the latest version in:
# https://github.com/ntavares/node-exporter-textfile-collector-scripts
#

"""Nagios plugin to test the state of all 3ware raid arrays and/or drives
   on all 3ware controllers on the local machine. Requires the tw_cli program
   written by 3ware, which should be called tw_cli_64 if running on a 64-bit
   system. May be remotely executed via any of the standard remote nagios
   execution mechanisms"""

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
METRIC_PREFIX = 'tw_cli'

def exit_error(msg):
    print METRIC_PREFIX + "_cli_error{message=\"" + str(msg) + "\"}\t1"
    sys.exit(1)

def exit_clean():
    global METRICS
    for mk, mv in METRICS.items():
        print METRIC_PREFIX + '_' + mk + "\t" + str(mv)
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

def _set_twcli_binary():
    """ set the path to the twcli binary"""
    global BIN
    BIN = '/usr/sbin/tw_cli'

def run(cmd, stripOutput=True):
    """runs a system command and returns stripped output"""
    if not cmd:
        exit_error("internal python error - no cmd supplied for 3ware utility")
    try:
        process = Popen(BIN, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    except OSError, error:
        error = str(error)
        if error == "No such file or directory":
            exit_error("Cannot find 3ware utility '%s'" % BIN)
        else:
            exit_error("error trying to run 3ware utility - %s" % error)

    if process.poll():

        exit_error("3ware utility process ended prematurely")

    try:
        stdout, stderr = process.communicate(cmd)
    except OSError, error:
        exit_error("unable to communicate with 3ware utility - %s" % error)


    if not stdout:
        exit_error("No output from 3ware utility")

    output = str(stdout).split("\n")
    # strip command prompt, since we're running an interactive CLI shell
    output[0] = re.sub(r'//.*?> ', '', output[0])

    if output[1] == "No controller found.":
        exit_error("No 3ware controllers were found on this machine")

    if process.returncode != 0:
        stderr = str(stdout).replace("\n"," ")
        exit_error("3ware utility returned an exit code of %s - %s" % (process.returncode, stderr))

    if stripOutput:
        return output[3:-2]

    return output


def test_all(verbosity, warn_true=False):
    """Calls the raid and drive testing functions"""

    test_arrays(verbosity, warn_true)

    test_drives(verbosity, warn_true)


def test_arrays(verbosity, warn_true=False):
    """Tests all the raid arrays on all the 3ware controllers on
    the local machine"""

    lines = run("show")
    #controllers = [ line.split()[0] for line in lines ]
    controllers = [ line.split()[0] for line in lines if line and line[0] == "c" ]

    for controller in controllers:
        unit_lines = run("/%s show unitstatus" % controller)
        if verbosity >= 3:
            for unit_line in unit_lines:
                print unit_line
            print

        for unit_line in unit_lines:
            unit_line = unit_line.split()
            state = unit_line[2]
            unit = int(unit_line[0][1:])
            raid = unit_line[1]
            add_metric('array_info', {"controller": controller[1:], "unit": unit, "state": state, "raid": raid}, 1)

            if state == "OK":
                add_metric('array_status', {"controller": controller[1:], "unit": unit, "state": state}, 1)
                continue
            elif state == "REBUILDING"    or \
                 state == "VERIFY-PAUSED" or \
                 state == "VERIFYING"     or \
                 state == "INITIALIZING":


                if state == "VERIFY-PAUSED" or \
                   state == "VERIFYING"     or \
                   state == "INITIALIZING":
                    percent_complete = unit_line[4]
                else:
                    percent_complete = unit_line[3]

                if warn_true:
                    add_metric('array_status', {"controller": controller[1:], "unit": unit, "state": state, "pct": percent_complete}, 0)
                else:
                    add_metric('array_status', {"controller": controller[1:], "unit": unit, "state": state, "pct": percent_complete}, 1)

            else:
                add_metric('array_status', {"controller": controller[1:], "unit": unit, "state": state}, 0)


def test_drives(verbosity, warn_true=False):
    """Tests all the drives on the all the 3ware raid controllers
    on the local machine"""

    lines = run("show")
    controllers = []
    for line in lines:
        parts = line.split()
        if parts:
            controllers.append(parts[0])

    for controller in controllers:
        drive_lines = run("/%s show drivestatus" % controller)

        if verbosity >= 3:
            for drive_line in drive_lines:
                print drive_line
            print

        for drive_line in drive_lines:
            drive_line = drive_line.split()
            state = drive_line[1]
            drive = drive_line[0]
            if drive[0] == "d":
                drive = drive[1:]
            array = drive_line[2]
            if array[0] == "u":
                array = array[1:]
            if state == "OK" or state == "NOT-PRESENT":
                add_metric('drive_status', {"controller": controller[1:], "drive": drive, "array": array, "state": state}, 1)
                continue
            if not warn_true and state in ('VERIFYING', 'REBUILDING', 'INITIALIZING'):
                add_metric('drive_status', {"controller": controller[1:], "drive": drive, "array": array, "state": state}, 1)
                continue
            else:
                add_metric('drive_status', {"controller": controller[1:], "drive": drive, "array": array, "state": state}, 0)


def _parse_temperature(val):
    result = re.split('(\d+)(.*)$', val)
    return result[1]

def _parse_yes_ok_on(val):
    if val in ['OK', 'Yes', 'On']:
        return 1
    return 0


"""Generic function to parse key = value lists, based on a detailsMap which
   selects the fields top parse. injectedLabels is just baseline labels to be included.
   Note that the map may list both labels to append to a catchall 'metric', or individual
   metrics, whose name overrides 'metric' and will contain injectedLabels."""

def collect_details(cmdprefix, detailsMap, metric, injectedLabels, verbosity):
    lines = run("%s show all" % cmdprefix, False)
    labels = copy.copy(injectedLabels)
    for line in lines:
        if re.match('^' + cmdprefix + ' (.+?)= (.+?)$', line):
            if verbosity >= 3:
                print line
            result = re.split('\S+ (.+?)= (.+?)$', line)
            #print "RESULT: " + str(result)
            k = result[1].strip()
            v = result[2].strip()
            if k in detailsMap.keys():
                if detailsMap[k]['parser']:
                    v = detailsMap[k]['parser'](v)
                # if this field is meant for a separate metric, do it
                if 'metric' in detailsMap[k]:
                    add_metric(detailsMap[k]['metric'], injectedLabels, v)
                else:
                    labels[detailsMap[k]['label']] = v
    add_metric(metric, labels, 1)

def collect_controller(verbosity):
    CTRL_DETAILS = {
        'Model':              { 'label': 'model',       'parser': None },
        'Firmware Version':   { 'label': 'firmware',    'parser': None },
        'Bios Version':       { 'label': 'bios',        'parser': None },
        'Serial Number':      { 'label': 'serial',      'parser': None },
        'PCB Version':        { 'label': 'pcb',         'parser': None },
        'PCHIP Version':      { 'label': 'pchip',       'parser': None },
        'ACHIP Version':      { 'label': 'achip',       'parser': None },
    }
    lines = run("show")
    controllers = [ line.split()[0] for line in lines if line and line[0] == "c" ]

    for controller in controllers:
        collect_details('/' + controller, CTRL_DETAILS, 'controller_info', { "controller": controller[1:] }, verbosity)
        collect_bbu(controller, verbosity)
        collect_drives(controller, verbosity)


def collect_drives(controller, verbosity):
    DRIVE_DETAILS = {
#        'Status':               { 'metric': 'drive_status',              'parser': _parse_yes_ok_on },
        'Reallocated Sectors':  { 'metric': 'drive_reallocated_sectors', 'parser': None },
        'Temperature':          { 'metric': 'drive_temperature',         'parser': _parse_temperature },
        'Model':                { 'label': 'model',     'parser': None },
        'Firmware Version':     { 'label': 'firmware',  'parser': None },
        'Serial':               { 'label': 'serial',    'parser': None },
        'Belongs to Unit':      { 'label': 'unit',      'parser': None },
        'Link Speed':           { 'label': 'linkspeed', 'parser': None },
    }
    drive_lines = run('/' + controller + ' show drivestatus')
    for drive_line in drive_lines:
        drive_line = drive_line.split()
        drive = drive_line[0]
        collect_details('/' + controller + '/' + drive, DRIVE_DETAILS, 'drive_info', { "controller": controller[1:], 'drive': drive }, verbosity)

def collect_bbu(controller, verbosity):
    BBU_DETAILS = {
        'Firmware Version':          { 'label': 'firmware',    'parser': None },
        'Serial Number':             { 'label': 'serial',      'parser': None },
        'Bootloader Version':        { 'label': 'bootloader',  'parser': None },
        'PCB Revision':              { 'label': 'pcb',         'parser': None },
        'Battery Installation Date': { 'label': 'since',       'parser': None },
        'Online State':               { 'metric': 'bbu_online',  'parser': _parse_yes_ok_on },
        'BBU Ready':                  { 'metric': 'bbu_ready',   'parser': _parse_yes_ok_on },
        'BBU Status':                 { 'metric': 'bbu_status',  'parser': _parse_yes_ok_on },
        'Battery Voltage status':     { 'metric': 'bbu_voltage_status',       'parser': _parse_yes_ok_on },
        'Battery Temperature Status': { 'metric': 'bbu_temperature_status',   'parser': _parse_yes_ok_on },
        'Battery Temperature Value':  { 'metric': 'bbu_temperature',          'parser': _parse_temperature },
    }
    collect_details('/' + controller + '/bbu', BBU_DETAILS, 'bbu_info', { "controller": controller[1:] }, verbosity)

def main():
    """Parses command line options and calls the function to
    test the arrays/drives"""

    parser = OptionParser()


    parser.add_option( "-a",
                       "--arrays-only",
                       action="store_true",
                       dest="arrays_only",
                       help="Only test the arrays. By default both arrays " \
                          + "and drives are checked")

    parser.add_option( "-d",
                       "--drives-only",
                       action="store_true",
                       dest="drives_only",
                       help="Only test the drives. By default both arrays " \
                          + "and drives are checked")


    parser.add_option( "-w",
                       "--warn-rebuilding",
                       action="store_true",
                       dest="warn_true",
                       help="Warn when an array or disk is Rebuilding, " \
                          + "Initializing or Verifying. You might want to do " \
                          + "this to keep a closer eye on things. Also, these " \
                          + "conditions can affect performance so you might " \
                          + "want to know this is going on. Default is to not " \
                          + "warn during these states as they are not usually " \
                          + "problems")

    parser.add_option( "-v",
                       "--verbose",
                       action="count",
                       dest="verbosity",
                       help="Verbose mode. Good for testing plugin. By default\
 only one result line is printed as per Nagios standards")

    parser.add_option( "-V",
                       "--version",
                       action="store_true",
                       dest="version",
                       help="Print version number and exit")

    parser.add_option( "-I",
                       "--info",
                       action="store_true",
                       dest="incl_info",
                       help="Include detailed component info")

    (options, args) = parser.parse_args()

    if args:
        parser.print_help()
        sys.exit(1)

    arrays_only  = options.arrays_only
    drives_only  = options.drives_only
    warn_true    = options.warn_true
    verbosity    = options.verbosity
    version      = options.version
    incl_info    = options.incl_info

    if version:
        print __version__
        sys.exit(OK)

    if arrays_only and drives_only:
        print "You cannot use the -a and -d switches together, they are",
        print "mutually exclusive\n"
        parser.print_help()
        sys.exit(1)
    elif drives_only and warn_true:
        print "You cannot use the -d and -w switches together"
        print "Array warning states are invalid when testing only drives\n"
        parser.print_help()
        sys.exit(1)

    _set_twcli_binary()

    if drives_only:
        test_drives(verbosity, warn_true)
    else:
        test_all(verbosity, warn_true)

    if incl_info:
        collect_controller(verbosity)

    exit_clean()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Caught Control-C..."
        sys.exit(1)
