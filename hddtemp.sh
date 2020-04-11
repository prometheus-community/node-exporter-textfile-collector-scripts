#!/bin/bash
#
#
# Description: Expose hard dist temperature metrics using hddtempd
# this expects a running and configured hddtempd,
# refer to t he hddtemp documentation for this case.
# 
# if disks are repored as in sleep ("SLP") the value will be -101
# for all other unknown status, the reported value will be -100
# this scenario asumes that any disk will never run in -100 degree celcius (-148°F)
#
#
# Author: Andres Bott <contact@andresbott.com>

temps=$(nc localhost 7634 2>&1 |sed 's/|//m' | sed 's/||/ \n/g' | awk -F'|' '{print $1 " " $3 }')

## exit if unable to connect to hddtempd
if [[ $temps == *"Connection refused"* ]]; then
  >&2 echo "# hddtemp file collector failed with connection refuesd to hddtempd on localhost:7634"
  exit 1
fi

echo '# HELP hddtemp Disk temperature measured by hddtemp'
echo '# TYPE hddtemp gauge'

#Set the field separator to new line
IFS=$'\n'

for item in $temps
do
  dev=$(echo "$item" | cut -d' ' -f1)
  val=$(echo "$item" | cut -d' ' -f2)

  # check if disk is sleep
  if [[ "$val" == "SLP" ]]
  then
      val="-101"
  # if not sleep but reporte value is not a number
  elif ! [[ "$val" =~ ^[0-9]+$ ]]
  then
        val="-100"
  fi
    echo "node_hddtemp{device=\"$dev\"} $val"
done
