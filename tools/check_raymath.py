#!/usr/bin/env python3
"""Compare the Goose port of raymath against the C library.

Builds two programs from the same signatures — one calls raylib's compiled
raymath, one calls raymath::* — runs both with the same deterministic inputs and
diffs the results. Prints mismatches and exits non-zero if any differ.

    python3 tools/check_raymath.py
"""

import glob
import struct
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(os.environ.get("TMPDIR", "/tmp/opencode")) / "raymath_check"
SRC = ROOT / "vendor" / "raylib" / "src"

spec = importlib.util.spec_from_file_location("pr", ROOT / "tools" / "port_raymath.py")
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)

FLOATS = [1.5, -2.25, 0.5, 3.0, 0.125, 2.0, 0.75, -1.0]
INTS = [3, 4, 2]
MATRIX = ("{ 2.0f, 0.0f, 0.0f, 0.0f,  0.0f, 2.0f, 0.0f, 0.0f,  "
          "0.0f, 0.0f, 2.0f, 0.0f,  3.0f, 4.0f, 5.0f, 1.0f }")


def values(ty, k):
    """C literal and Goose literal for parameter k of type ty."""
    ty = ty.replace("const ", "").strip()
    if ty == "float":
        v = FLOATS[k % len(FLOATS)]
        return f"{v}f", f"{v}"
    if ty == "int":
        return str(INTS[k % len(INTS)]), str(INTS[k % len(INTS)])
    if ty == "bool":
        return "true", "true"
    if ty == "Vector2":
        a, b = FLOATS[k % 8], FLOATS[(k + 3) % 8]
        return f"(Vector2){{ {a}f, {b}f }}", f"raylib::Vector2 {{ {a}, {b} }}"
    if ty == "Vector3":
        a, b, c = FLOATS[k % 8], FLOATS[(k + 3) % 8], FLOATS[(k + 5) % 8]
        return (f"(Vector3){{ {a}f, {b}f, {c}f }}",
                f"raylib::Vector3 {{ {a}, {b}, {c} }}")
    if ty == "Vector4" or ty == "Quaternion":
        a = FLOATS[k % 8]
        return (f"(Vector4){{ {a}f, 0.5f, -0.5f, 0.75f }}",
                f"raylib::Vector4 {{ {a}, 0.5, -0.5, 0.75 }}")
    if ty == "Matrix":
        return "(Matrix)" + MATRIX, ("raylib::Matrix { 2.0, 0.0, 0.0, 0.0,  0.0, 2.0, 0.0, 0.0,  "
                        "0.0, 0.0, 2.0, 0.0,  3.0, 4.0, 5.0, 1.0 }")
    raise SystemExit(f"check_raymath: no value for {ty}")


def show_c(ty, expr):
    ty = ty.replace("const ", "").strip()
    if ty == "float":
        return f'printf("%.9g ", (double){expr});'
    if ty == "int":
        return f'printf("%d ", {expr});'
    if ty == "bool":
        return f'printf("%d ", (int){expr});'
    if ty in ("Vector2", "Vector3", "Vector4", "Quaternion"):
        fields = {"Vector2": "xy", "Vector3": "xyz",
                  "Vector4": "xyzw", "Quaternion": "xyzw"}[ty]
        return " ".join(f'printf("%.9g ", (double){expr}.{f});' for f in fields)
    if ty in ("float3", "float16"):
        n = 3 if ty == "float3" else 16
        return " ".join(f'printf("%.9g ", (double){expr}.v[{i}]);' for i in range(n))
    if ty == "Matrix":
        return " ".join(f'printf("%.9g ", (double){expr}.m{i});' for i in range(16))
    raise SystemExit(f"check_raymath: no printer for {ty}")


def gvals(ty, expr):
    """Goose expressions for the components of a value."""
    ty = ty.replace("const ", "").strip()
    if ty in ("float", "int", "bool"):
        return [expr]
    if ty in ("Vector2", "Vector3", "Vector4", "Quaternion"):
        fields = {"Vector2": "xy", "Vector3": "xyz",
                  "Vector4": "xyzw", "Quaternion": "xyzw"}[ty]
        return [f"{expr}.{f}" for f in fields]
    if ty in ("float3", "float16"):
        n = 3 if ty == "float3" else 16
        return [f"{expr}.v[{i}]" for i in range(n)]
    if ty == "Matrix":
        return [f"{expr}.m{i}" for i in range(16)]
    raise SystemExit(f"check_raymath: no printer for {ty}")


