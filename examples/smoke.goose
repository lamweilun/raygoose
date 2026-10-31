import raylib from "..";
import ffi;

// No window: this runs headless on every platform, so CI can execute it.
fn main() {
    // raymath is wrapped in C, so it links wherever raylib builds.
    let sum = raylib::Vector2Add(raylib::Vector2 { 1.0, 2.0 }, raylib::Vector2 { 10.0, 20.0 });
    assert(sum.x == 11.0 && sum.y == 22.0);
    let m = raylib::MatrixTranslate(1.0, 2.0, 3.0);
    assert(m.m12 == 1.0);

    // a padded struct returned by value, through the shim
    let hit = raylib::GetRayCollisionBox(
        raylib::Ray { raylib::Vector3 { 0.0, 0.0, 0.0 }, raylib::Vector3 { 0.0, 0.0, 1.0 } },
        raylib::BoundingBox { raylib::Vector3 { -1.0, -1.0, 5.0 }, raylib::Vector3 { 1.0, 1.0, 7.0 } });
    assert(hit.hit && hit.distance == 5.0);

    // C `long`: 8 bytes on LP64, 4 on Windows; the shim normalizes it to i64
    let mtime = raylib::GetFileModTime(".\0"[0]);
    assert(mtime > 0);

    let cwd = ffi::cstr(raylib::GetWorkingDirectory());
    assert(cwd.len > 0);

    print("smoke ok: ", sum.x, " ", hit.distance, " mtime=", mtime, " cwd=", cwd, "\n");
}
