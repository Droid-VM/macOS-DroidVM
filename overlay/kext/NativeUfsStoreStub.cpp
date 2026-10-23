// The persistence hooks NativeRamBlock imports weakly: no board store window, so the Data disk stays volatile (mode 0 makes attachStore a no-op).
#include <stdint.h>

extern "C" {
unsigned native_ufs_store_mode(void) { return 0; }
int native_ufs_store_open(uint64_t, uint64_t *, const char **) { return 0; }
int native_ufs_store_read(uint64_t, uint32_t, void *) { return 0; }
int native_ufs_store_write(uint64_t, uint32_t, const void *) { return 0; }
int native_ufs_store_sync(void) { return 0; }
unsigned native_ufs_store_gpt_check(void) { return 0; }
}
