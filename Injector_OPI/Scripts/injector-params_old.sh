#!/bin/bash

#today=`date '+%Y_%m_%d-%H_%M'`;
today=`date '+%Y%m%d-%H%M'`;
#filename="/home/ifmif/data/injector/injectorparam$today.txt"
filename="/home/ifmif/data/injector-params/injectorparam$today.txt"

dispText[0]=".      Security Valve H2   :  ";
dispText[1]=".          Cde Debit H2 (sccm) :  "
dispText[2]=".          Vanne H2            :  ";
dispText[3]=".          Mes Debit H2 (sccm) :  ";
dispText[4]=".      Security Valve D2   :  ";
dispText[5]=".          Cde Debit D2 (sccm) :  ";
dispText[6]=".          Vanne D2            :  ";
dispText[7]=".          Mes Debit D2 (sccm) :  ";
dispText[8]=".      HT : Cde V (kV) =  ";
dispText[9]=".           Mes V(kV)  =  ";
dispText[10]=".      HT : Cde I (mA) =  ";
dispText[11]=".           Mes I(mA)  =  ";
dispText[12]=".      C1 : Cde I (A)  =  ";
dispText[13]=".           Mes I (A)  =  ";
dispText[14]=".      C2 : Cde I (A)  =  ";
dispText[15]=".           Mes I (A)  =  ";
dispText[16]=".      IE_PS  : ";
dispText[17]=".      IE : Cde I (mA) =  ";
dispText[18]=".      IE : Cde V (kV) =  ";
dispText[19]=".           Mes V(kV)  =  ";
dispText[20]=".      RF Mode : ";
dispText[21]=".      Generateur RF  : ";      
dispText[22]=".      Generateur RF ( CW Mode )      P (W)      : ";
dispText[23]=".      Generateur RF ( Pulsed Mode )  P (W)      : ";
dispText[24]=".      Generateur RF ( Pulsed Mode )  Offset (W) : ";
dispText[25]=".      ATU Mode : ";
dispText[26]=".      ATU  (X)      :  ";
dispText[27]=".      ATU  (Y)      :  ";
dispText[28]=".      Ground Electrode (GE): Temp(Deg C) = ";
dispText[29]=".      Repetition (ms)     :  ";
dispText[30]=".      Retard source (ms)  :  ";
dispText[31]=".      Duree source (ms)   :  ";
dispText[32]=".      SOL01 :  Cde I(A)   :  ";
dispText[33]=".               Mes I(A)   :  ";
dispText[34]=".      SOL02 :  Cde I(A)   :  ";
dispText[35]=".               Mes I(A)   :  ";
dispText[36]=".      STH01 :  Cde I(A)   :  ";
dispText[37]=".      STV01 :  Cde I(A)   :  ";
dispText[38]=".      STH02 :  Cde I(A)   :  ";
dispText[39]=".      STV02 :  Cde I(A)   :  ";
dispText[40]=".      R_PS  :  Cde V(kV)  :  ";
dispText[41]=".            :  Mes V(kV)  :  ";
dispText[42]=".      RC_PS :  Cde V(kV)  :  ";
dispText[43]=".      Faraday Cup :      ";
dispText[44]=".      Faraday Cup :  I(mA)  :  ";
dispText[45]=".      Beam Stop   :  I(mA)  :  ";
dispText[46]=".      P1              :    ";
dispText[47]=".      VS              : ";
dispText[48]=".      Pressure (torr)       :  ";
dispText[49]=".      Repetition (ms)          :  ";
dispText[50]=".      Retard Source (ms)       :  ";
dispText[51]=".      Pulse Source (ms)        :  ";
dispText[52]=".      Retard Chopper (ms)      :  ";
dispText[53]=".      Pulse Chopper (ms)       :  ";

dispPV[0]="SRC:SVL:H2OpenStat" #"SRC:SVL_H:OpenStat"
dispPV[1]="SRC:MFCH:Debit" #"SRC:MFC_H:Debit" 
dispPV[2]="SRC:MFCH:StsVanne" #"SRC:MFC_H:StsVanne"
dispPV[3]="SRC:MFCH:Deb2Mes" #"SRC:MFC_H:Deb2Mes"
dispPV[4]="SRC:SVL:D2OpenStat" #"SRC:SVL_D:OpenStat"
dispPV[5]="SRC:MFCD:Debit" #"SRC:MFC_D:Debit"
dispPV[6]="SRC:MFCD:StsVanne" #"SRC:MFC_D:StsVanne"
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
dispPV[23]="SRC:RF_GEN:Pwr"
dispPV[24]="SRC:RF_GEN:Offset"
dispPV[25]="SRC:RF_ATU:ModeXY"
dispPV[26]="SRC:RF_ATU:Mot100"
dispPV[27]="SRC:RF_ATU:Mot101"
dispPV[28]="LEBT:GE:Tcalc"
dispPV[29]="SRC:TIM:Trep"
dispPV[30]="SRC:TIM:RetPulse"
dispPV[31]="SRC:TIM:TPulse"
dispPV[32]="LEBT:SOL01_PS:ISet"
dispPV[33]="LEBT:SOL01_PS:IRdbk"
dispPV[34]="LEBT:SOL02_PS:ISet"
dispPV[35]="LEBT:SOL02_PS:IRdbk"
dispPV[36]="LEBT:STH01_PS:ISet"
dispPV[37]="LEBT:STV01_PS:ISet"
dispPV[38]="LEBT:STH02_PS:ISet"
dispPV[39]="LEBT:STV02_PS:ISet"
dispPV[40]="LEBT:R_PS:VSet"
dispPV[41]="LEBT:R_PS:VRdbkcalc"
dispPV[42]="LEBT:RC_PS:VSet"
dispPV[43]="LEBT:FC:InStat"
dispPV[44]="LEBT:FC:I"
dispPV[45]="LEBT:BS:I"
dispPV[46]="LEBT:VAC01:VacSGVC" #"LEBT:VAC01_SGVC:Vac"
dispPV[47]="LEBT:GV:OpenStat" #"LEBT:VI:OpenStat"
dispPV[48]="LEBT:VAC01:VacSGVC" #!! Attention, same as before!
dispPV[49]="SRC:TIM:Trep"
dispPV[50]="SRC:TIM:RetPulse"
dispPV[51]="SRC:TIM:TPulse"
dispPV[52]="SRC:TIM:RetChopper"
dispPV[53]="SRC:TIM:TChopper"

head1="Summary LIPAc of injector parameters"
head2="Date: "$today

echo $head1 >> $filename;
echo $head2 >> $filename;
echo "" >> $filename;

for i in {0..53}
do
  textPV[i]=`caget ${dispPV[i]} | tail -c 12`;
  echo "${dispText[i]}${textPV[i]}" >> $filename;

done

exit