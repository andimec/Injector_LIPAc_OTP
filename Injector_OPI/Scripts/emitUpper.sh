#!/bin/bash

#set FIC=` caget LEBT:EMIT:upperText | awk '{print$2}'`
set FIC=`/home/epicsmgr/EPICS/base/bin/linux-x86/caget LEBT:EMIT:upperText`
echo $FIC

