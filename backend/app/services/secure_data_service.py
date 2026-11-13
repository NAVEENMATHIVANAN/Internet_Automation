import os
import base64
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_encryption_key() -> bytes:
    encoded_key = os.getenv("ENCRYPTION_KEY")

    if not encoded_key:
        raise RuntimeError("ENCRYPTION_KEY is missing from environment variables.")

    try:
        key = base64.urlsafe_b64decode(encoded_key)
    except Exception as exc:
        raise RuntimeError("ENCRYPTION_KEY is not valid Base64.") from exc

    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must decode to exactly 32 bytes.")

    return key


def encrypt_sensitive_data(value: str, purpose: str) -> str:
    """
    Encrypt sensitive data using AES-256-GCM.
    Supported purposes: ssn, dob.
    Returns a Base64-encoded nonce + ciphertext.
    """
    if purpose not in {"ssn", "dob"}:
        raise ValueError("Unsupported encryption purpose.")

    if not value or not value.strip():
        raise ValueError("Value cannot be empty.")

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    nonce = secrets.token_bytes(12)
    associated_data = purpose.encode("utf-8")

    ciphertext = aesgcm.encrypt(
        nonce,
        value.encode("utf-8"),
        associated_data
    )

    encrypted_payload = nonce + ciphertext

    return base64.urlsafe_b64encode(encrypted_payload).decode("utf-8")


def decrypt_sensitive_data(encrypted_value: str, purpose: str) -> str:
    """
    Decrypt data previously encrypted with the same purpose.
    """
    if purpose not in {"ssn", "dob"}:
        raise ValueError("Unsupported decryption purpose.")

    if not encrypted_value:
        raise ValueError("Encrypted value cannot be empty.")

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    try:
        encrypted_payload = base64.urlsafe_b64decode(encrypted_value)

        if len(encrypted_payload) < 29:
            raise ValueError("Encrypted payload is invalid.")

        nonce = encrypted_payload[:12]
        ciphertext = encrypted_payload[12:]

        associated_data = purpose.encode("utf-8")

        decrypted = aesgcm.decrypt(
            nonce,
            ciphertext,
            associated_data
        )

        return decrypted.decode("utf-8")

    except Exception as exc:
        raise ValueError(
            "Decryption failed. The key, purpose, or encrypted data may be incorrect."
        ) from exc