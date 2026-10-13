#!/usr/bin/env bash

# Get CPU & Mem metrics, lightweight implementation
# Written (quickly) in 2023 by NetInvent
# SCRIPT_VERSION 2026052701

# ps works multiple times faster than top, and shows more processes
# top represents roughly 95% of the time spent by this script
# awk doesn't need optimisations here

printf "# TYPE top_process_cpu_usage gauge\n# HELP top_process_cpu_usage ps gathered instant CPU usage per process\n"
printf "# TYPE top_process_memory_usage gauge\n# HELP top_process_memory_usage ps gathered memory usage per process\n"

if [ "$1" == "" ]; then

ps -ax -o %cpu,%mem,comm,args --cols 80 | awk '{
        args=""; for(i = 4; i<= NF; i++) if ($i!="") {args=args" "$i};
        gsub("{|}|\\\\|\"", "", args);
        # Remove self process
        if ($3=="ps" && args=" -ax -o %cpu,%mem,comm,args --cols 80") { next };
        # Do not keep not cpu hungry entries
        if ($1!="0.0") {
                printf "top_process_cpu_usage{process=\""$3"\",args=\""args"\"} " $1z"\n"};
        # Do not keep not memory hungry entries
        if ($2!="0.0") {
                printf "top_process_memory_usage{process=\""$3"\",args=\""args"\"} " $2z"\n"};
}'

elif [ "$1" == "top" ]; then

# -w [n] forces total column width to [n] so data won't be truncated
# -c forces full commandline, which we need in order to get command arguments
# -bn 1 makes top run once in batch mode

top -w 120 -cbn 1 | awk '{
        # Skip headers
        if (NR<8) { next };
        # Get all command arguments and sanitize them, avoid making empty string if no arguments found
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
                printf "top_process_cpu_usage{process=\""$12"\",args=\""args"\"} " $9z"\n"};
        # Do not keep not memory hungry entries
        if ($10!="0.0") {
                printf "top_process_memory_usage{process=\""$12"\",args=\""args"\"} " $10z"\n"};
}'

fi
