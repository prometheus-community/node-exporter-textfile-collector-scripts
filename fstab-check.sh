#!/bin/bash
echo "# HELP node_fstab_mount_status List and status of filesystem mountpoints"
echo "# TYPE node_fstab_mount_status gauge"
mapfile -t mountpoints < <(awk '$1 !~ /^#/ && $2 ~ /^[/]/ {print $2}' /etc/fstab)
for mount in "${mountpoints[@]}"
do
  if ! findmnt "$mount" &> /dev/null
  then
    echo "node_fstab_mount_status{mountpoint=\"$mount\"} 0"
  else
    echo "node_fstab_mount_status{mountpoint=\"$mount\"} 1"
  fi
done
