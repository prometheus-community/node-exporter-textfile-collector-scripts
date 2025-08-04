#!/bin/sh

# Expose timestamp of given path
#
# This will provide the last modification timestamp (technically,
# stat(1)'s %Y parameter), which is a number of seconds since the
# epoch, once per provided path. It will claim the timestamp is zero
# if stat(1) fails to extract the timestamp for any reason.
#
# Usage: add this to crontab:
#
# */5 * * * * prometheus path-timestamp.sh /var/lib/prometheus | sponge /var/lib/node_exporter/path-timestamp.prom
#
# Author: Antoine Beaupré <anarcat@debian.org>

echo "# HELP node_path_modification_timestamp_seconds Last change timestamp"
echo "# TYPE node_path_modification_timestamp_seconds gauge"
for path in "$@"; do
    printf 'node_path_modification_timestamp_seconds{path="%s"} ' "$path"
    stat -c %Y "$path" 2>/dev/null || echo 0
done
