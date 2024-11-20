#!/bin/bash
#
# Description: Expose metrics from zypper updates.
#
# Author: Markus Otto <zuntrax@infra.run>

upgrades="$(/usr/bin/zypper list-updates \
  | /usr/bin/awk -F'|' '/^v/ {gsub(/ /,"",$2); print $2 $6}' \
  | /usr/bin/sort \
  | /usr/bin/uniq -c \
  | /usr/bin/awk '{print "zypper_upgrades_pending{origin=\"" $2 "\",arch=\"" $3 "\"} " $1}'
)"

echo '# HELP zypper_upgrades_pending Zypper package pending updates by origin.'
echo '# TYPE zypper_upgrades_pending gauge'
if [[ -n "${upgrades}" ]] ; then
  echo "${upgrades}"
else
  echo 'zypper_upgrades_pending{origin="",arch=""} 0'
fi

echo '# HELP node_reboot_required Node reboot is required for software updates.'
echo '# TYPE node_reboot_required gauge'
if [[ -f '/run/reboot-needed' ]] ; then
  echo 'node_reboot_required 1'
else
  echo 'node_reboot_required 0'
fi