def gprint(name, vals):
    """One print call, because print is line-oriented in Goose."""
    if not vals:
        return 'print("' + name + ' ");'
    return 'print("' + name + ' ", ' + ', " ", '.join(vals) + ');'


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    funcs = pr.parse(SRC.joinpath("raymath.h").read_text())
    cs, gs = [], []
    for fn in funcs:
        ret = fn["ret"].replace("const ", "").strip()
        params = pr.parse_params(fn["params"])
        # skip the hand-written signatures' pointer parameters? no: they work too
        name = fn["name"]
        cdecls, cargs = [], []
        gdecls, gargs = [], []
        cshow, gshow = [], []
        for k, p in enumerate(params):
            cval, gval = values(p["type"], k)
            if p["ptr"]:
                cdecls.append(f'{p["type"].replace("const ", "")} p{k} = {cval};')
                cargs.append(f"&p{k}")
                gdecls.append(f'var p{k}: {pr.gtype(p["type"])} = {gval};')
                gargs.append(f"p{k}")
                cshow.append(show_c(p["type"], f"p{k}"))
                gshow.extend(gvals(p["type"], f"p{k}"))
            else:
                cargs.append(cval)
                gargs.append(gval)
        call_c = f"{name}({', '.join(cargs)})"
        if ret == "void":
            cs.append("{ " + " ".join(cdecls) + f" {call_c}; "
                      + " ".join(cshow) + f'printf("\\n"); }}')
            gs.append("{\n  " + "\n  ".join(gdecls) + f"\n  raymath::{name}({', '.join(gargs)});\n  "
                      + gprint(name, gshow) + "\n}")
        else:
            cret = ret
            cs.append("{ " + " ".join(cdecls) + f" {cret} r = {call_c}; "
                      + show_c(ret, "r") + f'printf("\\n"); }}')
            gs.append("{\n  " + "\n  ".join(gdecls) + f"\n  let r = raymath::{name}({', '.join(gargs)});\n  "
                      + gprint(name, gvals(ret, "r") + gshow) + "\n}")
        # a marker so both outputs line up
        cs[-1] = cs[-1].replace("{ ", '{ printf("%s ", "' + name + '"); ', 1)

    csrc = ("#include \"raylib.h\"\n#include \"raymath.h\"\n#include <stdio.h>\n"
            "int main(void) {\n" + "\n".join(cs) + "\nreturn 0;\n}\n")
    gsrc = ("import raylib from \"" + str(ROOT) + "\";\n\nfn main() {\n"
            + "\n".join(gs) + "\n}\n")
    (TMP / "ref.c").write_text(csrc)
    (TMP / "port.goose").write_text(gsrc)

    libs = sorted(glob.glob(str(Path.home() / ".goose/build/pkg/local/*/*/cmake/pkg/raylib_build/raylib/libraylib.a")),
                  key=os.path.getmtime)
    if not libs:
        raise SystemExit("check_raymath: no libraylib.a; build an example first")
    cc = os.environ.get("CC", "cc")
    cbin = TMP / "ref"
    subprocess.run([cc, "-O1", "-I", str(SRC), str(TMP / "ref.c"), "-o", str(cbin),
                    libs[-1], "-lm", "-lpthread", "-ldl", "-lrt", "-lX11"], check=True)
    subprocess.run(["goose", "build", str(TMP / "port.goose")], check=True,
                   cwd=TMP)

    cout = subprocess.run([str(cbin)], capture_output=True, text=True, check=True).stdout
    gout = subprocess.run([str(TMP / "port")], capture_output=True, text=True, check=True).stdout
    return compare(cout.splitlines(), gout.splitlines())


def number(tok):
    tok = tok.strip()
    if tok in ("true", "false"):
        return 1.0 if tok == "true" else 0.0
    if tok in ("inf", "-inf", "nan", "-nan"):
        return float(tok.replace("nan", "NaN").replace("-NaN", "NaN"))
    try:
        return float(tok)
    except ValueError:
        raise SystemExit(f"check_raymath: not a number: {tok!r}")


def as_f32(x):
    return struct.unpack("f", struct.pack("f", x))[0]


def close(a, b):
    """Same C float, allowing for the two sides printing different digits."""
    if a != a and b != b:
        return True
    if a in (float("inf"), float("-inf")) or b in (float("inf"), float("-inf")):
        return a == b
    tol = float(os.environ.get("RAYMATH_TOL", "0"))
    if tol == 0:
        return as_f32(a) == as_f32(b)
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def compare(cl, gl):
    if len(cl) != len(gl):
        print(f"line counts differ: C {len(cl)}, Goose {len(gl)}")
    bad = 0
    for i, (c, g) in enumerate(zip(cl, gl)):
        ct, gt = c.split(), g.split()
        if not ct or not gt:
            continue
        if ct[0] != gt[0]:
            print(f"line {i}: {ct[0]} vs {gt[0]}")
            bad += 1
            continue
        cv, gv = ct[1:], gt[1:]
        if len(cv) != len(gv):
            print(f"{ct[0]}: {len(cv)} values vs {len(gv)}")
            bad += 1
            continue
        for j, (a, b) in enumerate(zip(cv, gv)):
            if not close(number(a), number(b)):
                print(f"{ct[0]} value {j}: C {a} vs Goose {b}")
                bad += 1
    print(f"check_raymath: {len(cl)} functions, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
