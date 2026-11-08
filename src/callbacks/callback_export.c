// MSVC has no weak externals. The loader option aliases each absent handler to
// this stub, which the setter's address check keeps from ever being called.
#include "callback_export.h"

#if defined(_MSC_VER)
void rg_unbound_export(void) { }

#pragma comment(linker, "/alternatename:raylib_trace_log_callback=rg_unbound_export")
#pragma comment(linker, "/alternatename:raylib_load_file_data_callback=rg_unbound_export")
#pragma comment(linker, "/alternatename:raylib_save_file_data_callback=rg_unbound_export")
#pragma comment(linker, "/alternatename:raylib_load_file_text_callback=rg_unbound_export")
#pragma comment(linker, "/alternatename:raylib_save_file_text_callback=rg_unbound_export")
#endif
