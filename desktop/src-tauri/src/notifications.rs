use tauri::Manager;

#[tauri::command]
fn send_notification(app: tauri::AppHandle, title: String, body: String) -> Result<(), String> {
    let builder = tauri::api::notification::NotificationBuilder::new(&app)
        .title(title)
        .body(body);
    builder.show().map_err(|e| e.to_string())?;
    Ok(())
}

