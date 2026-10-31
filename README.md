# raygoose

A [raylib](https://github.com/raysan5/raylib) binding for the
[Goose](https://github.com/aardappel/goose) language, generated from raylib's
own headers.

![the demo running](docs/demo.png)

Works today: **928 functions** from `raylib.h`, `raymath.h` and `rlgl.h`,
**40 structs**, **~530 constants**, plus string-taking overloads of the calls that need a C string.
Goose calls raylib's C functions directly — there is no marshalling layer at
runtime, only the C adapters listed below.

Pinned to raylib `8413b068` (v6.5-dev), built from the `vendor/raylib` submodule,
and tested with Goose `v2026.3-252-g2ed1a63d`.

## Platforms

Raylib itself is compiled from the submodule by the package's CMake target, so
its per-platform link dependencies (winmm/gdi32/opengl32 on Windows, the
Cocoa/IOKit/OpenGL frameworks on macOS, X11/GL on Linux) come along with the
target's link closure. Nothing platform-specific is written in the binding.

| target | what is verified |
|---|---|
| Linux x86-64 | built, all examples run |
| Linux arm64 | `layout_check.c` and `shims.c` compile for the ABI |
| macOS x86-64 / arm64 | `layout_check.c` and `shims.c` compile for the ABI |
| Windows x64 / arm64 (MinGW ABI, LLP64) | `layout_check.c` and `shims.c` compile for the ABI |
| Windows MSVC | same generated C; the MSVC static-assert path is `typedef`-based |
| 32-bit (x86, arm32, RPi 32-bit) | rejected at configure time, `sizeof(void*) != 8` |
| Web, Android, iOS | not supported: different toolchains and asset packaging |

The ABI checks are `just cross-check` (zig, compile only): all 231 `sizeof` and
`offsetof` assertions and every adapter compile against the real headers for
LLP64 Windows and for arm64 macOS/Linux. The part not verified yet is the full
raylib build and link on Windows/macOS — `.github/workflows/ci.yml` does build
Goose, regenerate, build every example and run the headless smoke test on
Ubuntu, Windows and macOS, but it has not run (the repo has no remote yet).

C `long` is the one type whose width differs (8 bytes on LP64, 4 on Windows), so
it never crosses directly: `GetFileModTime` goes through a shim that widens to
`int64_t`, keeping one Goose signature everywhere. `raymath`'s 146 inline
functions get one-line C wrappers, so the binding does not depend on raylib
exporting its inline math symbols.

## Using it

```sh
git clone --recurse-submodules https://github.com/lamweilun/raygoose
```

A program needs one import line; no build file of its own:

```goose
import raylib from "/path/to/raygoose";

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

Inside this repository:

```sh
just demo               # build and run examples/demo.goose
just gen                # regenerate raylib.goose and src/*.c from the headers
```

Examples:

| file | what it covers |
|---|---|
| `examples/basic.goose` | raw API: window, shapes, text, FPS |
| `examples/demo.goose` | ergonomic layer, custom font, formatted text, 24 bouncing balls |
| `examples/hard_cases.goose` | raymath, rlgl, audio, render textures, ray casts, `ffi::cstr` |
| `examples/smoke.goose` | headless: raymath, a padded struct return, the C `long` shim, `ffi::cstr` |

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

C `long` is 8 bytes on Linux/macOS and 4 on Windows, so it never crosses
directly: `GetFileModTime` goes through a shim that widens to `int64_t`, keeping
one Goose signature on every platform. `raymath`'s 146 inline functions get
one-line C wrappers for the same reason.

### The three things that need C

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
   shims. `src/shims.c` holds all of them; 88 of the 928 functions use one.

Everything else is a direct `extern fn` call — the same call the C compiler
would emit.

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

- **Callbacks are not bound.** Goose has no function pointers; `export fn` has a
  C symbol but no addressable value. `SetTraceLogCallback`, the four file
  callbacks and the audio processor callbacks are unreachable without a C
  trampoline per callback. Fixable, not done yet.
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
- **Windows and macOS are not run yet.** Their ABIs compile (`just cross-check`)
  and CI builds them, but every example here has only been built and run on
  Linux x86-64.

## Regenerating

```sh
python3 tools/gen_bindings.py
```

Parses `vendor/raylib/src/{raylib,raymath,rlgl}.h` and rewrites `raylib.goose`,
`src/shims.c` and `src/layout_check.c`. The ergonomic helpers are a fixed block
at the end of the generator, so they survive regeneration. `raymath.h` is read
from its inline definitions; `rlgl.h`'s implementation section is cut off.

Updating raylib: `git -C vendor/raylib checkout <tag> && just gen`, then
build the examples. The layout asserts catch struct changes; new variadic or
callback functions show up as skipped declarations in the generator log.

## Next steps worth doing

1. Callback trampolines: `export fn` hook + a C installer per callback
   (`SetTraceLogCallback` needs `va_list`, so a formatting trampoline).
2. Port `raymath` (146 functions) to Goose. They currently go through one-line
   C wrappers, which is correct but adds a call per operation; Goose's inlining
   would remove it.
3. Slice-based wrappers for the pointer+count pairs (`LoadFontData`,
   `TextSplit`, `DrawTriangleFan`, ...), which are the remaining ergonomic
   rough edge.
4. Split the generated file per module (core/shapes/textures/text/models/audio/
   rlgl) once Goose's multi-file package story matters for compile time.
5. `raygui` and `physac` on the same generator; both are single-header C.
