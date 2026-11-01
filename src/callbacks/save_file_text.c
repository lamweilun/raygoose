// SetSaveFileTextCallback: the text is only read, so the program gets the
// C string and copies it with ffi::cstr.
#include "raylib.h"
#include <stdint.h>

extern uint8_t raylib_save_file_text_callback(uint64_t file_name, uint64_t text);

static bool rg_save_file_text_trampoline(const char *fileName, const char *text) {
    return raylib_save_file_text_callback((uint64_t)(uintptr_t)fileName,
                                          (uint64_t)(uintptr_t)text) != 0;
}

void rg_set_save_file_text_callback(void) {
    SetSaveFileTextCallback(rg_save_file_text_trampoline);
}
