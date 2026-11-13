import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


KEY_DIR = Path(__file__).resolve().parents[2] / "keys"


def encrypt_with_public_key(value: str, public_key_path=None) -> str:
    if not value or not value.strip():
        raise ValueError("Value cannot be empty.")

    path = Path(public_key_path) if public_key_path else KEY_DIR / "public_key.pem"

    public_key = serialization.load_pem_public_key(
        path.read_bytes()
    )

    encrypted = public_key.encrypt(
        value.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_with_private_key(encrypted_value: str, private_key_path=None) -> str:
    if not encrypted_value:
        raise ValueError("Encrypted value cannot be empty.")

    path = Path(private_key_path) if private_key_path else KEY_DIR / "private_key.pem"

    private_key = serialization.load_pem_private_key(
        path.read_bytes(),
        password=None
    )

    encrypted_bytes = base64.b64decode(
        encrypted_value,
        validate=True
    )

    decrypted = private_key.decrypt(
        encrypted_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    return decrypted.decode("utf-8")