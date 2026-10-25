import json
import logging
import sys

logger = logging.getLogger(__name__)


async def dispatch_notification(title: str, message: str, payload: dict | None = None):
    """
    Dispatches a notification by emitting a JSON payload to stdout.
    The Tauri desktop shell reads this and bridges it to native OS notifications.
    """
    logger.info(f"DISPATCH NOTIFICATION | Title: {title} | Message: {message} | Payload: {payload}")
    
    ipc_message = {
        "senorita_ipc": "notification",
        "title": title,
        "body": message
    }
    
    # Print exactly one line as JSON for Rust to parse, and flush immediately
    print(json.dumps(ipc_message), flush=True)
    sys.stdout.flush()
