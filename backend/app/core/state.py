# Global application state

is_paused: bool = False


def get_pause_state() -> bool:
    return is_paused


def set_pause_state(state: bool):
    global is_paused
    is_paused = state
