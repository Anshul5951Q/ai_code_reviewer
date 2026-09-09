"""Tests for server-side token encryption and decryption."""
from __future__ import annotations

import pytest

from app.core.encryption import (
    TokenDecryptionError,
    TokenEncryptionError,
    _derive_fernet_key,
    decrypt_token,
    encrypt_token,
)


def test_encrypt_and_decrypt_roundtrip():
    """Test that a plaintext token encrypts and decrypts correctly."""
    sample_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    ciphertext = encrypt_token(sample_token)

    assert ciphertext != sample_token
    assert not ciphertext.startswith("ghp_")
    assert len(ciphertext) > 40

    decrypted = decrypt_token(ciphertext)
    assert decrypted == sample_token


def test_encryption_produces_unique_ciphertexts():
    """Fernet uses a random IV/timestamp per encryption, so ciphertexts should differ."""
    sample_token = "ghp_secure_token_abc"
    c1 = encrypt_token(sample_token)
    c2 = encrypt_token(sample_token)

    assert c1 != c2
    assert decrypt_token(c1) == sample_token
    assert decrypt_token(c2) == sample_token


def test_corrupted_ciphertext_raises_error():
    """Tampered ciphertext must fail to decrypt."""
    sample_token = "ghp_secret_value"
    ciphertext = encrypt_token(sample_token)

    # Corrupt a character in the middle
    corrupted = ciphertext[:15] + ("X" if ciphertext[15] != "X" else "Y") + ciphertext[16:]

    with pytest.raises(TokenDecryptionError):
        decrypt_token(corrupted)


def test_empty_token_encryption_raises_error():
    """Encrypting empty string must raise TokenEncryptionError."""
    with pytest.raises(TokenEncryptionError):
        encrypt_token("")


def test_empty_ciphertext_decryption_raises_error():
    """Decrypting empty string must raise TokenDecryptionError."""
    with pytest.raises(TokenDecryptionError):
        decrypt_token("")


def test_key_derivation_deterministic():
    """Same raw key produces same 32-byte urlsafe base64 key."""
    raw = "my-custom-super-secret-key"
    k1 = _derive_fernet_key(raw)
    k2 = _derive_fernet_key(raw)
    assert k1 == k2
    assert len(k1) == 44  # 32 bytes base64-encoded is 44 chars
