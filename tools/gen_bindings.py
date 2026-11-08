#!/usr/bin/env python3
"""Generate the Goose binding for raylib from the vendored C headers.

Outputs (all generated, do not edit):
  raylib.goose        structs, constants, extern declarations and shims' wrappers
  src/shims.c         C adapters for variadics, padded structs and callbacks
  src/layout_check.c  static asserts that the generator's layout model matches C

Model (docs/reference.md section 24, docs/goose_spec.md 7.10):
  * scalars cross by value; `T&` crosses as `T*`; pointers to C-owned memory are u64.
  * Goose structs are packed, so C padding is written as `pad n`.
  * A struct that contains pad cannot cross by value, so it gets a shim that
    takes or returns it through a pointer.
  * C variadics cannot be bound, so they get fixed-arity shims.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "vendor" / "raylib" / "src"

OUT_GOOSE = ROOT / "raylib.goose"
OUT_SHIMS = ROOT / "src" / "shims.c"
OUT_LAYOUT = ROOT / "src" / "layout_check.c"

KEYWORDS = set("""import namespace struct enum type fn thread_fn export simd
recursive let var extern const pad reusable if else while for in loop block
guard defer match return break continue as true false null self bool varint
i8 i16 i32 i64 u8 u16 u32 u64 f32 f64""".split())

SCALARS = {
    "bool": ("bool", 1, 1),
    "char": ("u8", 1, 1),
    "signed char": ("i8", 1, 1),
    "unsigned char": ("u8", 1, 1),
    "short": ("i16", 2, 2),
    "short int": ("i16", 2, 2),
    "unsigned short": ("u16", 2, 2),
    "unsigned short int": ("u16", 2, 2),
    "int": ("i32", 4, 4),
    "signed": ("i32", 4, 4),
    "signed int": ("i32", 4, 4),
    "unsigned": ("u32", 4, 4),
    "unsigned int": ("u32", 4, 4),
    "long": ("i64", 8, 8),
    "long int": ("i64", 8, 8),
    "unsigned long": ("u64", 8, 8),
    "long long": ("i64", 8, 8),
    "unsigned long long": ("u64", 8, 8),
    "float": ("f32", 4, 4),
    "double": ("f64", 8, 8),
    "size_t": ("u64", 8, 8),
    "int64_t": ("i64", 8, 8),
    "uint64_t": ("u64", 8, 8),
}

PTR = 8  # 64-bit targets only; see the guard in layout_check.c

# C `long` is 8 bytes on LP64 (Linux, macOS) and 4 on Windows LLP64, so it
# never crosses directly: the shim widens to int64_t/uint64_t.
LONG_TYPES = {"long": "i64", "unsigned long": "u64"}


def goose_name(name):
    return name + "_" if name in KEYWORDS else name


class Type:
    """A C type, resolved enough to map to Goose and compute a layout."""

    def __init__(self, text, structs, enums):
        self.text = text
        self.const = False
        self.ptr = 0
        t = " ".join(text.split())
        # peel qualifiers
        while True:
            t2 = re.sub(r"^(const|volatile|register|static|inline)\s+", "", t)
            t2 = re.sub(r"\s+(const|volatile)$", "", t2)
            if t2 == t:
                break
            if t.startswith("const") or " const " in " " + t + " ":
                self.const = True
            t = t2.strip()
        if t.startswith("const "):
            self.const = True
            t = t[6:].strip()
        while t.endswith("*"):
            self.ptr += 1
            t = t[:-1].strip()
        if t.startswith("struct "):
            t = t[7:].strip()
        if t.startswith("enum "):
            t = t[5:].strip()
        self.base = t
        # resolve pointer typedefs (ModelAnimPose = Transform *)
        if self.ptr == 0 and t in structs:
            target = structs[t]
            if target.alias_of is not None:
                self.base = target.alias_of
        # aliases such as Texture2D = Texture
        seen = set()
        while self.ptr == 0 and self.base in structs and structs[self.base].alias_of and self.base not in seen:
            seen.add(self.base)
            self.base = structs[self.base].alias_of

    def size(self, structs):
        if self.ptr:
            return PTR
        if self.base in SCALARS:
            return SCALARS[self.base][1]
        if self.base in structs:
            return structs[self.base].size
        return PTR  # unknown C type (function pointer typedef): an opaque word

    def align(self, structs):
        if self.ptr:
            return PTR
        if self.base in SCALARS:
            return SCALARS[self.base][2]
        if self.base in structs:
            return structs[self.base].align
        return PTR

    def goose(self, structs):
        """Goose type for a value of this type (not a reference)."""
        if self.ptr:
            return "u64"
        if self.base in SCALARS:
            return SCALARS[self.base][0]
        if self.base in structs:
            return self.base
        return "u64"  # function pointer typedef: an opaque token


class Struct:
    def __init__(self, name):
        self.name = name
        self.alias_of = None  # pointer or value alias target
        self.fields = []  # (c_type_text, name, array_len or 0)
        self.size = 0
        self.align = 1
        self.pads = []  # goose pad sizes, for reference
        self.goose_size = 0
        self.padded = False

    def layout(self, structs):
        off = 0
        max_align = 1
        self.offsets = []
        for text, _, count in self.fields:
            ty = Type(text, structs, None)
            a = ty.align(structs)
            s = ty.size(structs)
            if count:
                s *= count
            off = (off + a - 1) // a * a
            self.offsets.append(off)
            off += s
            max_align = max(max_align, a)
        self.align = max_align
        self.size = (off + max_align - 1) // max_align * max_align


def parse(path, structs, funcs, enums, defines):
    src = path.read_text()
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S | re.I)
    src = re.sub(r"//[^\n]*", " ", src)
    # rlgl.h declares its functions and carries the implementation below a
    # guard at the end: drop it.
    markers = list(re.finditer(r"#if\s+defined\(([A-Z_]+)_IMPLEMENTATION\)", src))
    if markers:
        src = src[:markers[-1].start()]
    # constants first, while the #defines are still there
    for m in re.finditer(r"^[ \t]*#define[ \t]+([A-Z][A-Z0-9_]*)[ \t]+(.+)$", src, re.M):
        name, value = m.group(1), m.group(2).strip()
        if "(" in name or "\\" in value:
            continue
        defines.append((name, value))
    # Keep the first branch of every conditional (the desktop OpenGL one) and
    # drop the directives: duplicate fields are dropped by name below.
    src = re.sub(r"^[ \t]*#.*$", "", src, flags=re.M)

    # struct bodies
    for m in re.finditer(r"typedef\s+struct\s*(\w*)\s*\{(.*?)\}\s*(\w+)\s*;", src, re.S):
        tag, body, name = m.group(1), m.group(2), m.group(3)
        st = structs.setdefault(name, Struct(name))
        st.source = path.name
        st.fields = parse_fields(body)
        if tag and tag != name:
            st.tag = tag
    # forward declarations and plain aliases
    for m in re.finditer(r"typedef\s+(struct\s+)?(\w+)\s+(\w+)\s*;", src):
        tag, target, name = m.group(1), m.group(2), m.group(3)
        if name in structs and structs[name].fields:
            continue
        st = structs.setdefault(name, Struct(name))
        st.alias_of = target
        if tag:
            st.opaque = True
    # enums
    for m in re.finditer(r"typedef\s+enum\s*\w*\s*\{(.*?)\}\s*(\w+)\s*;", src, re.S):
        enums.append((m.group(2), parse_enum_body(m.group(1))))
    # function declarations: join to the terminating ;
    for m in re.finditer(r"^[ \t]*(RLAPI|RMAPI)\s+([^;]+);", src, re.M):
        decl = " ".join(m.group(2).split())
        fm = re.match(r"(\w[\w \t*]*?)\s*\**\s*(\w+)\s*\((.*)\)$", decl)
        if not fm:
            print("gen: skipped declaration:", decl[:80], file=sys.stderr)
            continue
        ret_text, fname, params = fm.group(1).strip(), fm.group(2), fm.group(3).strip()
        raw_ret = decl[: decl.rindex(fname)].strip()
        funcs.append({
            "raw": decl,
            "ret": raw_ret,
            "name": fname,
            "params": parse_params(params),
        })



def parse_fields(body):
    fields = []
    for stmt in split_top(body, ";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        # split "type a, b[2], *c" into type + declarators
        m = re.match(
            r"(.+?)\s+((?:\*+\s*)?[A-Za-z_]\w*(?:\s*\[[^\]]*\])?"
            r"(?:\s*,\s*(?:\*+\s*)?[A-Za-z_]\w*(?:\s*\[[^\]]*\])?)*)$", stmt)
        if not m:
            print("gen: bad field:", stmt, file=sys.stderr)
            continue
        base = m.group(1).strip()
        decls = m.group(2).strip()
        for decl in decls.split(","):
            decl = decl.strip()
            pm = re.match(r"(\*+)?\s*([A-Za-z_]\w*)\s*(?:\[([^\]]*)\])?$", decl)
            if not pm:
                print("gen: bad declarator:", decl, file=sys.stderr)
                continue
            stars, name, count = pm.group(1) or "", pm.group(2), pm.group(3)
            if any(f[1] == name for f in fields):
                continue  # a preprocessor branch's duplicate
            ty = base + (" " + stars.strip() if stars else "")
            fields.append((ty, name, int(count) if count and count.isdigit() else 0))
    return fields


def parse_params(text):
    if not text or text.strip() == "void":
        return []
    params = []
    for p in split_top(text, ","):
        p = p.strip()
        if not p:
            continue
        if p == "...":
            params.append({"name": "...", "type": "...", "vararg": True})
            continue
        pm = re.match(r"(.+?)([A-Za-z_]\w*)\s*(?:\[([^\]]*)\])?$", p)
        if not pm:
            print("gen: bad param:", p, file=sys.stderr)
            params.append({"name": "?", "type": p, "vararg": False})
            continue
        ty, name, count = pm.group(1).strip(), pm.group(2), pm.group(3)
        if count is not None:
            ty = ty + " *"
        params.append({"name": name, "type": ty, "vararg": False, "array": count})
    return params


def split_top(text, sep):
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def parse_enum_body(body):
    items = []
    value = -1
    for part in split_top(body, ","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, expr = part.split("=", 1)
            value = eval_c(expr.strip(), items)
        else:
            name, value = part, value + 1
        items.append((name.strip(), value))
    return items


def eval_c(expr, known):
    expr = expr.strip()
    for name, val in known:
        expr = re.sub(r"\b%s\b" % re.escape(name), str(val), expr)
    expr = expr.replace("U", "").replace("L", "")
    expr = re.sub(r"\(\s*(\w+)\s*\)", r"\1", expr)  # (int) casts
    expr = re.sub(r"\b0x([0-9a-fA-F]+)\b", lambda m: str(int(m.group(1), 16)), expr)
    expr = expr.replace("<<", "<<").replace("|", "|")
    try:
        return int(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return 0


def goose_struct(st, structs):
    parts = []
    g_off = 0
    for (text, name, count), c_off in zip(st.fields, st.offsets):
        ty = Type(text, structs, None)
        if c_off > g_off:
            parts.append(f"pad {c_off - g_off}")
            g_off = c_off
        elif c_off < g_off:
            raise SystemExit(f"gen: layout conflict in {st.name}.{name}: c={c_off} goose={g_off}")
        gsize = ty.size(structs) * (count or 1)
        gt = ty.goose(structs)
        if count:
            gt = f"{gt}[{count}]"
        parts.append(f"{goose_name(name)}: {gt}")
        g_off += gsize
    if st.size > g_off:
        parts.append(f"pad {st.size - g_off}")
        g_off = st.size
    body = ",\n".join("    " + p for p in parts)
    st.goose_size = g_off
    st.pads = [p for p in parts if p.startswith("pad")]
    st.padded = bool(st.pads)
    return f"struct {st.name} {{\n{body}\n}}"



GOOSE_EXTRAS = """
// ------------------------------ ergonomics
// raylib wants NUL-terminated C strings. These overloads of the raylib names
// take a Goose slice and put the terminator right after the call, so
// `DrawText(\"hi\", 10, 10, 20, WHITE)` and `DrawText(t[0], ...)` both work.

