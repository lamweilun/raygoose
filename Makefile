# Convenience targets. Goose does the building; these just save typing.

.PHONY: all gen check demo basic hard smoke check-math cross-check clean

all: check

# Regenerate the binding and the raymath port from the vendored headers.
gen:
	python3 tools/gen_bindings.py
	python3 tools/port_raymath.py

# Build every example. The first one compiles raylib, later ones reuse it.
check:
	goose build examples/basic.goose
	goose build examples/demo.goose
	goose build examples/hard_cases.goose
	goose build examples/smoke.goose

demo:
	goose run examples/demo.goose

basic:
	goose run examples/basic.goose

hard:
	goose run examples/hard_cases.goose

smoke:
	goose run examples/smoke.goose

# The raymath port against the C library, 146 functions.
check-math:
	python3 tools/check_raymath.py

# The C layer for other ABIs: layouts and adapters without a full raylib build.
# Needs zig in PATH.
cross-check:
	zig cc -target x86_64-windows-gnu -std=c11 -c src/layout_check.c -I vendor/raylib/src -o /tmp/raygoose-layout-win.o
	zig cc -target x86_64-windows-gnu -std=c11 -c src/shims.c -I vendor/raylib/src -o /tmp/raygoose-shims-win.o
	zig cc -target aarch64-macos -std=c11 -c src/layout_check.c -I vendor/raylib/src -o /tmp/raygoose-layout-mac.o
	zig cc -target aarch64-macos -std=c11 -c src/shims.c -I vendor/raylib/src -o /tmp/raygoose-shims-mac.o
	zig cc -target aarch64-linux-gnu -std=c11 -c src/layout_check.c -I vendor/raylib/src -o /tmp/raygoose-layout-arm.o

clean:
	rm -f examples/basic examples/demo examples/hard_cases examples/smoke
