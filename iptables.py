#!/usr/bin/env python3

import subprocess
import re


def gather_tables():
    tables = ['filter', 'nat', 'mangle', 'raw']
    re_chain = re.compile('^Chain')
    re_header = re.compile('^num')
    re_blankline = re.compile('^(?:^ *\n)$')

    byte_lines = []
    packet_lines = []

    for ip_proto in ["iptables", "ip6tables"]:
        packet_metric_name = f"{ip_proto}_packets_total"
        byte_metric_name = f"{ip_proto}_bytes_total"

        byte_lines.append(f'# HELP {packet_metric_name} packet counters for {ip_proto} rules.')
        byte_lines.append(f'# TYPE {packet_metric_name} counter')

        packet_lines.append(f'# HELP {byte_metric_name} byte counters for {ip_proto} rules.')
        packet_lines.append(f'# TYPE {byte_metric_name} counter')

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
                l_options = ' '.join(line_pieces[10:]).replace('"', '\\"')

                labels = [f"table=\"{table}\"",
                          f"chain=\"{l_chain_name}\"",
                          f"line_number=\"{l_line_number}\"",
                          f"target=\"{l_target}\"",
                          f"prot=\"{l_prot}\"",
                          f"in=\"{l_in}\"",
                          f"out=\"{l_out}\"",
                          f"chain=\"{l_dest}\"",
                          f"src=\"{l_src}\""
                          f"line_number=\"{l_dest}\"",
                          f"options=\"{l_options}\""
                          ]

                # To the best of my knowledge, this can't be an fstring
                byte_lines.append(
                    '%s_packets_total{%s} %s' %
                    (packet_metric_name, ','.join(labels), l_packets)
                )

                packet_lines.append(
                    '%s{%s} %s' %
                    (byte_metric_name, ','.join(labels), l_bytes))

    return (f"{'\n'.join(packet_lines)}"
            "\n"
            f"{'\n'.join(byte_lines)}")


if __name__ == "__main__":
    print(gather_tables())
