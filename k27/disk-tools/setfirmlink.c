/*
 * setfirmlink: query, set or clear an APFS firmlink on a directory of a System-role volume in a volume group, through APFS's own
 * fsctl (apfs_vnop_ioctl 0xC4084A3C -> handle_firmlink_ctl, reversed from the 27.2 apfs kext). Setting needs root, a read-write
 * mount and the entitlement com.apple.private.apfs.set-firmlink (setfirmlink.entitlements). The target is relative to the root of
 * the Data volume of the group, like the second column of /usr/share/firmlinks.
 *
 *   setfirmlink DIR                 print the firmlink target of DIR (or "-")
 *   setfirmlink DIR TARGET          make DIR a firmlink to TARGET
 *   setfirmlink -d DIR              remove the firmlink of DIR
 *   setfirmlink -f [FILE]           every line "SOURCE<TAB>TARGET" of FILE (default /usr/share/firmlinks) whose SOURCE is a directory
 */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

int fsctl(const char *, unsigned long, void *, unsigned int);   /* libSystem; <sys/fsctl.h> is not in the SDK */

#define APFSIOC_FIRMLINK 0xC4084A3CUL

struct firmlink_ctl {
    char path[1024];        /* target, relative to the Data volume root */
    unsigned int get;       /* 1: query; 0: set or clear */
    unsigned int value;     /* set: 1 = make a firmlink, 0 = remove; query result: 1 = is a firmlink */
};

static int query(const char *dir)
{
    struct firmlink_ctl ctl = {.get = 1, .value = 1};
    if (fsctl(dir, APFSIOC_FIRMLINK, &ctl, 0) != 0) {
        fprintf(stderr, "%s: %s\n", dir, strerror(errno));
        return 1;
    }
    printf("%s\t%s\n", dir, ctl.value ? ctl.path : "-");
    return 0;
}

static int set(const char *dir, const char *target)
{
    struct firmlink_ctl ctl = {.get = 0, .value = target != NULL};
    if (target) {
        strlcpy(ctl.path, target, sizeof(ctl.path));
    }
    if (fsctl(dir, APFSIOC_FIRMLINK, &ctl, 0) != 0) {
        fprintf(stderr, "%s -> %s: %s\n", dir, target ? target : "(remove)", strerror(errno));
        return errno == EEXIST ? 0 : 1;      /* EEXIST: already in that state */
    }
    return query(dir);
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "-f") != 0) {
        return query(argv[1]);
    }
    if (argc == 3 && strcmp(argv[1], "-d") == 0) {
        return set(argv[2], NULL);
    }
    if (argc == 3 && strcmp(argv[1], "-f") != 0) {
        return set(argv[1], argv[2]);
    }
    if (argv[1] && strcmp(argv[1], "-f") == 0) {
        FILE *file = fopen(argc > 2 ? argv[2] : "/usr/share/firmlinks", "r");
        char line[2100], source[1024], target[1024];
        int failed = 0;
        struct stat st;
        if (!file) {
            perror("firmlinks");
            return 1;
        }
        while (fgets(line, sizeof(line), file)) {
            if (sscanf(line, "%1023[^\t]\t%1023[^\n]", source, target) != 2) {
                continue;
            }
            if (lstat(source, &st) != 0 || !S_ISDIR(st.st_mode)) {
                printf("%s\tskipped (not a directory)\n", source);
                continue;
            }
            failed |= set(source, target);
        }
        fclose(file);
        return failed;
    }
    fprintf(stderr, "usage: setfirmlink DIR [TARGET] | -d DIR | -f [FILE]\n");
    return 2;
}
