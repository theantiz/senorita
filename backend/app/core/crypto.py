import base64
import logging

from cryptography.fernet import Fernet

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet_instance = None


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = settings.ENCRYPTION_KEY
    try:
        key_bytes = key.encode()
        # Validate base64 format and length
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) == 32:
            _fernet_instance = Fernet(key_bytes)
            return _fernet_instance
    except Exception:
        pass

    logger.warning("ENCRYPTION_KEY env var is missing or invalid. Using a temporary dev-only key.")
    # Standard 32-byte url-safe base64 fallback key for local dev
    fallback_key = b"a184u0xvbMpAjGZh1_qUQK3NXffGaBUO2N09fPeL8ro="
    _fernet_instance = Fernet(fallback_key)
    return _fernet_instance


def encrypt(text: str | None) -> str | None:
    """
    Symmetrically encrypts cleartext string.
    Never logs values.
    """
    if text is None:
        return None
    try:
        f = get_fernet()
        return f.encrypt(text.encode()).decode()
    except Exception as e:
        logger.error("Failed to encrypt token")
        raise e


def decrypt(token: str | None) -> str | None:
    """
    Symmetrically decrypts encrypted ciphertext string.
    Never logs values.
    """
    if token is None:
        return None
    try:
        f = get_fernet()
        return f.decrypt(token.encode()).decode()
    except Exception as e:
        logger.error("Failed to decrypt token")
        raise e
