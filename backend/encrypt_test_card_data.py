
import base64
from pathlib import Path
from getpass import getpass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


BASE_DIR = Path(__file__).resolve().parent
PUBLIC_KEY_PATH = BASE_DIR / "keys" / "public_key.pem"


def encrypt_with_public_key(value: str, public_key) -> str:
    encrypted = public_key.encrypt(
        value.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(encrypted).decode("utf-8")


def main():
    if not PUBLIC_KEY_PATH.exists():
        raise FileNotFoundError(
            f"Public key not found: {PUBLIC_KEY_PATH}"
        )

    with open(PUBLIC_KEY_PATH, "rb") as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read()
        )

    # Fictional simulator test values
    card_type = "Visa"
    card_number = "4111111111111111"
    cardholder_name = "JOHN TEST"
    expiry_month = "12"
    expiry_year = "2030"
    cvv = "123"

    encrypted_payment = {
        "encrypted_card_type": encrypt_with_public_key(
            card_type, public_key
        ),
        "encrypted_card_number": encrypt_with_public_key(
            card_number, public_key
        ),
        "encrypted_cardholder_name": encrypt_with_public_key(
            cardholder_name, public_key
        ),
        "encrypted_expiry_month": encrypt_with_public_key(
            expiry_month, public_key
        ),
        "encrypted_expiry_year": encrypt_with_public_key(
            expiry_year, public_key
        ),
    }

    encrypted_cvv = encrypt_with_public_key(cvv, public_key)

    print("\nENCRYPTED PAYMENT DATA")
    print('"encrypted_payment": {')
    for key, value in encrypted_payment.items():
        print(f'  "{key}": "{value}",')
    print("}")

    print("\nENCRYPTED CVV")
    print(f'"encrypted_cvv": "{encrypted_cvv}"')


if __name__ == "__main__":
    main()
