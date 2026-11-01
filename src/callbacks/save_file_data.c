// SetSaveFileDataCallback: the data is only read, so the program gets the
// pointer and the size and copies what it wants.
#include "raylib.h"
#include <stdint.h>

extern uint8_t raylib_save_file_data_callback(uint64_t file_name, uint64_t data, int32_t data_size);

static bool rg_save_file_data_trampoline(const char *fileName, const void *data, int dataSize) {
    return raylib_save_file_data_callback((uint64_t)(uintptr_t)fileName,
                                          (uint64_t)(uintptr_t)data,
                                          (int32_t)dataSize) != 0;
}

void rg_set_save_file_data_callback(void) {
    SetSaveFileDataCallback(rg_save_file_data_trampoline);
}
