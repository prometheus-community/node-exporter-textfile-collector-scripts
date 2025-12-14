#!/usr/bin/env python3

import subprocess
import re
import os

tables = ['filter', 'nat', 'mangle', 'raw']
re_chain = re.compile('^Chain')
re_header = re.compile('^num')
re_blankline = re.compile('^(?:^ *\n)$')

iptables_packet_lines = []
iptables_byte_lines = []

for ip_proto in ["iptables", "ip6tables"]:
    for table in tables:
      # Run iptables with the following options:
      # -L: Listing all rules for chain
      # -n: Numeric lookup
      # -v: Verbose output
      # -x: Exact values
      # -t table: Specified table table
      # --line-numbers: Show line numbers
      cmd = [f'/sbin/{ip_proto}', '-L', '-n', '-v', '-x', '-t', table, "--line-numbers"]
      proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
      for line in proc.stdout.readlines():
        line = line.decode('utf8')

        if re_blankline.match(str(line)):
          continue

        line_pieces = line.split()

        # Check if line is the beginning of a chain
        if re_chain.match(str(line_pieces[0])):
          l_chain_name = line_pieces[1]
          continue

        # Check if the line is the header for the given chain
        if re_header.match(str(line_pieces[0])):
          continue

        l_line_number = line_pieces[0]
        l_packets = line_pieces[1]
        l_bytes = line_pieces[2]
        l_target = line_pieces[3]
        l_prot = line_pieces[4]
        l_in = line_pieces[6]
        l_out = line_pieces[7]
        l_src = line_pieces[8]
        l_dest = line_pieces[9]
        l_options = ' '.join(line_pieces[10:]).replace('"','\\"')

        # To the best of my knowledge, this can't be an fstring
        iptables_packet_lines.append('%s_packets_total{table="%s",chain="%s",line_number=%s,target="%s",prot="%s",in="%s",out="%s",src="%s",dest="%s",opt="%s"} %s' % (ip_proto,table,l_chain_name,l_line_number,l_target,l_prot,l_in,l_out,l_src,l_dest,l_options,l_packets))
        iptables_byte_lines.append('%s_bytes_total{table="%s",chain="%s",line_number=%s,target="%s",prot="%s",in="%s",out="%s",src="%s",dest="%s",opt="%s"} %s' % (ip_proto,table,l_chain_name,l_line_number,l_target,l_prot,l_in,l_out,l_src,l_dest,l_options,l_bytes))

    print(f'# HELP {ip_proto}_packets_total packet counters for {ip_proto} rules.')
    print(f'# TYPE {ip_proto}_packets_total counter')
    for line in iptables_packet_lines:
        print(line)

    print(f'# HELP {ip_proto}_bytes_total byte counters for {ip_proto} rules.')
    print(f'# TYPE {ip_proto}_bytes_total counter')
    for line in iptables_byte_lines:
        print(line)
