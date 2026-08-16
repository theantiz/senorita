use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_shell::ShellExt;
use std::net::TcpListener;

struct AppState {
    backend_port: u16,
}

#[tauri::command]
fn get_backend_port(state: tauri::State<AppState>) -> u16 {
    state.backend_port
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, Some(vec!["--minimized"])))
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .on_window_event(|window, event| match event {
            tauri::WindowEvent::CloseRequested { api, .. } => {
                let _ = window.hide();
                api.prevent_close();
            }
            _ => {}
        })
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Explicitly enable autostart if not already enabled
            let _ = app.autolaunch().enable();

            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let show_i = MenuItem::with_id(app, "show", "Open Dashboard", true, None::<&str>)?;
            
            let menu = Menu::with_items(app, &[&show_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => {
                        std::process::exit(0);
                    }
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| match event {
                    TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } => {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    _ => {}
                })
                .tooltip("Señorita")
                .build(app)?;

            // If started minimized (e.g. from autostart), hide the window
            let args: Vec<String> = std::env::args().collect();
            if args.contains(&"--minimized".to_string()) {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }

                // Greet the user with a notification
                let _ = app.notification().builder()
                    .title("Señorita")
                    .body("Good morning! I am running in the background. Click the tray icon to open my dashboard.")
                    .show();
            }

            // Find a free port
            let listener = TcpListener::bind("127.0.0.1:0").expect("Failed to bind to any port");
            let port = listener.local_addr().expect("Failed to get local address").port();
            drop(listener); // Free the port so the backend can use it

            // Manage the state
            app.manage(AppState { backend_port: port });

            // Spawn the backend from the resource dir
            let resource_dir = app.path().resource_dir().expect("Failed to get resource dir");
            let backend_exe = resource_dir.join("backend-dir").join("backend-dir.exe");

            let backend_command = app.shell().command(backend_exe.to_str().unwrap())
                .args(["--port", &port.to_string()]);
            
            let app_handle = app.handle().clone();
            match backend_command.spawn() {
                Ok((mut rx, mut _child)) => {
                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = rx.recv().await {
                            match event {
                                tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                                    let text = String::from_utf8_lossy(&line);
                                    log::info!("Backend: {}", text);
                                    if text.contains("Token: ") {
                                        let parts: Vec<&str> = text.split("Token: ").collect();
                                        if parts.len() > 1 {
                                            let token = parts[1].trim();
                                            let _ = app_handle.notification().builder()
                                                .title("Señorita Admin Token")
                                                .body(&format!("Your admin token is: {}", token))
                                                .show();
                                        }
                                    }
                                }
                                tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                                    log::error!("Backend Error: {}", String::from_utf8_lossy(&line));
                                }
                                _ => {}
                            }
                        }
                    });
                }
                Err(e) => {
                    log::error!("Failed to spawn backend sidecar: {}", e);
                    let _ = app.notification().builder()
                        .title("Señorita Error")
                        .body(&format!("Failed to start backend: {}", e))
                        .show();
                }
            }


            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
