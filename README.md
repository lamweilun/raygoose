# raygoose

[![ci](https://github.com/lamweilun/raygoose/actions/workflows/ci.yml/badge.svg)](https://github.com/lamweilun/raygoose/actions/workflows/ci.yml)

A [raylib](https://github.com/raysan5/raylib) binding for the
[Goose](https://github.com/aardappel/goose) language, generated from raylib's
own headers.

Pinned to raylib `4bfb72d8` (v6.5-dev), built from the `vendor/raylib` submodule,
and tested with Goose `v2026.4`.

## Platforms

Raylib itself is compiled from the submodule by the package's CMake target, so
its per-platform link dependencies (winmm/gdi32/opengl32 on Windows, the
Cocoa/IOKit/OpenGL frameworks on macOS, X11/GL on Linux) come along with the
target's link closure. Nothing platform-specific is written in the binding.

| target | what is verified |
|---|---|
| Linux x86-64 | built, all examples run |
| Windows x64, MSVC | CI: Goose built, binding generated, every example linked, headless smoke ran |
| macOS arm64 | CI: same |
| Windows x64 (MinGW ABI), Windows arm64 | `layout_check.c` and `shims.c` compile for the ABI |
| macOS x86-64, Linux arm64 | `layout_check.c` and `shims.c` compile for the ABI |
| 32-bit (x86, arm32, RPi 32-bit) | rejected at configure time, `sizeof(void*) != 8` |
| Web, Android, iOS | not supported: different toolchains and asset packaging |

The CI jobs build raylib from source and run two headless programs, so they work
on a runner: `examples/smoke.goose` (raymath, a padded-struct return, the C
`long` shim, `ffi::cstr`) and `examples/callbacks.goose` (the trace log and the
four file callbacks). The windowed examples are built but not run there. `make
cross-check` covers the ABIs CI does not have a runner for: all 231 `sizeof` and
`offsetof` assertions and every adapter compile against the real headers for
LLP64 Windows and arm64 macOS/Linux.

C `long` is the one type whose width differs (8 bytes on LP64, 4 on Windows), so
it never crosses directly: `GetFileModTime` goes through a shim that widens to
`int64_t`, keeping one Goose signature everywhere — the smoke test reads it on
every platform. `raymath` is not bound at all: it is a Goose port, tested
against the C library on every build of the binding (`tools/check_raymath.py`).

## What is covered

Three headers, plus what they need to be usable:

| header | how | contents |
|---|---|---|
| `raylib.h` | `extern fn` | 619 functions — core/window, shapes, textures, text, models, audio, camera, gestures — 35 structs, 22 enums |
| `raymath.h` | Goose port, `namespace raymath` | 146 functions over the same `Vector2/3/4/Matrix/Quaternion` types |
| `rlgl.h` | `extern fn` | 163 functions, `rlVertexBuffer`/`rlDrawCall`/`rlRenderBatch`, 12 enums and the `RL_*` constants |
| types and constants | generated | 38 structs and ~530 constants (enums, `FLAG_*`, `RL_*`, the 26 color macros) |

Nine of the 38 structs contain C padding and cross by pointer through
`src/shims.c`; everything else crosses by value. `raymath` is not bound at all,
it is Goose code.

**Not covered yet:**

- `raygui` and `physac` — neither is part of raylib 6.5 (`raygui` ships as a
  header in the examples, `physac` is a separate, unmaintained repository).
- `rcamera`'s `GetCameraForward/Up/Right` — exported by the library but not
  declared in `raylib.h`; the two `UpdateCamera*` functions are covered.
- `rgestures`' internal `ProcessGestureEvent`/`UpdateGestures` — they take an
  internal event struct; the 8 public gesture functions are covered.
- The audio callbacks — `SetAudioStreamCallback` and the two
  `AttachAudio*Processor` functions. raylib runs them on the mixer thread and
  they rewrite the sample buffer in place; a Goose export must stay on the
  thread that ran `goose_init` and there is no pointer write. The trace log and
  the four file callbacks are covered, through fixed exports (see
  [Callbacks](#callbacks)).
- `TextFormat` — variadic; use Goose's `str(...)`.
- `rlLoadExtensions` — it wants a GL procedure loader, and the one address
  raylib can offer, `rlGetProcAddress`, calls that loader, so a Goose callback
  would recurse.

Everything else in the raylib repository is examples, templates and resources.

## Using it

A program needs one import line; no build file of its own:

```goose
import raylib from "https://github.com/lamweilun/raygoose@v0.1.1";

fn main() {
    raylib::InitWindow(800, 450, "hello");
    raylib::SetTargetFPS(60);
    while !raylib::WindowShouldClose() {
        raylib::BeginDrawing();
        raylib::ClearBackground(raylib::RAYWHITE);
        raylib::DrawText("hello from goose", 20, 20, 40, raylib::MAROON);
        raylib::DrawCircleV(raylib::Vector2 { 400.0, 300.0 }, 60.0, raylib::ORANGE);
        raylib::EndDrawing();
    }
    raylib::CloseWindow();
}
```

```sh
goose run app.goose     # first build compiles raylib, later runs are cached
```

## Getting the source

```sh
git clone --recurse-submodules https://github.com/lamweilun/raygoose
```

`vendor/raylib` is a submodule: clone with `--recurse-submodules`, or run
`git submodule update --init --recursive` afterwards. Then, inside the
repository:

```sh
goose run examples/demo.goose   # build and run the demo
make gen                        # regenerate raylib.goose, raymath.goose and src/*.c
make check                      # build every example
```

Examples:

| file | what it covers |
|---|---|
| `examples/basic.goose` | raw API: window, shapes, text, FPS |
| `examples/demo.goose` | ergonomic layer, custom font, formatted text, 24 bouncing balls |
| `examples/hard_cases.goose` | raymath, rlgl, audio, render textures, ray casts, `ffi::cstr` |
| `examples/smoke.goose` | headless: raymath, a padded struct return, the C `long` shim, `ffi::cstr` |
| `examples/callbacks.goose` | headless: the trace log and the four file callbacks |

## How the binding works

Goose compiles to one C file and its FFI is "declare the C function and call
it" (`docs/reference.md` §24). So a binding is mostly a transcription problem:

| C | Goose |
|---|---|
| `int`, `float`, `bool` | `i32`, `f32`, `bool` |
| `Color` by value | `struct Color { r: u8, g: u8, b: u8, a: u8 }` |
| `Texture2D` | `struct Texture` + alias resolved by the generator |
| `const char *` | `const u8&` (raw) or a slice helper (ergonomic) |
| `int *out` | `i32&` |
| `Font *` | `Font&` |
| `void *`, `char **`, library-owned pointers | `u64` |
| `#define LOG_INFO 4` | `let LOG_INFO: i32 = 4;` |

Goose structs are **packed**, so where C inserts padding the generator writes
`pad n` at the exact offset. `src/layout_check.c` asserts every `sizeof` and `offsetof` against the real
headers, so a wrong layout breaks the build instead of the drawing.

### The four things that need C

1. **Structs containing padding** cannot cross by value: `Sound`, `Music`,
   `AudioStream`, `Mesh`, `ModelSkeleton`, `Shader`, `RayCollision`,
   `FilePathList`, `rlVertexBuffer`. Each function that takes or returns one gets
   a shim (`PlaySound(Sound)` → `void rg_PlaySound(void *sound)`) or a thin
   Goose wrapper for returns (`LoadSound` → `Sound` through an out-pointer).
2. **Variadic functions** cannot be declared at all. `TraceLog` gets a fixed shim
   (`trace_log(level, text)`); `TextFormat` is deliberately not bound — use
   Goose's own `str(...)` and append `"\0"` for the C string.
3. **NULL pointers.** Goose references are never null, so functions that accept
   NULL (`LoadFontEx` with no codepoints, shader value pointers) go through
   shims. `src/shims.c` holds all of them; 89 of the 782 functions use one.
4. **Callbacks.** Goose has no function-pointer values, so the five setters take
   no argument and install a C trampoline that calls a fixed export in the
   program (see [Callbacks](#callbacks)). `src/callbacks/` holds one file per
   callback.

Everything else is a direct `extern fn` call — the same call the C compiler
would emit.

### Callbacks

Goose has no function-pointer values, so a callback cannot be passed. The five
that can be bound are setters with no argument; the program defines the fixed
export the trampoline in `src/callbacks/` calls:

| binding call | export the program defines |
|---|---|
| `SetTraceLogCallback()` | `raylib_trace_log_callback(level: i32, text: u64)` |
| `SetLoadFileDataCallback()` | `raylib_load_file_data_callback(file_name: u64) -> const u8[:]` |
| `SetSaveFileDataCallback()` | `raylib_save_file_data_callback(file_name: u64, data: u64, data_size: i32) -> bool` |
| `SetLoadFileTextCallback()` | `raylib_load_file_text_callback(file_name: u64) -> const u8[:]` |
| `SetSaveFileTextCallback()` | `raylib_save_file_text_callback(file_name: u64, text: u64) -> bool` |

C strings arrive as `u64`; `ffi::cstr` and `ffi::bytes` copy them, and they are
valid only during the call. A loader returns a slice backed by a global buffer;
the trampoline copies it into raylib's allocator before returning. The handlers
run on the main thread, inside whatever raylib call triggered them.

A setter takes no argument: it installs a fixed trampoline, and the C object
refers to the program's handler weakly, so the package's library loads even when
the program defines none. A setter whose export is missing installs nothing and
says so on stderr, leaving raylib's default in place. That is all `goose run` can
do: a JIT run compiles the program into the compiler's process *after* the
package's library is loaded, so its exports are in no symbol table the loader
sees. Use `goose build`, which links statically, for a program that installs a
callback.

```goose
import raylib from "https://github.com/lamweilun/raygoose@v0.1.1";
import ffi;

export fn raylib_trace_log_callback(level: i32, text: u64) {
    print(level, ": ", ffi::cstr(text), "\n");
}

fn main() {
    raylib::SetTraceLogCallback();
    raylib::InitWindow(800, 450, "hello");
}
```

`examples/callbacks.goose` is the headless test for all five.

### raymath is ported, not bound

`raymath`'s 146 functions are translated to Goose in `raymath.goose`
(`namespace raymath`), not called through C. It is plain maths over the same
`Vector2/3/4/Matrix` types, so it inlines instead of crossing the boundary,
works with any raylib build, and `goose run` needs no C for it.
`tools/check_raymath.py` runs every function against the C original and
compares the results as C floats: the port is bit-identical on the current
header.

### Strings

raylib wants NUL-terminated `char *`. The raw declarations take `const u8&`, so
`DrawText("hi\0"[0], ...)` works. The helpers do it for you:

```goose
raylib::DrawText("hello", 20, 20, 40, raylib::RAYWHITE);
let t = str("fps ", raylib::GetFPS(), "\0");   // formatted, Goose's own str()
raylib::DrawText(t, 20, 60, 20, raylib::GRAY);
```

These are overloads under raylib's own names, so the raw form still works
where you want it (`DrawText("hi\0"[0], ...)`): `InitWindow`, `DrawText`,
`DrawTextEx`, `MeasureText`, `MeasureTextEx`, `LoadTexture`, `LoadImage`,
`LoadFont`, `LoadSound`, `LoadMusicStream`.

### Build

`raylib.build` names one CMake target. The root `CMakeLists.txt` builds the
vendored raylib plus `raygoose_native` (the shims and the layout asserts) and
links them statically into the program. That means:

- nothing needs to be installed on the machine;
- `goose run` works, since a native part is present;
- the library and the binding are versioned together.

A dynamic variant is also possible (`extern "raylib" { ... }` with a
`dylibs_linux` mapping), but it only covers the functions that need no shim, so
the generated binding uses the static path.

## Limitations

- **Audio callbacks are not bound.** Goose has no function pointers and its
  exports must stay on the thread that ran `goose_init`; raylib's audio
  processors run on the mixer thread and write the sample buffer in place. The
  trace log and the four file callbacks are covered — see [Callbacks](#callbacks).
- **Callbacks need `goose build`.** A `goose run` loads the package's JIT library
  before it compiles the program into the same process, so the program's exports
  are in no symbol table the loader can see; the setters report and leave
  raylib's defaults in place. A built executable links statically and binds them.
- **`TextFormat` is missing on purpose.** Use `str()`.
- **No pointer arithmetic.** `Mesh.vertices`, `Font.recs`, `Model.meshes`,
  `FilePathList.paths` and friends are opaque `u64` handles. You can pass them
  back to raylib, but to read elements you need `ffi::bytes(ptr, n)` (a copy) or
  a C accessor.
- **`u64` results cannot be dereferenced.** Strings come back via
  `ffi::cstr(GetWorkingDirectory())`.
- **`rlgl`'s extension loader** (`rlLoadExtensions`) takes a function pointer and
  is unusable.
- **64-bit only.** Pointers cross as `u64`, so 32-bit targets are refused at
  configure time.
- **Windows and macOS are tested headless only.** CI builds every example there
  and runs the smoke test; the windowed examples have only been watched on
  Linux x86-64.

## Regenerating

```sh
python3 tools/gen_bindings.py
```

```sh
python3 tools/gen_bindings.py   # raylib.h + rlgl.h -> raylib.goose, src/*.c
python3 tools/port_raymath.py   # raymath.h       -> raymath.goose
python3 tools/check_raymath.py  # port vs the C library, 146 functions
```

`gen_bindings.py` writes `raylib.goose`, `src/shims.c` and
`src/layout_check.c`; the ergonomic helpers are a fixed block at the end, so
they survive regeneration. `rlgl.h`'s implementation section is cut off.
`port_raymath.py` translates raymath's scalar bodies (its SSE branch is
dropped); three functions with out-parameters or a `switch` are hand-written
in it, and `check_raymath.py` builds both the C and the Goose versions, runs
them on the same inputs and compares the results as C floats.

### Updating raylib

```sh
make bump RAYLIB=6.2     # a tag or any commit
```

That moves the pin in `vendor/raylib`, regenerates both files, builds every
example and runs the raymath comparison. Commit the submodule pointer and the
regenerated files together; CI then proves the result on Linux, Windows and
macOS.

What usually needs a hand:

- **Struct changes** are caught by `src/layout_check.c`. The generator
  recomputes the `pad n` fields, and the asserts fail loudly if a field moved,
  so a layout change cannot slip through silently.
- **raymath is translated, not bound.** `port_raymath.py` stops with the
  function and the statement it cannot translate — that is how the
  `MatrixPerspective`/`MatrixOrtho` `double`-to-`float` change between 6.2 and
  master showed up. Fix the translator, or add the function to its `HAND`
  table.
- **New variadic functions** are skipped by the generator; watch for "skipped
  declaration" lines and add a shim next to the existing ones. A new callback
  setter needs a trampoline in `src/callbacks/` and a no-arg wrapper in the
  ergonomic block.
- Anything else — new functions, structs, enums, pointer returns — comes
  through without work.

Regenerating takes seconds; the slow part is raylib compiling once per
compiler, which Goose caches under `~/.goose/build`.

## License

zlib, the same license as raylib — see [LICENSE](LICENSE). raylib and raymath,
vendored as the `vendor/raylib` submodule and ported into `raymath.goose`, are
under that same license.

## AI disclosure

This project was written with an AI coding agent (OpenCode) working under a
human's direction: the header generator, the raymath port, the C adapters, the
examples and this document. The checks are not decorative — the struct layouts
are asserted against raylib's headers at compile time, the raymath port is
diffed function by function against the C library by `tools/check_raymath.py`,
and CI builds the binding and runs the headless smoke test on Linux, Windows and
macOS.
