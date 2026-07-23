use tauri::{
    AppHandle, CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu,
    SystemTrayMenuItem,
};
use reqwest::blocking::Client;
use std::time::Duration;

pub fn create_tray(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let mut status = CustomMenuItem::new("status".to_string(), "Status: Unknown");
    status.enabled = false;
    
    let ask = CustomMenuItem::new("ask".to_string(), "Ask Señorita");
    let dashboard = CustomMenuItem::new("dashboard".to_string(), "Open Dashboard");
    let briefing = CustomMenuItem::new("briefing".to_string(), "Today's Briefing");
    let handled = CustomMenuItem::new("handled".to_string(), "Handled Today");
    let tasks = CustomMenuItem::new("tasks".to_string(), "Tasks");
    let calendar = CustomMenuItem::new("calendar".to_string(), "Calendar");
    let memory = CustomMenuItem::new("memory".to_string(), "Memory");
    let connections = CustomMenuItem::new("connections".to_string(), "Connections");
    let activity = CustomMenuItem::new("activity".to_string(), "Activity");
    let settings = CustomMenuItem::new("settings".to_string(), "Settings");
    
    let pause = CustomMenuItem::new("pause".to_string(), "Pause Assistant");
    let resume = CustomMenuItem::new("resume".to_string(), "Resume Assistant");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");

    let tray_menu = SystemTrayMenu::new()
        .add_item(status)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(ask)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(dashboard)
        .add_item(briefing)
        .add_item(handled)
        .add_item(tasks)
        .add_item(calendar)
        .add_item(memory)
        .add_item(connections)
        .add_item(activity)
        .add_item(settings)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(pause)
        .add_item(resume)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit);

    let tray = SystemTray::new().with_menu(tray_menu);
    app.handle().set_system_tray(tray)?;

    Ok(())
}

pub fn handle_tray_event(app: &AppHandle, event: SystemTrayEvent) {
    match event {
        SystemTrayEvent::MenuItemClick { id, .. } => {
            // Helper to navigate frontend
            let navigate = |route: &str| {
                if let Some(window) = app.get_window("main") {
                    window.show().unwrap();
                    window.set_focus().unwrap();
                    // Emit event to frontend to handle routing
                    window.emit("navigate", route).unwrap();
                }
            };

            match id.as_str() {
                "ask" => navigate("/chat"),
                "dashboard" => navigate("/dashboard"),
                "briefing" => navigate("/dashboard"),
                "handled" => navigate("/activity"),
                "tasks" => navigate("/tasks"),
                "calendar" => navigate("/calendar"),
                "memory" => navigate("/memory"),
                "connections" => navigate("/dashboard"),
                "activity" => navigate("/activity"),
                "settings" => navigate("/settings"),
                "pause" => {
                    let client = Client::builder().timeout(Duration::from_secs(2)).build().unwrap();
                    let _ = client.patch("http://localhost:8000/system/pause").send();
                }
                "resume" => {
                    let client = Client::builder().timeout(Duration::from_secs(2)).build().unwrap();
                    let _ = client.patch("http://localhost:8000/system/resume").send();
                }
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        },
        SystemTrayEvent::LeftClick { .. } => {
            if let Some(window) = app.get_window("main") {
                window.show().unwrap();
                window.set_focus().unwrap();
            }
        }
        _ => {}
    }
}
