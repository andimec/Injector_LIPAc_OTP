#!/bin/bash
# updated at 27/Mar/2023

# updated at 29/June/2017 by R. Ichimiya (QST)
#if [ $HOSTNAME == "injector-wks" ]
#	then export LD_LIBRARY_PATH=/opt/glibc-2.14/lib:$LD_LIBRARY_PATH
#fi

#today=`date '+%Y_%m_%d-%H_%M'`;
today=`date '+%Y%m%d-%H%M'`;
#filename="/home/ifmif/data/injector/injectorparam$today.txt"
# updated at 29/June/2017 by R. Ichimiya (QST)
#filename="/home/ifmif/data/data_INJ/injector-params/injectorparam$today.txt"
filename="/mnt/data_old/data_INJ/injector-params/injectorparam$today.txt"

dispText[0]=".      Security aValve H2   :  ";
dispText[1]=".          Valve H2            :  ";
dispText[2]=".          Flow set H2 (sccm) :  ";
dispText[3]=".          Flow read H2 (sccm) :  ";
dispText[4]=".      Security Valve D2   :  ";
dispText[5]=".          Valve D2            :  ";
dispText[6]=".          Flow set D2 (sccm) :  ";
dispText[7]=".          Flow read D2 (sccm) :  ";
dispText[8]=".      Main HV : set V (kV) =  ";
dispText[9]=".      Main HV : read V(kV)  =  ";
dispText[10]=".      Main HV : set I (mA) =  ";
dispText[11]=".      Main HV : read I (mA)  =  ";
dispText[12]=".      C1 : set I (A)  =  ";
dispText[13]=".      C1 : read I (A)  =  ";
dispText[14]=".      C2 : set I (A)  =  ";
dispText[15]=".      C2 : read I (A)  =  ";
dispText[16]=".      IE_PS  : ";
dispText[17]=".      IE : set I (mA) =  ";
dispText[18]=".      IE : set V (kV) =  ";
dispText[19]=".      IE : read V(kV)  =  ";
dispText[20]=".      RF Mode : ";
dispText[21]=".      Generateur RF  : ";      
dispText[22]=".      Generateur RF ( CW Mode )      P (W)      : ";
dispText[23]=".      Generateur RF ( Pulsed Mode )  P (W)      : ";
dispText[24]=".      Generateur RF ( Pulsed Mode )  Offset (W) : ";
dispText[25]=".      ATU Mode : ";
dispText[26]=".      ATU  (X)      :  ";
dispText[27]=".      ATU  (Y)      :  ";
dispText[28]=".      Ground Electrode (GE): Temp(Deg C) = ";
#dispText[]=".      Repetition (ms)     :  ";
#dispText[]=".      Retard source (ms)  :  ";
#dispText[]=".      Duree source (ms)   :  ";
dispText[29]=".      SOL01 :  set I(A)   :  ";
dispText[30]=".      SOL01 :  read I(A)   :  ";
dispText[31]=".      SOL02 :  set I(A)   :  ";
dispText[32]=".      SOL02 :  read I(A)   :  ";
dispText[33]=".      STH01 :  set I(A)   :  ";
dispText[34]=".      STV01 :  set I(A)   :  ";
dispText[35]=".      STH02 :  set I(A)   :  ";
dispText[36]=".      STV02 :  set I(A)   :  ";
dispText[37]=".      R_PS  :  set V(kV)  :  ";
dispText[38]=".      R_PS  :  read V(kV)  :  ";
dispText[39]=".      R_PS  :  read I(A)  :  ";
dispText[40]=".      RC_PS :  set V(kV)  :  ";
dispText[41]=".      RC_PS :  read V(kV)  :  ";
dispText[42]=".      Faraday Cup :      ";
dispText[43]=".      Faraday Cup :  I(mA)  :  ";
dispText[44]=".      Faraday Cup Water Temp. inlet (Deg C)  :  ";
dispText[45]=".      Faraday Cup Water Temp. outlet (Deg C)  :  ";
#dispText[]=".      Beam Stop   :  I(mA)  :  ";
dispText[46]=".      FC (EMU-FC, ACCT) Measurememt Start (ms)  :  ";
dispText[47]=".      FC (EMU-FC, ACCT) Measurememt End (ms)   : ";
dispText[48]=".      SGVC #1 (mbar)       :    ";
dispText[49]=".      GV              : ";
dispText[50]=".      SGVC #2 (mbar)       :  ";
dispText[51]=".      Repetition (ms)          :  ";
#dispText[]=".      Retard Source (ms)       :  ";
dispText[52]=".      Source pulse width (ms)        :  ";
dispText[53]=".      Chopper Delay (us)      :  ";
dispText[54]=".      Chopper pulse width (us)       :  ";
dispText[55]=".      Chopper HV Set (V)       :  ";
dispText[56]=".      Valve Kr            :  ";
dispText[57]=".      Flow set Kr (sccm) :  ";
dispText[58]=".      Flow read Kr (sccm) :  ";
dispText[59]=".      HV sparks count :  ";
dispText[60]=".      Repeller sparks count :  ";

