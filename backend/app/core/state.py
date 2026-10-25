import json
import os

# Global application state file
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".senorita_state.json")

def load_state() -> bool:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return data.get("is_paused", False)
        except Exception:
            return False
    return False

is_paused: bool = load_state()

def get_pause_state() -> bool:
    return is_paused

def set_pause_state(state: bool):
    global is_paused
    is_paused = state
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"is_paused": state}, f)
    except Exception:
        pass
