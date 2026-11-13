import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv
from sqlalchemy.types import TypeDecorator, Text

load_dotenv()

PREFIX = "ENC_V1:"
AAD = b"internet-order-json-v1"


def get_encryption_key():
    encoded_key = os.getenv("ENCRYPTION_KEY")

    if not encoded_key:
        raise RuntimeError("ENCRYPTION_KEY is missing")

    encoded_key = encoded_key.strip().strip('"').strip("'")

    try:
        key = base64.b64decode(
            encoded_key,
            altchars=b"-_",
            validate=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "ENCRYPTION_KEY is not valid Base64"
        ) from exc

    if len(key) != 32:
        raise RuntimeError(
            "ENCRYPTION_KEY must decode to exactly 32 bytes"
        )

    return key


def encrypt_json(value):
    if value is None:
        return None

    plaintext = json.dumps(
        value,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    nonce = os.urandom(12)

    ciphertext = AESGCM(
        get_encryption_key()
    ).encrypt(nonce, plaintext, AAD)

    return PREFIX + base64.b64encode(
        nonce + ciphertext
    ).decode("ascii")


def decrypt_json(value):
    if value is None:
        return None

    if not isinstance(value, str) or not value.startswith(PREFIX):
        raise ValueError(
            "Unencrypted or unsupported order data detected. "
            "Run the Stage 7 migration first."
        )

    encrypted_bytes = base64.b64decode(
        value[len(PREFIX):],
        validate=True,
    )

    if len(encrypted_bytes) < 29:
        raise ValueError("Invalid encrypted order data")

    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]

    plaintext = AESGCM(
        get_encryption_key()
    ).decrypt(nonce, ciphertext, AAD)

    return json.loads(plaintext.decode("utf-8"))


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_json(value)

    def process_result_value(self, value, dialect):
        return decrypt_json(value)