from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

KEY_DIR = Path("keys")
KEY_DIR.mkdir(exist_ok=True)

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=3072
)

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

(KEY_DIR / "private_key.pem").write_bytes(private_pem)
(KEY_DIR / "public_key.pem").write_bytes(public_pem)

print("RSA key pair generated.")
print("Private key: keys/private_key.pem")
print("Public key: keys/public_key.pem")