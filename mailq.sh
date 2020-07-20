#!/bin/bash
#
# Description: Expose the size of the mail queue from mailq command.
#
# Author: Thore Guentel <thore.guentel@tangogolf.de>
#
# Results:
# * 0 and more is the count of the mailq objects
# * -1 means mailq command is not found
# * -2 means error at checking the mailq
#

METRIC="mailq_size_total"
HELPTXT="# HELP $METRIC Count of Mails in the Queue"
TYPETXT="# TYPE $METRIC gauge"

MAILQCMD=$(which mailq)
if [ "$MAILQCMD" != "" ]
  then
  QLEN=$($MAILQCMD | grep -c "^[A-F0-9]")
  if [ $QLEN -ge 0 ]
    then
    RES=$QLEN
  else
    RES=-2
  fi
else
  RES=-1
fi

echo -e $HELPTXT\\n$TYPETXT\\n$METRIC $RES
