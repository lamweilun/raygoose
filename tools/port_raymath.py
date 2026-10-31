#!/usr/bin/env python3
"""Port raymath.h to Goose.

raymath is header-only C with no SIMD branches in this version: 146 small
functions over raylib's vector/matrix types. This reads each `RMAPI` definition
and emits the scalar reference implementation as Goose in namespace `raymath`.

Not everything translates mechanically (out-parameters, nested array
initialisers), so HAND has hand-written replacements. `tools/check_raymath.py`
compares the port against the C functions.

Output: raymath.goose
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "vendor" / "raylib" / "src" / "raymath.h"
OUT = ROOT / "raymath.goose"

TYPES = {
    "void": None,
    "float": "f32",
    "int": "i32",
    "bool": "bool",
    "unsigned int": "u32",
    "Vector2": "raylib::Vector2",
    "Vector3": "raylib::Vector3",
    "Vector4": "raylib::Vector4",
    "Quaternion": "raylib::Vector4",  # raylib: typedef Vector4 Quaternion
    "Matrix": "raylib::Matrix",
    "float3": "float3",
    "float16": "float16",
}

KEYWORDS = set("""import namespace struct enum type fn thread_fn export simd
recursive let var extern const pad reusable if else while for in loop block
guard defer match return break continue as true false null self bool varint
i8 i16 i32 i64 u8 u16 u32 u64 f32 f64""".split())

MATHF = {
    "sqrtf": "sqrt",
    "sinf": "sin",
    "cosf": "cos",
    "tanf": "tan",
    "atan2f": "atan2",
    "atanf": "atan",
    "acosf": "acos",
    "asinf": "asin",
    "expf": "exp",
    "logf": "log",
    "powf": "pow",
    "fmodf": "fmod",
    "floorf": "floor",
    "roundf": "round",
    "ceilf": "ceil",
    "fabsf": "absf",
    "fmaxf": "maxf",
    "fminf": "minf",
}

CONSTANTS = """\
let PI: f32 = 3.14159265358979323846;
let DEG2RAD: f32 = 0.017453292519943295;
let RAD2DEG: f32 = 57.29577951308232;
let EPSILON: f32 = 0.000001;

// fabsf/fmaxf/fminf with C's edge cases: fabsf of -0.0 is 0.0, fmaxf/fminf
// return the other operand when one is NaN.
fn absf(x: f32) -> f32 {
    if x < 0.0 { return -x; }
    if x == 0.0 { return 0.0; }
    return x;
}

fn maxf(a: f32, b: f32) -> f32 {
    if a > b { return a; }
    if b > a { return b; }
    if a != a { return b; }
    return a;
}

fn minf(a: f32, b: f32) -> f32 {
    if a < b { return a; }
    if b < a { return b; }
    if a != a { return b; }
    return a;
}
"""

HAND = {
    # Out-parameters and a nested array initialiser: clearer written out.
    "Vector3OrthoNormalize": """\
fn Vector3OrthoNormalize(v1: raylib::Vector3&, v2: raylib::Vector3&) {
    var v = raylib::Vector3 { v1.x, v1.y, v1.z };
    var length = sqrt(v.x*v.x + v.y*v.y + v.z*v.z);
    if length == 0.0 { length = 1.0; }
    var ilength = 1.0/length;
    v1.x = v1.x*ilength;
    v1.y = v1.y*ilength;
    v1.z = v1.z*ilength;

    var vn1 = raylib::Vector3 { v1.y*v2.z - v1.z*v2.y, v1.z*v2.x - v1.x*v2.z, v1.x*v2.y - v1.y*v2.x };
    v = vn1;
    length = sqrt(v.x*v.x + v.y*v.y + v.z*v.z);
    if length == 0.0 { length = 1.0; }
    ilength = 1.0/length;
    vn1.x = vn1.x*ilength;
    vn1.y = vn1.y*ilength;
    vn1.z = vn1.z*ilength;

    v2.x = vn1.y*v1.z - vn1.z*v1.y;
    v2.y = vn1.z*v1.x - vn1.x*v1.z;
    v2.z = vn1.x*v1.y - vn1.y*v1.x;
}
""",
    # A four-way switch: an if/else chain in Goose.
    "QuaternionFromMatrix": """\
