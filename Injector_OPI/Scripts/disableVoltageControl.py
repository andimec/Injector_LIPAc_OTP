from org.csstudio.opibuilder.scriptUtil import PVUtil
from org.csstudio.opibuilder.scriptUtil import ConsoleUtil

PSInfo = PVUtil.getString(pvs[0])

PSInfo=PSInfo.split(',')

if PSInfo[0]=="Matsusada Precision":
    #ConsoleUtil.writeInfo("Visible")
    widget.setPropertyValue("visible",True)
    
else: 
    #ConsoleUtil.writeInfo("Disabled button")
    widget.setPropertyValue("visible",False)