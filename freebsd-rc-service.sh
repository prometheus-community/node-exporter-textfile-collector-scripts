#! /bin/sh -
#
# Expose metrics about the status of FreeBSD rc(8) services.
#
# SYNOPSIS
#	freebsd-rc-service.sh [-i ignored]
#	freebsd-rc-service.sh -h
#
# DESCIPTION
# This script should probably run as UID 0 in order to be able to successfully
# get the status of each service (e.g., as of FreeBSD 14.0-CURRENT, the cron's
# PID file is readable only to UID 0).
#
# A status metric is provided for a service if:
# - The service is enabled.
# - The service provides a status command.
# - The service is not ignored via the -i flag.
#
# This script accepts the following flags:
# -h		Print help and exit.
# -i ignored	Ignore specified services. Services have to be listed
#		by their absolute paths,
#		e.g., "/etc/rc.d/sendmail /etc/rc.d/ip6addrctl".
#
# METRICS
# This script provides the following metrics:
#
# - freebsd_rc_service_status{path="PATH"} STATUS
#   where:
#   - PATH is an absolute path to the service script
#   - STATUS is the exit code of the "quietstatus" command of the script.
#
# --
#
# Copyright 2022 Mateusz Piotrowski <mateusz.piotrowski@klarasystems.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author: Mateusz Piotrowski <0mp@FreeBSD.org>

#
# Functions
#

help() {

	cat 1>&2 <<EOF
Usage: $0 [-i ignored]
       $0 -h
EOF
}

# Not all rc(8) services provide the status command. In general, that's a good
# (but not ideal) indication of which services are long-running programs like
# web servers.
list_services_with_status() {

	service -e | xargs -n 1 -J {} -- {} 2>&1 1>/dev/null | awk '/status/{print $2}'
}

# SYNOPSIS
#	filter_ignored_services "all_services" "ignored_services"
filter_ignored_services() {
	_all_services="$1"
	shift
	_ignored_services="$1"
	shift

	if [ "$_ignored_services" = "" ]; then
		printf '%s\n' "$_all_services"
	else
		# Assemble a grep invocation that filters out all the ignored
		# services.
		set -- grep -v
		for _is in $_ignored_services; do
			set -- "$@" -e "$_is"
		done
		printf '%s\n' "$_all_services" | xargs -n 1 | "$@"
	fi
}

#
# Preamble
#

set -u

#
# Parse command-line arguments.
#

ignored_services=""
OPTIND=1
while getopts hi: opt; do
	case "$opt" in
	h)
		help
		exit 0
		;;
	i)
		ignored_services="$OPTARG"
		;;
	?)
		exit 1
		;;
	esac
done
if [ "$OPTIND" -ne 0 ]; then
	shift "$(( OPTIND - 1 ))"
fi

#
# Main
#

unfiltered_services=$(list_services_with_status)
services=$(filter_ignored_services "$unfiltered_services" "$ignored_services")

echo '# HELP freebsd_rc_service_status Status of a FreeBSD rc(8) service.'
echo '# TYPE freebsd_rc_service_status gauge'

for s in $services; do
	if $s quietstatus >/dev/null 2>&1; then
		isrunning="1"
	else
		isrunning="0"
	fi
	echo "freebsd_rc_service_status{path=\"${s}\"} ${isrunning}"
done