fn QuaternionFromMatrix(mat: raylib::Matrix) -> raylib::Vector4 {
    let fourWSquaredMinus1 = mat.m0 + mat.m5 + mat.m10;
    let fourXSquaredMinus1 = mat.m0 - mat.m5 - mat.m10;
    let fourYSquaredMinus1 = mat.m5 - mat.m0 - mat.m10;
    let fourZSquaredMinus1 = mat.m10 - mat.m0 - mat.m5;

    var biggestIndex: i32 = 0;
    var fourBiggestSquaredMinus1 = fourWSquaredMinus1;
    if fourXSquaredMinus1 > fourBiggestSquaredMinus1 {
        fourBiggestSquaredMinus1 = fourXSquaredMinus1;
        biggestIndex = 1;
    }
    if fourYSquaredMinus1 > fourBiggestSquaredMinus1 {
        fourBiggestSquaredMinus1 = fourYSquaredMinus1;
        biggestIndex = 2;
    }
    if fourZSquaredMinus1 > fourBiggestSquaredMinus1 {
        fourBiggestSquaredMinus1 = fourZSquaredMinus1;
        biggestIndex = 3;
    }

    let biggestVal = sqrt(fourBiggestSquaredMinus1 + 1.0)*0.5;
    let mult = 0.25/biggestVal;

    var result = raylib::Vector4 { 0.0, 0.0, 0.0, 0.0 };
    if biggestIndex == 0 {
        result.w = biggestVal;
        result.x = (mat.m6 - mat.m9)*mult;
        result.y = (mat.m8 - mat.m2)*mult;
        result.z = (mat.m1 - mat.m4)*mult;
    } else if biggestIndex == 1 {
        result.x = biggestVal;
        result.w = (mat.m6 - mat.m9)*mult;
        result.y = (mat.m1 + mat.m4)*mult;
        result.z = (mat.m8 + mat.m2)*mult;
    } else if biggestIndex == 2 {
        result.y = biggestVal;
        result.w = (mat.m8 - mat.m2)*mult;
        result.x = (mat.m1 + mat.m4)*mult;
        result.z = (mat.m6 + mat.m9)*mult;
    } else {
        result.z = biggestVal;
        result.w = (mat.m1 - mat.m4)*mult;
        result.x = (mat.m8 + mat.m2)*mult;
        result.y = (mat.m6 + mat.m9)*mult;
    }
    return result;
}
""",
    "MatrixDecompose": """\
