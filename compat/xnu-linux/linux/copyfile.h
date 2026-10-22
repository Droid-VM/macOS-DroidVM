/* Linux implementation of the COPYFILE_DATA operation used by XNU installfile. */
#ifndef GUNYAH_HOST_COPYFILE_H
#define GUNYAH_HOST_COPYFILE_H
#include <errno.h>
#include <unistd.h>
#define COPYFILE_DATA 1
static inline int fcopyfile(int source, int destination, void *state, int flags)
{
    (void)state;
    if (flags != COPYFILE_DATA) { errno = EINVAL; return -1; }
    char buffer[65536];
    for (;;) {
        ssize_t count = read(source, buffer, sizeof(buffer));
        if (count < 0) { if (errno == EINTR) continue; return -1; }
        if (count == 0) return 0;
        ssize_t offset = 0;
        while (offset < count) {
            ssize_t written = write(destination, buffer + offset, count - offset);
            if (written < 0) { if (errno == EINTR) continue; return -1; }
            if (written == 0) { errno = EIO; return -1; }
            offset += written;
        }
    }
}
#endif
