import raylib from "..";

struct Ball { pos: raylib::Vector2, vel: raylib::Vector2, radius: f32, color: raylib::Color }

fn main() {
    raylib::InitWindow(960, 540, "raygoose");
    raylib::SetTargetFPS(60);

    var balls: Ball[24] = [default<Ball>(); 24];
    var i = 0;
    while i < 24 {
        balls[i] = Ball {
            raylib::Vector2 { (60 + (i * 37) % 840) as f32, (60 + (i * 83) % 420) as f32 },
            raylib::Vector2 { (3 - (i * 7) % 6) as f32, (2 - (i * 5) % 4) as f32 },
            (10 + (i * 3) % 14) as f32,
            raylib::Color { (80 + (i * 60) % 175) as u8, (120 + (i * 40) % 135) as u8, 200, 230 },
        };
        i = i + 1;
    }

    var frames: i32 = 0;
    // raylib's built-in font: no asset, works on every platform.
    let font = raylib::GetFontDefault();

    while !raylib::WindowShouldClose() && frames < 1200 {
        let dt = raylib::GetFrameTime();
        for &b in balls {
            b.pos.x = b.pos.x + b.vel.x * 60.0 * dt;
            b.pos.y = b.pos.y + b.vel.y * 60.0 * dt;
            if b.pos.x < b.radius || b.pos.x > 960.0 - b.radius { b.vel.x = -b.vel.x; }
            if b.pos.y < b.radius || b.pos.y > 540.0 - b.radius { b.vel.y = -b.vel.y; }
        }

        raylib::BeginDrawing();
        raylib::ClearBackground(raylib::Color { 18, 18, 24, 255 });
        for &b in balls {
            raylib::DrawCircleV(b.pos, b.radius, b.color);
        }
        raylib::DrawTextEx(font, "raylib 6.5 + goose", raylib::Vector2 { 24.0, 20.0 }, 40.0, 1.0, raylib::RAYWHITE);
        let stats = str("fps ", raylib::GetFPS(), "   balls ", balls.len, "   frame ", frames, "\0");
        raylib::DrawTextEx(font, stats, raylib::Vector2 { 24.0, 70.0 }, 24.0, 1.0, raylib::GRAY);
        raylib::DrawText("press ESC to quit", 24, 500, 20, raylib::LIGHTGRAY);
        raylib::EndDrawing();
        frames = frames + 1;
    }

    print("ran ", frames, " frames at ", raylib::GetFPS(), " fps\n");
    raylib::CloseWindow();
}
