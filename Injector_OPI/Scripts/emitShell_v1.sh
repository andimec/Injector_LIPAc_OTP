#!/bin/bash
#cd /home/pmattei/IFMIF/topIFMIF/emitApp/gui
#cd /home/pmattei/IFMIF/scripts
cd /home/ifmifmgr/topIFMIF_INJ/bin/linux-x86_64
if [ "`ps -ef | grep xterm | grep -v grep | wc -l`" == 0 ]; then
  /usr/bin/xterm -g 110x60+995+80 -j +ah -hold -fg green -bg black -rightbar \
  -e ./emitSnlEmu_v1 -s &
fi