fn MatrixDecompose(mat: raylib::Matrix, translation: raylib::Vector3&,
                   rotation: raylib::Vector4&, scale: raylib::Vector3&) {
    let eps: f32 = 0.000000001;

    translation.x = mat.m12;
    translation.y = mat.m13;
    translation.z = mat.m14;

    var cols: raylib::Vector3[3] = [
        raylib::Vector3 { mat.m0, mat.m1, mat.m2 },
        raylib::Vector3 { mat.m4, mat.m5, mat.m6 },
        raylib::Vector3 { mat.m8, mat.m9, mat.m10 },
    ];
    var shear: f32[3] = [0.0; 3];
    var scl = raylib::Vector3 { 0.0, 0.0, 0.0 };

    var stabilizer = eps;
    for i in 3 {
        stabilizer = maxf(stabilizer, absf(cols[i].x));
        stabilizer = maxf(stabilizer, absf(cols[i].y));
        stabilizer = maxf(stabilizer, absf(cols[i].z));
    }
    cols[0] = Vector3Scale(cols[0], 1.0/stabilizer);
    cols[1] = Vector3Scale(cols[1], 1.0/stabilizer);
    cols[2] = Vector3Scale(cols[2], 1.0/stabilizer);

    scl.x = Vector3Length(cols[0]);
    if scl.x > eps { cols[0] = Vector3Scale(cols[0], 1.0/scl.x); }

    shear[0] = Vector3DotProduct(cols[0], cols[1]);
    cols[1] = Vector3Subtract(cols[1], Vector3Scale(cols[0], shear[0]));

    scl.y = Vector3Length(cols[1]);
    if scl.y > eps {
        cols[1] = Vector3Scale(cols[1], 1.0/scl.y);
        shear[0] = shear[0]/scl.y;
    }

    shear[1] = Vector3DotProduct(cols[0], cols[2]);
    cols[2] = Vector3Subtract(cols[2], Vector3Scale(cols[0], shear[1]));
    shear[2] = Vector3DotProduct(cols[1], cols[2]);
    cols[2] = Vector3Subtract(cols[2], Vector3Scale(cols[1], shear[2]));

    scl.z = Vector3Length(cols[2]);
    if scl.z > eps {
        cols[2] = Vector3Scale(cols[2], 1.0/scl.z);
        shear[1] = shear[1]/scl.z;
        shear[2] = shear[2]/scl.z;
    }

    if Vector3DotProduct(cols[0], Vector3CrossProduct(cols[1], cols[2])) < 0.0 {
        scl = Vector3Negate(scl);
        cols[0] = Vector3Negate(cols[0]);
        cols[1] = Vector3Negate(cols[1]);
        cols[2] = Vector3Negate(cols[2]);
    }

    scale = Vector3Scale(scl, stabilizer);

    let rotationMatrix = raylib::Matrix {
        cols[0].x, cols[1].x, cols[2].x, 0.0,
        cols[0].y, cols[1].y, cols[2].y, 0.0,
        cols[0].z, cols[1].z, cols[2].z, 0.0,
        0.0, 0.0, 0.0, 1.0,
    };
    rotation = QuaternionFromMatrix(rotationMatrix);
}
""",
}


def clean(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def parse(text):
    pat = re.compile(r"^RMAPI\s+([^\n{]+?)\s*\(([^)]*)\)\s*\n\{", re.M)
    out = []
    for m in pat.finditer(text):
        head, params = m.group(1).strip(), m.group(2).strip()
        hm = re.match(r"(.+?)\s*(\*?)\s*(\w+)$", head)
        ret = hm.group(1).strip() + (" *" if hm.group(2) else "")
        name = hm.group(3)
        start = m.end() - 1
        depth, j = 0, start
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append({"ret": ret, "name": name, "params": params,
                    "body": text[start + 1:j]})
    return out


def parse_params(text):
    if not text or text.strip() == "void":
        return []
    ps = []
    for raw in split_top(text, ","):
        raw = raw.strip()
        pm = re.match(r"(.+?)\s*(\*?)\s*(\w+)$", raw)
        ty = " ".join(pm.group(1).split())
        ps.append({"type": ty, "name": pm.group(3), "ptr": bool(pm.group(2))})
    return ps


def split_top(text, sep):
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def gtype(ty, ptr=False):
    ty = ty.replace("const ", "").strip()
    if ty == "void":
        return None
    base = TYPES.get(ty)
    if base is None:
        raise SystemExit(f"port_raymath: unmapped type {ty!r}")
    return base + ("&" if ptr else "")


def expr(e):
    """Translate a C expression to Goose."""
    e = e.replace("->", ".")
    e = re.sub(r"\b(float|int|double|unsigned)\s*\)", ")", e)  # (float)x -> (x)
    e = re.sub(r"\(float\)", "", e)
    for c, g in MATHF.items():
        e = re.sub(r"\b%s\b" % c, g, e)
    e = re.sub(r"\b([0-9]+\.[0-9]*|\.[0-9]+|[0-9]+(?=[eE]))([eE][-+]?[0-9]+)?f\b", r"\1\2", e)
    e = re.sub(r"(\d)f\b", r"\1.0", e)
    return e.strip()


def literal(ty, init):
    """A Goose initialiser for `Type x = init;`."""
    init = init.strip()
    if init == "{ 0 }" or init == "{0}":
        if ty in ("f32", "i32", "u32", "bool"):
            return "0"
        return f"default<{ty}>()"
    m = re.match(r"^\{(.*)\}$", init, re.S)
    if m:
        items = [expr(x) for x in split_top(m.group(1), ",") if x.strip()]
        if len(items) == 1:
            return f"default<{ty}>()"
        return f"{ty} {{ {', '.join(items)} }}"
    return expr(init)


def tokenize(text):
    """Split a C body into statements and brace tokens at paren depth zero.

    A `{` right after an `=` starts a struct/array initialiser and is kept
    inside the statement instead of being a block brace.
    """
    out, cur, depth, lit = [], "", 0, 0
    for ch in text:
        if ch == "\n":
            ch = " "
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "{" and depth == 0 and lit == 0 and not cur.rstrip().endswith("="):
            if cur.strip():
                out.append(cur.strip())
            out.append("{")
            cur = ""
            continue
        if ch == "{" and depth == 0:
            lit += 1
            cur += ch
            continue
        if ch == "}" and depth == 0 and lit > 0:
            lit -= 1
            cur += ch
            continue
        if depth == 0 and ch in ";{}" and lit == 0:
            if cur.strip():
                out.append(cur.strip())
            if ch != ";":
                out.append(ch)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def if_parts(t):
    """(kind, condition, rest) for a token that starts an if/else statement."""
    if t == "else":
        return "else", "", ""
    m = re.match(r"^else\s+if\b", t)
    if m:
        kind, rest = "elseif", t[m.end():].lstrip()
    elif t.startswith("if"):
        kind, rest = "if", t[2:].lstrip()
    else:
        return None
    if not rest.startswith("("):
        return None
    depth = 0
    for i, ch in enumerate(rest):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return kind, rest[1:i], rest[i + 1:].strip()
    return None


def reindent(lines):
    out, depth = [], 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("}"):
            depth -= 1
        out.append("    " * depth + line)
        if line.endswith("{"):
            depth += 1
    return "\n".join(out)


def translate(fn):
    ret = gtype(fn["ret"])
    params = parse_params(fn["params"])

    text = clean(fn["body"])
    # keep the scalar branch of an SSE alternative
    text = re.sub(r"#if defined\(RAYMATH_SSE_ENABLED\).*?#else(.*?)#endif", r"\1", text, flags=re.S)
    text = re.sub(r"^[ \t]*#.*$", "", text, flags=re.M)
    toks = tokenize(text)

    # A C parameter is a writable local; a Goose parameter is not. Copy the
    # ones the body assigns, and take the originals under a distinct name.
    assigned = set()
    for tok in toks:
        am = re.match(r"^(\w+)\s*[-+*/]?=", tok)
        if am:
            assigned.add(am.group(1))
    copies = []
    for p in params:
        if p["name"] in assigned:
            copies.append(f"var {p['name']} = {p['name']}_in;")
            p["name"] = p["name"] + "_in"
    ps = ", ".join(f"{p['name']}: {gtype(p['type'], p['ptr'])}" for p in params)
    sig = f"fn {fn['name']}({ps})" + (f" -> {ret}" if ret else "")

    body = list(copies)
    chain = None  # index of a brace-less if's closing `}`, for else-if
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else ""

        if t == "}":
            body.append("}")
            chain = None
            i += 1
            continue
        if t == "{":
            i += 1
            continue

        m = re.match(r"^for\s*\(\s*int\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\w+)\s*;\s*\w+\+\+\s*\)$", t)
        if m:
            body.append(f"for i in {m.group(1)} {{")
            chain = None
            i += 2 if nxt == "{" else 1
            continue

        parts = if_parts(t)
        if parts:
            kind, cond, rest = parts
            if kind == "if":
                head = f"if {expr(cond)} {{"
            elif kind == "elseif":
                head = (f"}} else if {expr(cond)} {{" if chain is not None
                        else f"else if {expr(cond)} {{")
            else:
                head = "} else {" if chain is not None else "else {"
            if kind != "if" and chain is not None:
                body[chain] = head
                chain = None
            else:
                body.append(head)
            if rest:
                body.extend(translate_stmt(rest))
                body.append("}")
                chain = len(body) - 1
                i += 1
            else:
                if nxt != "{":
                    raise SystemExit(f"port_raymath: dangling {t!r} in {fn['name']}")
                i += 2
            continue

        body.extend(translate_stmt(t))
        chain = None
        i += 1

    # a local may be named after a Goose keyword (`float fn = ...`)
    declared = set()
    for line in body:
        dm = re.match(r"var\s+(\w+)\s*:", line)
        if dm:
            declared.add(dm.group(1))
    declared.update(p["name"] for p in params)
    for name in declared & KEYWORDS:
        body = [re.sub(r"\b%s\b" % name, name + "_", line) for line in body]
    return sig + " {\n" + reindent(body) + "\n}\n"


def translate_stmt(t):
    """Translate one C statement into zero or more Goose lines."""
    t = t.strip().rstrip(";").strip()
    if not t:
        return []

    m = re.match(r"^return$", t)
    if m:
        return ["return;"]
    m = re.match(r"^return\s+(.+)$", t)
    if m:
        return [f"return {expr(m.group(1))};"]

    # declaration
    m = re.match(r"^([A-Za-z_][\w ]*?)\s+(\w+)\s*(\[[^\]]*\])?\s*=\s*(.+)$", t)
    if m:
        ty_raw, name, arr, init = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
        ty = gtype(ty_raw)
        if arr:
            count = arr.strip("[]")
            if init.strip() in ("{ 0 }", "{0}"):
                zero = "0.0" if ty == "f32" else f"default<{ty}>()"
                return [f"var {name}: {ty}[{count}] = [{zero}; {count}];"]
            return [f"var {name}: {ty}[{count}] = {literal(ty, init)};"]
        # `float a = x, b = y;` declares several names
        parts = [x.strip() for x in split_top(init, ",")]
        decls = [(name, parts[0])]
        for extra in parts[1:]:
            em = re.match(r"^(\w+)\s*=\s*(.+)$", extra)
            if not em:
                raise SystemExit(f"port_raymath: bad declarator {extra!r}")
            decls.append((em.group(1), em.group(2)))
        out = []
        for nm, value in decls:
            out.extend(decl_lines(ty, nm, value))
        return out

    # assignment / compound assignment
    m = re.match(r"^(\*?[\w.\[\]]+)\s*([-+*/]?=)\s*(.+)$", t)
    if m:
        lhs, op, rhs = m.group(1).replace("->", "."), m.group(2), m.group(3)
        if lhs.startswith("*"):
            lhs = lhs[1:]
        if op != "=":
            return [f"{lhs} = {lhs} {op[0]} {expr(rhs)};"]
        tern = split_ternary(rhs)
        if tern:
            cond, a, b = tern
            return [f"if {expr(cond)} {{ {lhs} = {expr(a)}; }} else {{ {lhs} = {expr(b)}; }}"]
        return [f"{lhs} = {expr(rhs)};"]

    if re.match(r"^[\w.]+\(.*\)$", t):
        return [expr(t) + ";"]
    raise SystemExit(f"port_raymath: cannot translate {t!r}")


def split_ternary(init):
    """Split a top-level `c ? a : b` (no nesting in raymath)."""
    depth = 0
    q = -1
    for i, ch in enumerate(init):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "?" and depth == 0:
            q = i
        elif ch == ":" and depth == 0 and q >= 0:
            cond = init[:q].strip()
            while cond.startswith("(") and cond.endswith(")"):
                cond = cond[1:-1].strip()
            return cond, init[q + 1:i].strip(), init[i + 1:].strip()
    return None


def decl_lines(ty, name, init):
    tern = split_ternary(init)
    if tern:
        cond, a, b = tern
        out = [f"var {name}: {ty} = {fallback(ty, b)};"]
        out.append(f"if {expr(cond)} {{ {name} = {expr(a)}; }} else {{ {name} = {expr(b)}; }}")
        return out
    if ty == "i32" and re.search(r"(<=|>=|==|!=|&&|\|\|)", init):
        # C idiom: `int eq = a <= b && ...;` — a bool stored as 0/1
        return [f"var {name}: i32 = 0;", f"if {expr(init)} {{ {name} = 1; }}"]
    return [f"var {name}: {ty} = {literal(ty, init)};"]


def fallback(ty, e):
    e = expr(e)
    if ty in ("f32", "i32", "u32"):
        return e
    if ty == "bool":
        return e
    return e


def main():
    text = SRC.read_text()
    funcs = parse(text)
    if len(funcs) != 146:
        print(f"port_raymath: expected 146 functions, found {len(funcs)}", file=sys.stderr)
    out = [
        "// Generated by tools/port_raymath.py from vendor/raylib/src/raymath.h.",
        "// raymath's scalar reference implementation, ported to Goose: no C of",
        "// raymath is linked. libm comes in through the math module.",
        "namespace raymath;",
        "",
        "import math;",
        "",
        "struct float3 { v: f32[3] }",
        "struct float16 { v: f32[16] }",
        "",
        CONSTANTS,
    ]
    for fn in funcs:
        if fn["name"] in HAND:
            out.append(HAND[fn["name"]])
            continue
        out.append(translate(fn))
    OUT.write_text("\n".join(out))
    print(f"port_raymath: {len(funcs)} functions, {len(HAND)} hand-written -> {OUT.name}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
