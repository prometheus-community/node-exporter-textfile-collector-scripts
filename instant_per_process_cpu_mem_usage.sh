#!/usr/bin/env bash

# Get CPU & Mem metrics, lightweight implementation
# Written (quickly) in 2023 by NetInvent
# SCRIPT_VERSION 2023110201


# -w [n] forces total column width to [n] so data won't be truncated
# -c forces full commandline, which we need in order to get command arguments
# -bn 1 makes top run once in batch mode

top -w 120 -cbn 1 | awk '{
        # Skip headers
        if (NR<8) { next };
        # Get all command arguments
        args=""; for(i = 13; i<= NF; i++) if ($i!="") {args=args" "$i};
        # Sanitize arguments
        gsub("{|}|\\\\|\"", "", args);
        # Sanitize debian style floats in top
        gsub(",", ".", $9);
        gsub(",", ".", $10);
        # Dont keep more than 30 chars for args, since we limited top -w size, we wont need this
        #args=substr(args, 1, 30);
        # Remove self process
        if ($12=="top" && args=" -w 120 -cbn 1") { next };
        # Do not keep not cpu hungry entries
        if ($9!="0.0") {
                if (cputype==0) { printf "# TYPE top_process_cpu_usage gauge\n# HELP top_process_cpu_usage ps gathered instant CPU usage per process\n"; cputype=1 };
                printf "top_process_cpu_usage{pid=\""$1"\",process=\""$12"\",sanitized_args=\""args"\"} " $9z"\n"};
        # Do not keep not memory hungry entries
        if ($10!="0.0") {
                if (memtype==0) { printf "# TYPE top_process_memory_usage gauge\n# HELP top_process_memory_usage ps gathered memory usage per process\n"; memtype=1 };
                printf "top_process_memory_usage{pid=\""$1"\",process=\""$12"\",sanitized_args=\""args"\"} " $10z"\n"};
}'
