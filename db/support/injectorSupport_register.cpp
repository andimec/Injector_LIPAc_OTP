/* THIS IS A GENERATED FILE. DO NOT EDIT! */
/* Generated from /home/ifmif/Documents/IOCs/example_ioc_mounts/db/support/injectorSupport.expanded.dbd */

#include <string.h>
#ifndef USE_TYPED_RSET
#  define USE_TYPED_RSET
#endif
#include "compilerDependencies.h"
#include "epicsStdlib.h"
#include "iocsh.h"
#include "iocshRegisterCommon.h"
#include "registryCommon.h"
#include "recSup.h"
#include "shareLib.h"

#define epicsExportSharedSymbols
#include "shareLib.h"

extern "C" {

epicsShareExtern typed_rset *pvar_rset_motorRSET;

typedef int (*rso_func)(dbRecordType *pdbRecordType);
epicsShareExtern rso_func pvar_func_motorRecordSizeOffset;

static const char * const recordTypeNames[] = {
    "motor"
};

static const recordTypeLocation rtl[] = {
    {(struct typed_rset *)pvar_rset_motorRSET, pvar_func_motorRecordSizeOffset}
};

epicsShareExtern dset *pvar_dset_devInjectorAi, *pvar_dset_devInjectorAo,
    *pvar_dset_devInjectorBi, *pvar_dset_devInjectorBo,
    *pvar_dset_devMotorSoft, *pvar_dset_devInjectorSi,
    *pvar_dset_devInjectorSo, *pvar_dset_devInjectorWf;

static const char * const deviceSupportNames[] = {
    "devInjectorAi", "devInjectorAo", "devInjectorBi", "devInjectorBo",
    "devMotorSoft", "devInjectorSi", "devInjectorSo", "devInjectorWf"
};

static const dset * const devsl[] = {
    pvar_dset_devInjectorAi, pvar_dset_devInjectorAo,
    pvar_dset_devInjectorBi, pvar_dset_devInjectorBo,
    pvar_dset_devMotorSoft, pvar_dset_devInjectorSi,
    pvar_dset_devInjectorSo, pvar_dset_devInjectorWf
};

int injectorSupport_registerRecordDeviceDriver(DBBASE *pbase)
{
    static int executed = 0;
    if (!pbase) {
        printf("pdbbase is NULL; you must load a DBD file first.\n");
        return -1;
    }

    if (executed) {
        printf("Warning: Registration already done.\n");
    }
    executed = 1;

    registerRecordTypes(pbase, NELEMENTS(rtl), recordTypeNames, rtl);
    registerDevices(pbase, NELEMENTS(devsl), deviceSupportNames, devsl);
    return 0;
}

/* injectorSupport_registerRecordDeviceDriver */
static const iocshArg rrddArg0 = {"pdbbase", iocshArgPdbbase};
static const iocshArg *rrddArgs[] = {&rrddArg0};
static const iocshFuncDef rrddFuncDef = {
    "injectorSupport_registerRecordDeviceDriver",
    1,
    rrddArgs,
    "Register the various records, devices, for this DBD.\n\n"
    "These are registered into the database given as first argument,\n"
    "which should always be 'pdbbase'.\n\n"
    "Example: injectorSupport_registerRecordDeviceDriver pdbbase\n",
};
static void rrddCallFunc(const iocshArgBuf *)
{
    iocshSetError(injectorSupport_registerRecordDeviceDriver(*iocshPpdbbase));
}

} // extern "C"

/*
 * Register commands on application startup
 */
static int Registration() {
    iocshRegisterCommon();
    iocshRegister(&rrddFuncDef, rrddCallFunc);
    return 0;
}

static int done EPICS_UNUSED = Registration();
