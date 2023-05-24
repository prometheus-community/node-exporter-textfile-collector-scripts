#!/usr/bin/env sh
#
# Generate node_os_info and node_os_version metrics on legacy systems
# which are not handled by node_exporter's own collector
# (e.g. CentOS 6)

set -e

[ -f /etc/os-release ] && exit 0
[ -f /usr/lib/os-release ] && exit 0

ID=""
ID_LIKE=""
NAME=""
PRETTY_NAME=""
VERSION=""
VERSION_CODENAME=""
VERSION_ID=""
VERSION_METRIC=""

if [ -f /etc/redhat-release ]; then
  # CentOS release 6.10 (Final)
  PRETTY_NAME="$(cat /etc/redhat-release)"
  if [ -f /etc/centos-release ]; then
    ID="centos"
  elif [ -f /etc/oracle-release ]; then
    ID="ol"
  fi
  ID_LIKE="rhel fedora"
  NAME="$(expr "$PRETTY_NAME" : '\([^ ]*\)')" || true
  VERSION="$(expr "$PRETTY_NAME" : '.* \([0-9].*\)')" || true
  VERSION_ID="$(expr "$PRETTY_NAME" : '.* \([0-9][0-9.]*\)')" || true
  # metric cannot distinguish 6.1 from 6.10, so only keep the integer part
  VERSION_METRIC="$(expr "$VERSION_ID" : '\([0-9]*\)')" || true
elif [ -f /etc/lsb-release ]; then
  # DISTRIB_ID=Ubuntu
  # DISTRIB_RELEASE=12.04
  # DISTRIB_CODENAME=precise
  # DISTRIB_DESCRIPTION="Ubuntu 12.04 LTS"
  # Beware, old versions of CentOS with package "redhat-lsb-core" look like this instead:
  # LSB_VERSION=base-4.0-amd64:base-4.0-noarch:core-4.0-amd64:core-4.0-noarch

  # shellcheck disable=SC1091
  . /etc/lsb-release
  ID="$(echo "${DISTRIB_ID}" | tr '[:upper:]' '[:lower:]')"
  NAME="${DISTRIB_ID}"
  PRETTY_NAME="${DISTRIB_DESCRIPTION}"
  VERSION="${DISTRIB_RELEASE} (${DISTRIB_CODENAME})"
  VERSION_CODENAME="${DISTRIB_CODENAME}"
  VERSION_ID="${DISTRIB_RELEASE}"
  # 12.04.1 -> 12.04
  VERSION_METRIC="$(expr "$VERSION_ID" : '\([0-9]*\|[0-9]*\.[0-9]*\)')" || true
fi

[ "$VERSION_METRIC" = "" ] && VERSION_METRIC="0"

cat <<EOS
node_os_info{id="$ID",id_like="$ID_LIKE",name="$NAME",pretty_name="$PRETTY_NAME",version="$VERSION",version_codename="$VERSION_CODENAME",version_id="$VERSION_ID"} 1
node_os_version{id="$ID",id_like="$ID_LIKE",name="$NAME"} $VERSION_METRIC
EOS
