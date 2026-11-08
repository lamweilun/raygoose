// A callback setter installs a C trampoline that calls a fixed export fn in the
// program. The handler is referenced weakly: a plain reference would leave an
// undefined symbol in the package's JIT library, which `goose run` loads with
// RTLD_NOW before the program is compiled into the same process, so nothing
// could resolve it and the library would fail to load. Weak, the library always
// loads; a setter whose handler the program does not define says so and leaves
// raylib's default in place.
#pragma once

#include <stdio.h>

#if defined(_MSC_VER)
// MSVC has no weak externals: callback_export.c aliases an absent handler to a
// stub symbol that is never called, and the setter compares addresses.
void rg_unbound_export(void);
#define RG_PROGRAM_EXPORT_ATTR(name)
#define RG_PROGRAM_EXPORT_BOUND(name) ((const void *)&(name) != (const void *)&rg_unbound_export)
#elif defined(__APPLE__)
// Mach-O wants weak_import for a symbol a dylib may not find when it loads.
#define RG_PROGRAM_EXPORT_ATTR(name) __attribute__((weak_import))
#define RG_PROGRAM_EXPORT_BOUND(name) ((name) != 0)
#else
#define RG_PROGRAM_EXPORT_ATTR(name) __attribute__((weak))
#define RG_PROGRAM_EXPORT_BOUND(name) ((name) != 0)
#endif

// Declares the program's handler, which the trampoline calls.
#define RG_PROGRAM_EXPORT(ret, name, ...) RG_PROGRAM_EXPORT_ATTR(name) ret name(__VA_ARGS__)

static inline void rg_program_export_missing(const char *setter, const char *name) {
    fprintf(stderr,
            "raylib: %s() installs a trampoline that calls the program's `export fn %s`; "
            "the program defines none, so raylib's default handler stays in place "
            "(a `goose run` cannot bind exports: use `goose build`)\n",
            setter, name);
}
