from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger("ai_code_reviewer.encryption")


class TokenEncryptionError(Exception):
    """Raised when token encryption fails."""
    pass


class TokenDecryptionError(Exception):
    """Raised when token decryption fails or ciphertext is corrupted/tampered."""
    pass


def _derive_fernet_key(raw_key: Optional[str]) -> bytes:
    """
    Derive a valid 32-byte URL-safe base64-encoded key for Fernet.
    If raw_key is already a valid 32-byte base64 string, it will be used directly.
    Otherwise, a deterministic SHA-256 hash of the input string is base64-encoded.
    """
    if not raw_key:
        # Fallback for dev / tests when GITHUB_TOKEN_ENCRYPTION_KEY is not set
        raw_key = f"dev-fallback-key-ai-code-reviewer-{settings.app_env}"
        if settings.is_production:
            logger.warning(
                "GITHUB_TOKEN_ENCRYPTION_KEY is not configured in production! "
                "Using fallback key is insecure."
            )

    key_bytes = raw_key.strip().encode("utf-8")

    # Check if raw_key is already a valid 44-byte base64 Fernet key
    try:
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) == 32:
            return key_bytes
    except Exception:
        pass

    # Hash arbitrary length secret to 32 bytes and urlsafe base64-encode
    digest = hashlib.sha256(key_bytes).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    """Instantiate a Fernet cipher using configured encryption key."""
    key = _derive_fernet_key(settings.github_token_encryption_key)
    return Fernet(key)


def encrypt_token(plaintext_token: str) -> str:
    """
    Encrypt a GitHub access token using AES-128-CBC + HMAC-SHA256 (Fernet).
    Returns an ASCII string ciphertext.
    Never logs or exposes the plaintext token.
    """
    if not plaintext_token:
        raise TokenEncryptionError("Cannot encrypt empty token.")

    try:
        f = get_fernet()
        ciphertext = f.encrypt(plaintext_token.encode("utf-8"))
        return ciphertext.decode("utf-8")
    except Exception as exc:
        logger.error("Failed to encrypt GitHub token: internal error")
        raise TokenEncryptionError("Token encryption failed.") from None


def decrypt_token(ciphertext: str) -> str:
    """
    Decrypt a stored GitHub access token.
    Never logs or exposes the decrypted token.
    Raises TokenDecryptionError if corrupted, tampered, or key has changed.
    """
    if not ciphertext:
        raise TokenDecryptionError("Cannot decrypt empty ciphertext.")

    try:
        f = get_fernet()
        decrypted_bytes = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        logger.warning("Token decryption failed: invalid or tampered ciphertext.")
        raise TokenDecryptionError("Stored token could not be decrypted. It may have expired or been revoked.") from None
    except Exception as exc:
        logger.error("Unexpected error during token decryption.")
        raise TokenDecryptionError("Token decryption failed.") from None
