import json

from app.services.rsa_encryption_service import encrypt_with_public_key

# Synthetic test data only
payload = {
    "encrypted_ssn": encrypt_with_public_key("123-45-6789"),
    "encrypted_dob": encrypt_with_public_key("01/15/1990")
}

print(json.dumps(payload, indent=2))