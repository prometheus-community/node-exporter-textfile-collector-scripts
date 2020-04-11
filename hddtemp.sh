#!/bin/bash
#
#
# Description: Expose hard dist temperature metrics using hddtempd
# this expects a running and configured hddtempd,
# refer to t he hddtemp documentation for this case.
#
# Author: Andres Bott <contact@andresbott.com>

temps=`nc localhost 7634 2>&1 |sed 's/|//m' | sed 's/||/ \n/g' | awk -F'|' '{print $1 " " $3 }'`

## exit if unable to connect to hddtempd
if [[ $temps == *"Connection refused"* ]]; then
  >&2 echo "# hddtemp file collector failed with connection refuesd to hddtempd on localhost:7634"
  exit 1
fi

echo '# HELP hddtemp Disk tem perature measured by hddtemp'
echo '# TYPE hddtemp gauge'

#Set the field separator to new line
IFS=$'\n'

for item in $temps
do
    echo "node_hddtemp{device=\"`echo $item | cut -d' ' -f1`\"} `echo $item | cut -d' ' -f2`"
done
 
