import logging

logger = logging.getLogger(__name__)

async def dispatch_notification(title: str, message: str, payload: dict | None = None):
    """
    Stub for dispatching a notification.
    In a later module, this will bridge to the desktop shell (Tauri) for native OS notifications.
    """
    logger.info(f"DISPATCH NOTIFICATION | Title: {title} | Message: {message} | Payload: {payload}")
    print(f"\\n[NOTIFICATION DISPATCHED] {title}: {message}\\n")