extern fn rg_load_font_path(path: const u8&, size: i32) -> Font = \"rg_load_font_path\";

fn InitWindow(width: i32, height: i32, title: const u8[:]) {
    let t = str(title, \"\\0\");
    InitWindow(width, height, t[0]);
}
fn DrawText(text: const u8[:], x: i32, y: i32, size: i32, tint: Color) {
    let t = str(text, \"\\0\");
    DrawText(t[0], x, y, size, tint);
}
fn DrawTextEx(font: Font, text: const u8[:], position: Vector2, size: f32, spacing: f32, tint: Color) {
    let t = str(text, \"\\0\");
    DrawTextEx(font, t[0], position, size, spacing, tint);
}
fn MeasureText(text: const u8[:], size: i32) -> i32 {
    let t = str(text, \"\\0\");
    return MeasureText(t[0], size);
}
fn MeasureTextEx(font: Font, text: const u8[:], size: f32, spacing: f32) -> Vector2 {
    let t = str(text, \"\\0\");
    return MeasureTextEx(font, t[0], size, spacing);
}
fn LoadTexture(path: const u8[:]) -> Texture {
    let t = str(path, \"\\0\");
    return LoadTexture(t[0]);
}
fn LoadImage(path: const u8[:]) -> Image {
    let t = str(path, \"\\0\");
    return LoadImage(t[0]);
}
fn LoadFont(path: const u8[:], fontSize: i32) -> Font {
    let t = str(path, \"\\0\");
    return rg_load_font_path(t[0], fontSize);
}
fn LoadSound(path: const u8[:]) -> Sound {
    let t = str(path, \"\\0\");
    return LoadSound(t[0]);
}
fn LoadMusicStream(path: const u8[:]) -> Music {
    let t = str(path, \"\\0\");
    return LoadMusicStream(t[0]);
}

// ------------------------------ callbacks
// Goose has no function-pointer values, so a raylib callback is a fixed export
// the program defines; the C trampoline in src/callbacks/ calls it. A program
// that installs one must define the matching export:
//
//   export fn raylib_trace_log_callback(level: i32, text: u64)
//   export fn raylib_load_file_data_callback(file_name: u64) -> const u8[:]
//   export fn raylib_save_file_data_callback(file_name: u64, data: u64, data_size: i32) -> bool
//   export fn raylib_load_file_text_callback(file_name: u64) -> const u8[:]
//   export fn raylib_save_file_text_callback(file_name: u64, text: u64) -> bool
//
// A setter whose export the program does not define installs nothing and says
// so on stderr: `goose run` cannot bind exports at all (the package's library
// loads before the program is compiled into the same process), so a program
// that installs a callback needs `goose build`.
//
// C strings arrive as u64 and are valid only during the call; read them with
// ffi::cstr or ffi::bytes. Returned slices are copied before the trampoline
// returns, so a global buffer is enough. The audio processor callbacks are not
// bound: raylib runs them on the mixer thread and they edit the buffer in
// place.

extern fn rg_set_trace_log_callback() = \"rg_set_trace_log_callback\";
fn SetTraceLogCallback() { rg_set_trace_log_callback(); }

extern fn rg_set_load_file_data_callback() = \"rg_set_load_file_data_callback\";
fn SetLoadFileDataCallback() { rg_set_load_file_data_callback(); }

extern fn rg_set_save_file_data_callback() = \"rg_set_save_file_data_callback\";
fn SetSaveFileDataCallback() { rg_set_save_file_data_callback(); }

extern fn rg_set_load_file_text_callback() = \"rg_set_load_file_text_callback\";
fn SetLoadFileTextCallback() { rg_set_load_file_text_callback(); }

extern fn rg_set_save_file_text_callback() = \"rg_set_save_file_text_callback\";
fn SetSaveFileTextCallback() { rg_set_save_file_text_callback(); }
"""

C_EXTRAS = """
Font rg_load_font_path(const char *path, int size) { return LoadFontEx(path, size, NULL, 0); }
"""

class Mapper:
    """Maps C declarations to Goose types and says whether a shim is needed.

    mode is one of:
      "ok"      crosses directly
      "ref"     a struct with C padding: only by reference, through a shim
      "convert" C `long`, whose width differs between LP64 and Windows LLP64:
                the shim takes int64_t/uint64_t and casts, so the Goose
                signature is the same on every platform
    """

    def __init__(self, structs):
        self.structs = structs

    def param(self, p):
        text = p["type"]
        if p["vararg"]:
            return "...", "vararg"
        ty = Type(text, self.structs, None)
        if ty.ptr == 0:
            if ty.base in LONG_TYPES:
                return LONG_TYPES[ty.base], "convert"
            if ty.base in SCALARS:
                return ty.goose(self.structs), "ok"
            st = self.structs.get(ty.base)
            if st is None:
                return "u64", "ok"
            return ty.base, "ok" if not st.padded else "ref"
        if ty.ptr == 1:
            pointee = Type(ty.base, self.structs, None)
            if pointee.base in SCALARS and ty.base not in self.structs:
                g = pointee.goose(self.structs)
                return (f"const {g}&" if ty.const else f"{g}&"), "ok"
            if ty.base == "void" or ty.base == "char":
                return ("const u8&" if ty.const else "u8&"), "ok"
            st = self.structs.get(ty.base)
            if st is not None and st.fields:
                return (f"const {ty.base}&" if ty.const else f"{ty.base}&"), "ok"
            return "u64", "ok"
        return "u64", "ok"

    def ret(self, text):
        t = " ".join(text.split())
        if t in ("void", ""):
            return None, "ok"
        ty = Type(text, self.structs, None)
        if ty.ptr:
            return "u64", "ok"
        if ty.base in LONG_TYPES:
            return LONG_TYPES[ty.base], "convert"
        if ty.base in SCALARS:
            return SCALARS[ty.base][0], "ok"
        st = self.structs.get(ty.base)
        if st is None:
            return "u64", "ok"
        return ty.base, ("out" if st.padded else "ok")


def main():
    structs, funcs, enums, defines = {}, [], [], []
    headers = [ENGINE / "raylib.h", ENGINE / "rlgl.h"]
    for h in headers:
        parse(h, structs, funcs, enums, defines)

    for st in structs.values():
        if st.alias_of is None and st.fields:
            st.layout(structs)

    mapr = Mapper(structs)

    # ---- goose source ----------------------------------------------------
    out = []
    out.append("// Generated by tools/gen_bindings.py from vendor/raylib/src/*.h. Do not edit.")
    out.append("// raylib and rlgl, bound through extern fn (docs/reference.md section 24).")
    out.append("")
    out.append("namespace raylib;")
    out.append("")
    out.append("// raymath is a Goose port; see raymath.goose and tools/port_raymath.py.")
    out.append("import .raymath;")
    out.append("")

    out.append("// ------------------------------- types")
    for name, st in structs.items():
        if st.alias_of is not None:
            continue
        if not st.fields:
            continue
        out.append(goose_struct(st, structs))
        out.append("")

    out.append("// --------------------------- constants")
    seen_consts = set()
    for ename, items in enums:
        out.append(f"// {ename}")
        for name, value in items:
            if value is None or name in ("true", "false"):
                continue
            gname = goose_name(name)
            if gname in seen_consts:
                continue
            seen_consts.add(gname)
            v = value if value >= 0 else value + (1 << 32)
            out.append(f"let {gname}: i32 = {v};")
        out.append("")
    for name, value in defines:
        gname = goose_name(name)
        if gname in seen_consts:
            continue
        seen_consts.add(gname)
        vm = re.match(r"CLITERAL\(\s*Color\s*\)\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}$", value)
        if vm:
            out.append(f"let {gname} = Color {{ {', '.join(vm.groups())} }};")
            continue
        if re.match(r"^-?(0x[0-9a-fA-F]+|\d+)[uUlLfF]*$", value):
            num = re.sub(r"[uUlLfF]+$", "", value)
            if "f" in value[-1:] or "." in num:
                out.append(f"let {gname}: f32 = {num};")
            else:
                out.append(f"let {gname}: i32 = {int(num, 0)};")
        elif re.match(r'^"[^"]*"$', value):
            out.append(f"let {gname}: const u8[:] = {value};")

    out.append("")
    out.append("// --------------------------- externs")
    shims = []      # C code of every adapter
    for f in funcs:
        name = f["name"]
        params = f["params"]
        if any(p["vararg"] for p in params):
            continue  # variadics get hand-written shims below
        ret_goose, ret_mode = mapr.ret(f["ret"])
        mapped = [mapr.param(p) for p in params]
        modes = [m for _, m in mapped]
        if ret_mode == "ok" and all(m == "ok" for m in modes):
            sig = ", ".join(f"{goose_name(p['name'])}: {gt}" for p, (gt, _) in zip(params, mapped))
            r = f" -> {ret_goose}" if ret_goose else ""
            out.append(f"extern fn {name}({sig}){r};")
            continue
        else:
            shim = make_shim(f, mapr, ret_goose, ret_mode, mapped)
        out.append(shim["decl"])
        if shim["wrapper"]:
            out.append(shim["wrapper"])
        shims.append(shim["code"])

    # hand-written variadic shims
    out.append("")
    out.append("// raylib's two variadic functions cannot be bound; these fixed-arity shims")
    out.append("// cover the common cases. Use Goose's own str(...) for formatted text.")
    out.append('extern fn rg_trace_log(level: i32, text: const u8&) = "rg_trace_log";')
    out.append("fn trace_log(level: i32, text: const u8&) { rg_trace_log(level, text); }")
    shims.append('void rg_trace_log(int level, const char *text) { TraceLog(level, "%s", text); }')

    out.append(GOOSE_EXTRAS)
    OUT_GOOSE.write_text("\n".join(out) + "\n")

    # ---- shims.c ---------------------------------------------------------
    c = []
    c.append("// Generated by tools/gen_bindings.py. C adapters raylib needs from Goose:")
    c.append("// variadics, structs that contain C padding, and pointer arguments.")
    c.append('#include "raylib.h"')
    c.append('#include "rlgl.h"')
    c.append("#include <string.h>")
    c.append("#include <stdint.h>")
    c.append("")
    c.extend(shims)
    c.append("")
    c.append(C_EXTRAS)
    OUT_SHIMS.parent.mkdir(parents=True, exist_ok=True)
    OUT_SHIMS.write_text("\n".join(c) + "\n")

    # ---- layout_check.c --------------------------------------------------
    lc = ["// Generated by tools/gen_bindings.py: the C layout the binding assumes.",
          "// Compiled on every target; a mismatch breaks the build, not the frame.",
          '#include "raylib.h"', '#include "rlgl.h"',
          "#include <stddef.h>", "#include <stdint.h>", "#include <stdbool.h>", "",
          "#if defined(_MSC_VER) && !defined(__clang__)",
          "#define RG_ASSERT_JOIN_(a, b) a##b",
          "#define RG_ASSERT_JOIN(a, b) RG_ASSERT_JOIN_(a, b)",
          "#define RG_STATIC_ASSERT(c, m) typedef char RG_ASSERT_JOIN(rg_sa_, __COUNTER__)[(c) ? 1 : -1]",
          "#else",
          "#define RG_STATIC_ASSERT(c, m) _Static_assert(c, m)",
          "#endif",
          "",
          'RG_STATIC_ASSERT(sizeof(void *) == 8, "raygoose needs a 64-bit target");',
          'RG_STATIC_ASSERT(sizeof(bool) == 1, "C bool must be one byte");',
          ""]
    for name, st in structs.items():
        if not st.fields:
            continue
        lc.append(f'RG_STATIC_ASSERT(sizeof({name}) == {st.size}, "sizeof {name}");')
        for (text, fname, count), off in zip(st.fields, st.offsets):
            lc.append(f'RG_STATIC_ASSERT(offsetof({name}, {fname}) == {off}, "{name}.{fname}");')
    OUT_LAYOUT.write_text("\n".join(lc) + "\n")

    print(f"gen: {len([s for s in structs.values() if s.fields])} structs, "
          f"{len(funcs)} functions, {sum(len(i) for _, i in enums)} constants, "
          f"{len(shims)} shims", file=sys.stderr)
    padded = sorted(s.name for s in structs.values() if s.padded)
    print("gen: padded structs:", ", ".join(padded), file=sys.stderr)


def make_shim(f, mapr, ret_goose, ret_mode, mapped):
    """A C adapter for a signature a Goose extern cannot express."""
    name = f["name"]
    symbol = f"rg_{name}"
    cparams, gparams, cargs = [], [], []
    for i, (p, (gt, mode)) in enumerate(zip(f["params"], mapped)):
        pname = goose_name(p["name"])
        ty = Type(p["type"], mapr.structs, None)
        if mode == "ref":
            cparams.append(f"void *p{i}")
            cargs.append("*(%s *)p%d" % (ty.base, i))
            gparams.append(f"{pname}: {ty.base}&")
        elif mode == "convert":
            wide = "int64_t" if ty.base == "long" else "uint64_t"
            cparams.append(f"{wide} p{i}")
            cargs.append(f"({ty.base})p{i}")
            gparams.append(f"{pname}: {gt}")
        else:
            cparams.append(f"{p['type']} {p['name']}")
            cargs.append(p["name"])
            gparams.append(f"{pname}: {gt}")

    wrapper = ""
    if ret_mode == "out":
        cparams.insert(0, "void *out")
        gparams.insert(0, f"out: {ret_goose}&")
        body = [f"    {f['ret']} r = {name}({', '.join(cargs)});",
                "    memcpy(out, &r, sizeof r);"]
        c_ret = "void"
        args = ", ".join(goose_name(p["name"]) for p in f["params"])
        wrapper_sig = ", ".join(f"{goose_name(p['name'])}: {gt}" for p, (gt, _) in zip(f["params"], mapped))
        wrapper = (f"fn {name}({wrapper_sig}) -> {ret_goose} {{\n"
                   f"    var out: {ret_goose} = default<{ret_goose}>();\n"
                   f"    {symbol}(out{', ' + args if args else ''});\n"
                   f"    return out;\n}}")
        decl_ret = ""
        public = symbol
    else:
        if ret_goose is None:
            c_ret = "void"
            body = [f"    {name}({', '.join(cargs)});"]
        elif ret_mode == "convert":
            c_ret = "int64_t" if ret_goose == "i64" else "uint64_t"
            body = [f"    return ({c_ret}){name}({', '.join(cargs)});"]
        else:
            c_ret = f["ret"]
            body = [f"    return {name}({', '.join(cargs)});"]
        decl_ret = f" -> {ret_goose}" if ret_goose else ""
        public = name

    decl = f"extern fn {public}({', '.join(gparams)}){decl_ret} = \"{symbol}\";"
    code = (f"{c_ret} {symbol}({', '.join(cparams)}) {{\n" + "\n".join(body) + "\n}")
    return {"symbol": symbol, "decl": decl, "code": code, "wrapper": wrapper}


if __name__ == "__main__":
    main()
