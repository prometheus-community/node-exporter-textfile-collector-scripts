#!/bin/bash
mapfile -t mountpoints < <(awk '$1 !~ /^#/ && $2 ~ /^[/]/ {print $2}' /etc/fstab)
for mount in "${mountpoints[@]}"
do
   if ! findmnt "$mount" &> /dev/null
   then
         echo "node_fstab_mount_status{filesystem=\"$mount\"} 0"
   else
         echo "node_fstab_mount_status{filesystem=\"$mount\"} 1"
   fi
done
