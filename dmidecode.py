#!/usr/bin/env python
#
# dmidecode Prometheus node_exporter textfile collector script
#
# (c) 2020, Nuno Tavares <n.tavares@portavita.eu>
# Based on code from: https://github.com/huanghao/dmidecode
#

from __future__ import print_function
import os, sys

__version__ = "0.0.1"

TYPE = {
    0:  'bios',
    1:  'system',
    2:  'base board',
    3:  'chassis',
    4:  'processor',
    7:  'cache',
    8:  'port connector',
    9:  'system slot',
    10: 'on board device',
    11: 'OEM strings',
    #13: 'bios language',
    15: 'system event log',
    16: 'physical memory array',
    17: 'memory device',
    19: 'memory array mapped address',
    24: 'hardware security',
    25: 'system power controls',
    27: 'cooling device',
    32: 'system boot',
    41: 'onboard device',
    }


def parse_dmi(content):
    """
    Parse the whole dmidecode output.
    Returns a list of tuples of (type int, value dict).
    """
    info = []
    lines = iter(content.strip().splitlines())
    while True:
        try:
            line = next(lines)
        except StopIteration:
            break

        if line.startswith('Handle 0x'):
            typ = int(line.split(',', 2)[1].strip()[len('DMI type'):])
            if typ in TYPE:
                info.append((TYPE[typ], _parse_handle_section(lines)))
    return info


def _parse_handle_section(lines):
    """
    Parse a section of dmidecode output

    * 1st line contains address, type and size
    * 2nd line is title
    * line started with one tab is one option and its value
    * line started with two tabs is a member of list
    """
    data = {
        '_title': next(lines).rstrip(),
        }

    for line in lines:
        line = line.rstrip()
        if line.startswith('\t\t'):
            if isinstance(data[k], list):
                data[k].append(line.lstrip())
        elif line.startswith('\t'):
            k, v = [i.strip() for i in line.lstrip().split(':', 1)]
            if v:
                data[k] = v
            else:
                data[k] = []
        else:
            break

    return data


def profile():
#    if os.isatty(sys.stdin.fileno()):
#        content = _get_output()
#    else:
#        content = sys.stdin.read()
    content = _get_output()

    info = parse_dmi(content)
    _show(info)


def _get_output():
    import subprocess
    try:
        output = subprocess.check_output('/usr/sbin/dmidecode', shell=False)

    except Exception as e:
        print(e, file=sys.stderr)
        if str(e).find("command not found") == -1:
            print("please install dmidecode", file=sys.stderr)
            print("e.g. sudo apt install dmidecode",file=sys.stderr)

        sys.exit(1)
    return output.decode()

#
# Builds a label dict from o, with all the 'expected' labels reduced to lowercase-letter-only labels
# and filtering out those whose values are listed in 'rejected'
#
def _get_labels(o, expected, rejected):
    r = {}
    for l in expected:
        if l in o.keys():
            if o[l] not in rejected:
                r[''.join(filter(str.isalpha, l.lower()))] = o[l]
    return r

def _show(info):
    def _get(i):
        return [v for j, v in info if j == i]

    system = _get('system')[0]
    l = _get_labels(system, ['Manufacturer','Product Name', 'Serial Number'], ['Not Specified'])
    print ('node_dmi_hardware_info{{{}}} 1'.format( ','.join('{}="{}"'.format(k,v) for k,v in l.items()) ))

    for cpu in _get('processor'):
        l = _get_labels(cpu, ['Manufacturer','Family', 'Max Speed', 'Core Count'], ['Not Specified'])
        print ('node_dmi_processor{{{}}} 1'.format( ','.join('{}="{}"'.format(k,v) for k,v in l.items()) ))

    for mem in _get('memory device'):
        if mem['Size'] == 'No Module Installed':
            continue
        l = _get_labels(mem, ['Size', 'Speed', 'Manufacturer', 'Serial Number', 'Type', 'Part Number', 'Form Factor', 'Locator', 'Bank Locator'], ['Not Specified'])
        print ('node_dmi_memory_device{{{}}} 1'.format( ','.join('{}="{}"'.format(k,v) for k,v in l.items()) ))


    bios = _get('bios')[0]
    l = _get_labels(bios, ['Vendor', 'Version', 'Release Date'], ['Not Specified'])
    print ('node_dmi_bios{{{}}} 1'.format( ','.join('{}="{}"'.format(k,v) for k,v in l.items()) ))

if __name__ == '__main__':
    profile()
