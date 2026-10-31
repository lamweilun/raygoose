import raylib from "..";

fn main() {
    raylib::InitWindow(800, 450, "raygoose\0"[0]);
    raylib::SetTargetFPS(60);

    var frames: i32 = 0;
    while frames < 60 {
        raylib::BeginDrawing();
        raylib::ClearBackground(raylib::RAYWHITE);
        raylib::DrawText("raylib + goose\0"[0], 20, 20, 40, raylib::DARKGRAY);
        raylib::DrawCircleV(raylib::Vector2 { 400.0, 300.0 }, 60.0, raylib::MAROON);
        raylib::DrawRectangleRec(raylib::Rectangle { 40.0, 250.0, 120.0, 80.0 }, raylib::ORANGE);
        raylib::DrawLine(0, 0, 800, 450, raylib::Color { 0, 121, 241, 255 });
        raylib::DrawFPS(20, 70);
        raylib::EndDrawing();
        frames = frames + 1;
    }
    print("ok frames=", frames, " fps=", raylib::GetFPS(), "\n");
    raylib::CloseWindow();
}
