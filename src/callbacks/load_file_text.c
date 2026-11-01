// SetLoadFileTextCallback: the program returns a slice; C copies it into a
// NUL-terminated buffer raylib can free with its own allocator.
#include "raylib.h"
#include <limits.h>
#include <stdint.h>
#include <string.h>

extern const uint8_t *raylib_load_file_text_callback(uint64_t file_name, int64_t *out_len);

static char *rg_load_file_text_trampoline(const char *fileName) {
    int64_t len = 0;
    const uint8_t *bytes = raylib_load_file_text_callback((uint64_t)(uintptr_t)fileName, &len);
    char *text = NULL;

    if ((bytes == NULL) || (len < 0) || (len > INT_MAX)) return NULL;

    text = (char *)MemAlloc((unsigned int)len + 1);
    if (text == NULL) return NULL;

    if (len > 0) memcpy(text, bytes, (size_t)len);
    text[len] = '\0';

    return text;
}

void rg_set_load_file_text_callback(void) {
    SetLoadFileTextCallback(rg_load_file_text_trampoline);
}
