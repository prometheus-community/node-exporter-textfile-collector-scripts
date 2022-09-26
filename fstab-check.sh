#!/bin/bash
> /var/lib/node_exporter/fstab-check.prom
mountpoints=( $(awk '$1 !~ /^#/ && $2 ~ /^[/]/ {print $2}' /etc/fstab) )
for mount in ${mountpoints[@]}
do
   if ! findmnt "$mount" &> /dev/null
   then
         echo "node_fstab_mount_status{filesystem="\"$mount"\"} 0" >> /var/lib/node_exporter/fstab-check.prom
   else
         echo "node_fstab_mount_status{filesystem="\"$mount"\"} 1" >> /var/lib/node_exporter/fstab-check.prom
   fi
done
