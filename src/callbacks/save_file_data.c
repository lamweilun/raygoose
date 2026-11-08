// SetSaveFileDataCallback: the data is only read, so the program gets the
// pointer and the size and copies what it wants.
#include "callback_export.h"
#include "raylib.h"
#include <stdint.h>

RG_PROGRAM_EXPORT(uint8_t, raylib_save_file_data_callback, uint64_t file_name, uint64_t data, int32_t data_size);

static bool rg_save_file_data_trampoline(const char *fileName, const void *data, int dataSize) {
    return raylib_save_file_data_callback((uint64_t)(uintptr_t)fileName,
                                          (uint64_t)(uintptr_t)data,
                                          (int32_t)dataSize) != 0;
}

void rg_set_save_file_data_callback(void) {
    if (!RG_PROGRAM_EXPORT_BOUND(raylib_save_file_data_callback)) {
        rg_program_export_missing("SetSaveFileDataCallback", "raylib_save_file_data_callback");
        return;
    }
    SetSaveFileDataCallback(rg_save_file_data_trampoline);
}
