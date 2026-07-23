#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod tray;
mod notifications;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            tray::create_tray(app)?;
            let app_handle = app.handle();
            std::thread::spawn(move || {
                let client = reqwest::blocking::Client::builder()
                    .timeout(std::time::Duration::from_secs(2))
                    .build()
                    .unwrap();
                loop {
                    let status = match client.get("http://localhost:8000/healthz").send() {
                        Ok(res) if res.status().is_success() => "● System: Online",
                        Ok(_) => "◐ System: Degraded",
                        Err(_) => "○ System: Offline",
                    };
                    app_handle.tray_handle().get_item("status").set_title(status).unwrap_or(());
                    std::thread::sleep(std::time::Duration::from_secs(10));
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            notifications::send_notification,
        ])
        .on_system_tray_event(|app, event| {
            tray::handle_tray_event(app, event);
        })
        .run(tauri::generate_context!())
        .expect("error while running Señorita desktop");
}

