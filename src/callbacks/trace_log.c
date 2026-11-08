// SetTraceLogCallback: raylib hands the handler a format string and a
// va_list, neither of which crosses the Goose FFI. C formats the message and
// passes the finished text to the program's export.
#include "callback_export.h"
#include "raylib.h"
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>

RG_PROGRAM_EXPORT(void, raylib_trace_log_callback, int32_t level, uint64_t text);

static void rg_trace_log_trampoline(int logLevel, const char *text, va_list args) {
    char buffer[1024] = { 0 };

    vsnprintf(buffer, sizeof buffer, text, args);
    raylib_trace_log_callback(logLevel, (uint64_t)(uintptr_t)buffer);
}

void rg_set_trace_log_callback(void) {
    if (!RG_PROGRAM_EXPORT_BOUND(raylib_trace_log_callback)) {
        rg_program_export_missing("SetTraceLogCallback", "raylib_trace_log_callback");
        return;
    }
    SetTraceLogCallback(rg_trace_log_trampoline);
}
