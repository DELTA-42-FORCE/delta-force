#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

fn main() {
    if let Err(error) = delta_force_windows_architecture_spike::run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
