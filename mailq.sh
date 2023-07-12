#!/bin/bash
#
# Description: Expose the size of the mail queue from mailq command.
#
# Author: Thore Guentel <thore.guentel@tangogolf.de>
# Version: 1.1.0
#
# Results:
# 0 and more is the count of the mailq objects
#

METRIC_RES="mailq_queue_size_total"
HELP_RES="# HELP $METRIC_RES Count of mails in the queue"
TYPE_RES="# TYPE $METRIC_RES gauge"

MAILQCMD=$(which mailq)

if [ "$MAILQCMD" != "" ]; then
  $MAILQCMD 2>&1>/dev/null
  if [ $? -gt 0 ]; then
    echo "Mail system seems to be down"
    exit 3
  else
    QLEN=$($MAILQCMD 2>/dev/null | grep -c "^[A-F0-9]")
    if [ $QLEN -ge 0 ]; then
      RES=$QLEN
    else
      echo "mailq could not be checked"
      exit 2
    fi
  fi
else
  echo "mailq command not found"
  exit 1
fi

echo -e $HELP_RES\\n$TYPE_RES\\n$METRIC_RES $RES
