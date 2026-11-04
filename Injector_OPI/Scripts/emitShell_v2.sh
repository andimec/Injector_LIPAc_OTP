#!/bin/bash
#cd /home/pmattei/IFMIF/topIFMIF/emitApp/gui
#cd /home/pmattei/IFMIF/scripts
# This path will disappear in the future
cd /home/ifmifmgr/topIFMIF_INJ/bin/linux-x86_64
# cd /mnt/ioc/topIFMIF_INJ/(target)/emitIOCSNL/bin/linux-x86_64 (final path)

export EPICS_CA_MAX_ARRAY_BYTES=10485760

if [ "`ps -ef | grep xterm | grep -v grep | wc -l`" == 0 ]; then
  /usr/bin/xterm -g 110x60+995+80 -j +ah -hold -fg green -bg black -rightbar \
  -e ./emitSnlEmu_v2 -s &
fi
