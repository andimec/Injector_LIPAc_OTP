#include <cstring>
#include <dbScan.h>
#include <devSup.h>
#include <epicsExport.h>
struct extendedDset { long number; DEVSUPFUN functions[8]; };
static IOSCANPVT interruptList;
static long get_ioint_info(int, dbCommon*, IOSCANPVT* dest) {
    if (!interruptList) scanIoInit(&interruptList);
    *dest=interruptList;
    return 0;
}
extern "C" {
extern dset *pvar_dset_devAiSoft;
extendedDset devInjectorAi;
epicsExportAddress(dset,devInjectorAi);
extern dset *pvar_dset_devAoSoft;
extendedDset devInjectorAo;
epicsExportAddress(dset,devInjectorAo);
extern dset *pvar_dset_devBiSoft;
extendedDset devInjectorBi;
epicsExportAddress(dset,devInjectorBi);
extern dset *pvar_dset_devBoSoft;
extendedDset devInjectorBo;
epicsExportAddress(dset,devInjectorBo);
extern dset *pvar_dset_devSiSoft;
extendedDset devInjectorSi;
epicsExportAddress(dset,devInjectorSi);
extern dset *pvar_dset_devSoSoft;
extendedDset devInjectorSo;
epicsExportAddress(dset,devInjectorSo);
extern dset *pvar_dset_devWfSoft;
extendedDset devInjectorWf;
epicsExportAddress(dset,devInjectorWf);
}
static int prepare() {
    std::memcpy(&devInjectorAi, pvar_dset_devAiSoft, sizeof(long)+pvar_dset_devAiSoft->number*sizeof(DEVSUPFUN));
    devInjectorAi.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    std::memcpy(&devInjectorAo, pvar_dset_devAoSoft, sizeof(long)+pvar_dset_devAoSoft->number*sizeof(DEVSUPFUN));
    devInjectorAo.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    std::memcpy(&devInjectorBi, pvar_dset_devBiSoft, sizeof(long)+pvar_dset_devBiSoft->number*sizeof(DEVSUPFUN));
    devInjectorBi.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    std::memcpy(&devInjectorBo, pvar_dset_devBoSoft, sizeof(long)+pvar_dset_devBoSoft->number*sizeof(DEVSUPFUN));
    devInjectorBo.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    std::memcpy(&devInjectorSi, pvar_dset_devSiSoft, sizeof(long)+pvar_dset_devSiSoft->number*sizeof(DEVSUPFUN));
    devInjectorSi.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    std::memcpy(&devInjectorSo, pvar_dset_devSoSoft, sizeof(long)+pvar_dset_devSoSoft->number*sizeof(DEVSUPFUN));
    devInjectorSo.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    std::memcpy(&devInjectorWf, pvar_dset_devWfSoft, sizeof(long)+pvar_dset_devWfSoft->number*sizeof(DEVSUPFUN));
    devInjectorWf.functions[3]=reinterpret_cast<DEVSUPFUN>(get_ioint_info);
    return 0;
}
static int prepared=prepare();
