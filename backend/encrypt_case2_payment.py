from getpass import getpass
import json
import re

from app.services.rsa_encryption_service import encrypt_with_public_key


CARD_TYPES = {
    "1": "Visa",
    "2": "MasterCard",
    "3": "American Express",
    "4": "Discover",
}


def main():
    print("CASE 2 PAYMENT ENCRYPTION")
    print("Run from the backend folder. CVV is encrypted for one-time use only.\n")

    for key, value in CARD_TYPES.items():
        print(f"{key}. {value}")
    card_type_choice = input("Card type: ").strip()
    if card_type_choice not in CARD_TYPES:
        raise SystemExit("Invalid card type.")

    card_number = input("Enter 16-digit card number: ").strip().replace(" ", "")
    cardholder_name = getpass("Cardholder name (hidden): ").strip()
    expiry_month = input("Expiry month (MM): ").strip()
    expiry_year = input("Expiry year (YYYY): ").strip()
    expiry_year = re.sub(r"\s+", "", expiry_year)
    cvv = getpass("CVV (hidden; do not save): ").strip()

    normalized_number = re.sub(r"[\s-]", "", card_number)

    if not normalized_number.isdigit() or len(normalized_number) != 16:
        raise SystemExit("Card number must contain exactly 16 digits.")
    if not cardholder_name:
        raise SystemExit("Cardholder name is required.")
    if not expiry_month.isdigit() or not 1 <= int(expiry_month) <= 12:
        raise SystemExit("Expiry month must be 01 through 12.")
    if not re.fullmatch(r"\d{4}", expiry_year):
        raise SystemExit("Expiry year must contain exactly four digits (YYYY).")
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        raise SystemExit("CVV must contain three or four digits.")

    encrypted_payment = {
        "encrypted_card_type": encrypt_with_public_key(CARD_TYPES[card_type_choice]),
        "encrypted_card_number": encrypt_with_public_key(normalized_number),
        "encrypted_cardholder_name": encrypt_with_public_key(cardholder_name),
        "encrypted_expiry_month": encrypt_with_public_key(expiry_month.zfill(2)),
        "encrypted_expiry_year": encrypt_with_public_key(expiry_year),
    }
    encrypted_cvv = encrypt_with_public_key(cvv)

    # Drop local references before printing. Only ciphertext is emitted.
    card_number = None
    normalized_number = None
    cardholder_name = None
    expiry_month = None
    expiry_year = None
    cvv = None

    print("\nCOPY encrypted_payment INTO POST /api/orders/create:")
    print(json.dumps({"encrypted_payment": encrypted_payment}, indent=2))
    print("\nCOPY encrypted_cvv INTO POST /api/automation/run/{order_id}:")
    print(json.dumps({"encrypted_cvv": encrypted_cvv}, indent=2))
    print("\nDo not store the encrypted_cvv output. Use it once for the automation request.")


if __name__ == "__main__":
    main()
