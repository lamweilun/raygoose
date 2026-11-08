// SetLoadFileDataCallback: the program returns a slice, which cannot outlive
// the call, so C copies it into memory raylib can free with its own allocator.
#include "callback_export.h"
#include "raylib.h"
#include <limits.h>
#include <stdint.h>
#include <string.h>

RG_PROGRAM_EXPORT(const uint8_t *, raylib_load_file_data_callback, uint64_t file_name, int64_t *out_len);

static unsigned char *rg_load_file_data_trampoline(const char *fileName, int *dataSize) {
    int64_t len = 0;
    const uint8_t *bytes = raylib_load_file_data_callback((uint64_t)(uintptr_t)fileName, &len);
    unsigned char *data = NULL;

    if ((bytes == NULL) || (len <= 0) || (len > INT_MAX)) {
        *dataSize = 0;
        return NULL;
    }

    data = (unsigned char *)MemAlloc((unsigned int)len);
    if (data != NULL) {
        memcpy(data, bytes, (size_t)len);
        *dataSize = (int)len;
    } else {
        *dataSize = 0;
    }

    return data;
}

void rg_set_load_file_data_callback(void) {
    if (!RG_PROGRAM_EXPORT_BOUND(raylib_load_file_data_callback)) {
        rg_program_export_missing("SetLoadFileDataCallback", "raylib_load_file_data_callback");
        return;
    }
    SetLoadFileDataCallback(rg_load_file_data_trampoline);
}
