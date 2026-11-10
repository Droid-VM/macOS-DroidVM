/*
 * mkxart: add the xART volume (APFS role 0x100) to an APFS container. launchd's mount-phase-1 (apfs_boot_util) mounts it at
 * /System/Volumes/xarts and aborts without it (docs/k27-real-disk-layout-plan.md P5). APFS lets only a task with the entitlement
 * com.apple.private.apfs.xart create one (apfs_is_volume_role_allowed), which diskutil does not have: this binary carries it
 * (mkxart.entitlements) and must be in the trust cache. APFS.framework's APFSVolumeCreate is resolved at run time (no SDK stub).
 *
 *   mkxart CONTAINER          e.g. mkxart disk1
 */
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <stdio.h>

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: mkxart CONTAINER\n");
        return 2;
    }
    void *apfs = dlopen("/System/Library/PrivateFrameworks/APFS.framework/APFS", RTLD_NOW);
    int (*create)(const char *, CFMutableDictionaryRef) = apfs ? dlsym(apfs, "APFSVolumeCreate") : NULL;
    CFStringRef *role_key = apfs ? dlsym(apfs, "kAPFSVolumeRoleKey") : NULL;
    CFStringRef *name_key = apfs ? dlsym(apfs, "kAPFSVolumeNameKey") : NULL;
    if (!create || !role_key || !name_key) {
        fprintf(stderr, "APFS.framework: %s\n", dlerror());
        return 1;
    }
    int role = 0x100;
    CFMutableDictionaryRef properties = CFDictionaryCreateMutable(NULL, 0, &kCFTypeDictionaryKeyCallBacks,
        &kCFTypeDictionaryValueCallBacks);
    CFNumberRef number = CFNumberCreate(NULL, kCFNumberIntType, &role);
    CFDictionaryAddValue(properties, *role_key, number);
    CFDictionaryAddValue(properties, *name_key, CFSTR("xART"));
    int error = create(argv[1], properties);
    printf("APFSVolumeCreate(%s, xART): %#x\n", argv[1], error);
    CFRelease(number);
    CFRelease(properties);
    return error != 0;
}
