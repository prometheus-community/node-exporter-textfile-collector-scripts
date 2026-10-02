#!/bin/bash

InitiatorName=$(grep "^InitiatorName=" /etc/iscsi/initiatorname.iscsi | cut -d'=' -f2)

echo "# HELP node_iscsi_initiator_name name of the nodes iSCSI initiator"
echo "# TYPE node_iscsi_initiator_name gauge"
echo 'node_iscsi_initiator_name{initiator_name="'"${InitiatorName}"'"}1'
