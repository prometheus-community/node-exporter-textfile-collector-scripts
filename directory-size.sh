#!/usr/bin/env sh
#
# Expose directory usage metrics, passed as an argument.
#
# Usage: add this to crontab:
#
# */5 * * * * prometheus directory-size.sh /var/lib/prometheus | sponge /var/lib/node_exporter/directory_size.prom
#
# Author: Antoine Beaupré <anarcat@debian.org>

echo "# HELP node_directory_size_bytes Disk space used by some directories"
echo "# TYPE node_directory_size_bytes gauge"
du --block-size=1 --summarize "$@" \
  | sed -E \
    -e 's/\\/\\\\/g' \
    -e 's/"/\\"/g' \
    -e 's/^([0-9]+)[[:blank:]](.+)$/node_directory_size_bytes{directory="\2"} \1/'
