import json
from getpass import getpass

from app.services.rsa_encryption_service import encrypt_with_public_key


print("SIMULATOR TEST PAYMENT REQUEST")
print("Enter fictional test details only.\n")

cardholder = input("Fictional cardholder name: ").strip()
card_number = getpass("Fictional card number: ").strip()
expiry_month = input("Expiry month (MM): ").strip()
expiry_year = input("Expiry year (YYYY): ").strip()
cvv = getpass("Fictional CVV: ").strip()

request_data = {
    "encrypted_identity": None,
    "encrypted_test_card": {
        "encrypted_cardholder_name": encrypt_with_public_key(cardholder),
        "encrypted_card_number": encrypt_with_public_key(card_number),
        "encrypted_expiry_month": encrypt_with_public_key(expiry_month),
        "encrypted_expiry_year": encrypt_with_public_key(expiry_year),
        "encrypted_cvv": encrypt_with_public_key(cvv),
        "card_type": "Visa"
    }
}

print("\nCopy the JSON below into Swagger:")
print(json.dumps(request_data, indent=2))