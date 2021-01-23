#!/bin/bash
#
#
# Description: Exposes OS Release metrics that are available from
# systemd's /etc/os-release file.
#
# Author: Darshil Chanpura <dtchanpura@protonmail.com>

set -o errexit
set -o pipefail

. /etc/os-release 2> /dev/null

echo "# HELP node_os_info A metric with a constant '1' value labeled by OS Release id, id_like, name, pretty_name, version, version_codename and version_id"
echo "# TYPE node_os_info gauge"
echo "node_os_info{id=\"${ID}\",id_like=\"${ID_LIKE}\",name=\"${NAME}\",pretty_name=\"${PRETTY_NAME}\",version=\"${VERSION}\",version_codename=\"${VERSION_CODENAME}\",version_id=\"${VERSION_ID}\"} 1"
