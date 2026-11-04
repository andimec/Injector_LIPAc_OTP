#include <iocsh.h>
#include <epicsExit.h>
int main(int argc, char **argv) {
    if(argc>1) iocsh(argv[1]);
    iocsh(nullptr);
    epicsExit(0);
    return 0;
}
