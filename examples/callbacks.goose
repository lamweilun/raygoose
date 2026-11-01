import raylib from "..";
import ffi;

// The five callback handlers. Each is a fixed export: Goose has no function
// pointers, so the binding's C trampoline calls it by name. Text arrives as a
// C string (u64), valid only during the call; ffi::cstr copies it.

var logged: u8[>..] = [];
var loaded_data: u8[>..] = [];
var loaded_text: u8[>..] = [];
var saved_data: u8[>..] = [];
var saved_text: u8[>..] = [];

export fn raylib_trace_log_callback(level: i32, text: u64) {
    if level == raylib::LOG_WARNING {
        logged = ffi::cstr(text);
    }
}

// The loader returns a slice; C copies it into raylib's allocator before the
// callback returns, so a reusable global buffer is enough.
export fn raylib_load_file_data_callback(file_name: u64) -> const u8[:] {
    loaded_data = [];
    if ffi::cstr(file_name) == "virtual.bin" {
        loaded_data.push(1);
        loaded_data.push(2);
        loaded_data.push(3);
    }
    return loaded_data;
}

export fn raylib_load_file_text_callback(file_name: u64) -> const u8[:] {
    loaded_text = [];
    if ffi::cstr(file_name) == "virtual.txt" {
        format(loaded_text, "from the callback");
    }
    return loaded_text;
}

export fn raylib_save_file_data_callback(file_name: u64, data: u64, data_size: i32) -> bool {
    if ffi::cstr(file_name) != "virtual.bin" {
        return false;
    }
    saved_data = [];
    ffi::bytes(data, data_size, saved_data);
    return true;
}

export fn raylib_save_file_text_callback(file_name: u64, text: u64) -> bool {
    if ffi::cstr(file_name) != "virtual.txt" {
        return false;
    }
    saved_text = ffi::cstr(text);
    return true;
}

// No window: this runs headless on every platform, so CI can execute it.
fn main() {
    raylib::SetTraceLogCallback();
    raylib::trace_log(raylib::LOG_WARNING, "callback check\0"[0]);
    assert(logged == "callback check");

    raylib::SetLoadFileDataCallback();
    var size: i32 = 0;
    let data = raylib::LoadFileData("virtual.bin\0"[0], size);
    assert(size == 3);
    let got = ffi::bytes(data, size);
    assert(got.len == 3 && got[0] == 1 && got[1] == 2 && got[2] == 3);

    raylib::SetLoadFileTextCallback();
    let text = raylib::LoadFileText("virtual.txt\0"[0]);
    assert(ffi::cstr(text) == "from the callback");

    raylib::SetSaveFileDataCallback();
    assert(raylib::SaveFileData("virtual.bin\0"[0], "\x09\x08\x07\0"[0], 3));
    assert(saved_data.len == 3 && saved_data[0] == 9 && saved_data[1] == 8 && saved_data[2] == 7);

    raylib::SetSaveFileTextCallback();
    assert(raylib::SaveFileText("virtual.txt\0"[0], "to the callback\0"[0]));
    assert(saved_text == "to the callback");

    // The raw extern still takes the u64 raylib wants; 0 restores the default.
    raylib::SetTraceLogCallback(0);
    raylib::trace_log(raylib::LOG_WARNING, "not seen\0"[0]);
    assert(logged == "callback check");

    print("callbacks ok: ", logged, "\n");
}
