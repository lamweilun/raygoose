import raylib from "..";
import ffi;

fn main() {
    raylib::InitWindow(640, 360, "hard cases");
    raylib::SetTargetFPS(60);
    raylib::InitAudioDevice();

    // raymath is a header-only library in C, exported by the raylib build.
    let a = raylib::Vector2Add(raylib::Vector2 { 1.0, 2.0 }, raylib::Vector2 { 10.0, 20.0 });
    let m = raylib::MatrixTranslate(1.0, 2.0, 3.0);
    let n = raylib::Vector3Normalize(raylib::Vector3 { 3.0, 4.0, 0.0 });
    print("raymath: ", a.x, " ", a.y, " | ", n.x, " ", n.y, " | m12=", m.m12, "\n");

    // raylib-owned C strings come back as u64 and are copied with ffi::cstr.
    let cwd = ffi::cstr(raylib::GetWorkingDirectory());
    let gpu = ffi::cstr(raylib::GetMonitorName(0));
    print("cwd=", cwd, " monitor=", gpu, "\n");

    // a struct returned by value
    let font = raylib::GetFontDefault();
    print("font: base=", font.baseSize, " glyphs=", font.glyphCount, "\n");

    // an audio stream with no file: AudioStream is padded, so it crosses
    // through the shims both as a return value and as a parameter.
    var stream = raylib::LoadAudioStream(44100, 16, 1);
    print("audio: rate=", stream.sampleRate, " channels=", stream.channels,
          " valid=", raylib::IsAudioStreamValid(stream), "\n");
    raylib::UnloadAudioStream(stream);

    let target = raylib::LoadRenderTexture(320, 180);
    print("render texture id=", target.id, " texture=", target.texture.width, "\n");

    let hit = raylib::GetRayCollisionBox(
        raylib::Ray { raylib::Vector3 { 0.0, 0.0, 0.0 }, raylib::Vector3 { 0.0, 0.0, 1.0 } },
        raylib::BoundingBox { raylib::Vector3 { -1.0, -1.0, 5.0 }, raylib::Vector3 { 1.0, 1.0, 7.0 } });
    print("ray hit=", hit.hit, " distance=", hit.distance, "\n");

    var frames: i32 = 0;
    while frames < 30 {
        raylib::BeginDrawing();
        raylib::ClearBackground(raylib::RAYWHITE);
        raylib::DrawTextEx(font, "custom font", raylib::Vector2 { 20.0, 20.0 }, 32.0, 2.0, raylib::MAROON);
        var bar: i32 = 10;
        if hit.hit { bar = 110; }
        raylib::DrawRectangle(20, 120, bar, 20, raylib::DARKGREEN);
        raylib::rlSetLineWidth(2.0);
        raylib::DrawFPS(20, 80);
        raylib::EndDrawing();
        frames = frames + 1;
    }

    raylib::UnloadRenderTexture(target);
    raylib::CloseAudioDevice();
    print("ok\n");
    raylib::CloseWindow();
}