dispPV[0]="SRC:SVL:H2OpenStat" #"SRC:SVL_H:OpenStat"
dispPV[1]="SRC:MFCH:StsVanne" #"SRC:MFC_H:StsVanne"
dispPV[2]="SRC:MFCH:Debit" #"SRC:MFC_H:Debit" 
dispPV[3]="SRC:MFCH:Deb2Mes" #"SRC:MFC_H:Deb2Mes"
dispPV[4]="SRC:SVL:D2OpenStat" #"SRC:SVL_D:OpenStat"
dispPV[5]="SRC:MFCD:StsVanne" #"SRC:MFC_D:StsVanne"
dispPV[6]="SRC:MFCD:Debit" #"SRC:MFC_D:Debit"
dispPV[7]="SRC:MFCD:Deb1Mes" #"SRC:MFC_D:Deb1Mes"
dispPV[8]="LEBT:HV_PS:HTCmd"
dispPV[9]="LEBT:HV_PS:ScaleVHT"
dispPV[10]="LEBT:HV_PS:ICmd"
dispPV[11]="LEBT:HV_PS:ScaleIHT"
dispPV[12]="SRC:COIL01_PS:ISet"
dispPV[13]="SRC:COIL01_PS:IRdbk"
dispPV[14]="SRC:COIL02_PS:ISet"
dispPV[15]="SRC:COIL02_PS:IRdbk"
dispPV[16]="SRC:IE_PS:OnStat"
dispPV[17]="SRC:IE_PS:ISet"
dispPV[18]="SRC:IE_PS:VSet"
dispPV[19]="SRC:IE_PS:VRdbkcalc"
dispPV[20]="SRC:RF_GENE:CWmdOn"
dispPV[21]="SRC:RF_GENE:MOCmdOn"
dispPV[22]="SRC:RF_GENE:WrtPI"
dispPV[23]="SRC:RF_GENE:RfPwr"
dispPV[24]="SRC:RF_GENE:RfOffset"
dispPV[25]="SRC:RF_ATU:ModeXY"
dispPV[26]="SRC:RF_ATU:Mot100"
dispPV[27]="SRC:RF_ATU:Mot101"
dispPV[28]="LEBT:GE:Tcalc"
#dispPV[]="SRC:TIM:Trep"
#dispPV[]="ACCELERATORVIEW:TS:REP:MS"
#dispPV[]="SRC:TIM:RetPulse"
#dispPV[]="SRC:TIM:TPulse"
#dispPV[]="ACCELERATORVIEW:TS:PULSE:MS"
dispPV[29]="LEBT:SOL01_PS:ISet"
dispPV[30]="LEBT:SOL01_PS:IRdbk"
dispPV[31]="LEBT:SOL02_PS:ISet"
dispPV[32]="LEBT:SOL02_PS:IRdbk"
dispPV[33]="LEBT:STH01_PS:ISet"
dispPV[34]="LEBT:STV01_PS:ISet"
dispPV[35]="LEBT:STH02_PS:ISet"
dispPV[36]="LEBT:STV02_PS:ISet"
dispPV[37]="LEBT:R_PS:VSet"
dispPV[38]="LEBT:R_PS:VRdbkcalc"
dispPV[39]="LEBT:R_PS:IRdbkcalc"
dispPV[40]="LEBT:RC_PS:VSet"
dispPV[41]="LEBT:RC_PS:VRdbkcalc"
dispPV[42]="LEBT:FC:InStat"
dispPV[43]="LEBT:FC:I"
#dispPV[]="LEBT:BS:I"
dispPV[44]="LEBT:FC:Tincalc"
dispPV[45]="LEBT:FC:Toutcalc"
dispPV[46]="LEBT:FACQ:Tmeas1"
dispPV[47]="LEBT:FACQ:Tmeas2"
dispPV[48]="LEBT:VAC01:VacSGVC" #"LEBT:VAC01_SGVC:Vac"
dispPV[49]="LEBT:GV:OpenStat" #"LEBT:VI:OpenStat"
dispPV[50]="LEBT:VAC02:VacSGVC" #!! Attention, same as before!
#dispPV[]="SRC:TIM:Trep"
dispPV[51]="ACCELERATORVIEW:TS:REP:MS"
#dispPV[]="SRC:TIM:RetPulse"
#dispPV[]="SRC:TIM:TPulse"
dispPV[52]="ACCELERATORVIEW:TS:PULSE:MS"
#dispPV[]="SRC:TIM:RetChopper"
dispPV[53]="CCS:TSAPP:ChopGateDelayRdbk"
#dispPV[]="SRC:TIM:TChopper"
dispPV[54]="CCS:TSAPP:ChopGateWidthRdbk"
dispPV[55]="LEBT:CHOP_PS:VSet"
dispPV[56]="LEBT:MFC:StsVanne"
dispPV[57]="LEBT:MFC:Debit"
dispPV[58]="LEBT:MFC:Deb1Mes"
dispPV[59]="LEBT:HV:Counter"
dispPV[60]="LEBT:Repeller:Counter"

head1="Summary LIPAc of injector parameters"
head2="Date: "$today

echo $head1 >> $filename;
echo $head2 >> $filename;
echo "" >> $filename;

for i in {0..60}
do
   # updated at 29/June/2017 by R. Ichimiya (QST)
#   if [ $HOSTNAME == "injector-wks" ]
#      then
#	textPV[i]=`/home/ifmif/epicsbin/caget ${dispPV[i]} | tail -c 12`;
#      else
#	textPV[i]=`caget ${dispPV[i]} | tail -c 12`;
#   fi
 
#  textPV[i]=`/home/ifmif/epicsbin/caget ${dispPV[i]} | tail -c 12`;
   textPV[i]=`caget -t ${dispPV[i]}`;
   echo ${dispText[i]}${textPV[i]} >> $filename;

done

exit
