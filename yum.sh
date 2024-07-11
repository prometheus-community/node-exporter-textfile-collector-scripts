#!/usr/bin/env bash
#
# Description: Expose metrics from yum updates.
#
# Author: Slawomir Gonet <slawek@otwiera.cz>
#
# Based on apt.sh by Ben Kochie <superq@gmail.com>

set -u -o pipefail

# shellcheck disable=SC2016
filter_awk_script='
BEGIN { mute=1 }
/Obsoleting Packages/ {
  mute=0
}
mute && /^[[:print:]]+\.[[:print:]]+/ {
  print $3
}
'

print_metric_general='{print "yum_upgrades_pending{origin=\""$2"\",category=\"all\"} "$1}'
print_metric_security='{print "yum_upgrades_pending{origin=\""$2"\",category=\"security\"} "$1}'

check_upgrades() {
  /usr/bin/yum $1 -q check-update |
    /usr/bin/xargs -n3 |
    awk "${filter_awk_script}" |
    sort |
    uniq -c |
    awk "${2}"
}

check_all_upgrades() { check_upgrades "" "${print_metric_general}" ; }
check_security_upgrades() { check_upgrades "--security" "${print_metric_security}" ; }

upgrades=$(check_all_upgrades)
security_upgrades=$(check_security_upgrades)

echo '# HELP yum_upgrades_pending Yum package pending updates by origin.'
echo '# TYPE yum_upgrades_pending gauge'
if [[ -n "${upgrades}" ]]; then
  echo "${upgrades}"
else
  echo 'yum_upgrades_pending{origin="",category=\"all\"} 0'
fi
if [[ -n "${security_upgrades}" ]]; then
  echo "${security_upgrades}"
else
  echo 'yum_upgrades_pending{origin="",category=\"security\"} 0'
fi


# If yum-utils/dnf-utils is not installed then we skip rendering this metric
if [[ -x /bin/needs-restarting ]]; then
  echo '# HELP node_reboot_required Node reboot is required for software updates.'
  echo '# TYPE node_reboot_required gauge'
  if /bin/needs-restarting -r >/dev/null 2>&1; then
    echo 'node_reboot_required 0'
  else
    echo 'node_reboot_required 1'
  fi
fi
