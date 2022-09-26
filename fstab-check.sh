#!/bin/bash
path="/var/lib/node_exporter/fstab-check.prom"
mapfile -t mountpoints < <(awk '$1 !~ /^#/ && $2 ~ /^[/]/ {print $2}' /etc/fstab)
for mount in "${mountpoints[@]}"
do
   if ! findmnt "$mount" &> /dev/null
   then
         echo "node_fstab_mount_status{filesystem=\"$mount\"} 0" | sponge $path
   else
         echo "node_fstab_mount_status{filesystem=\"$mount\"} 1" | sponge $path
   fi
done
