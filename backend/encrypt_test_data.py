
import json
from getpass import getpass

from app.services.rsa_encryption_service import encrypt_with_public_key


def main():
    print("RSA Test Data Encryption")
    print("------------------------")

    ssn = getpass("Enter simulator test SSN: ")
    dob = getpass("Enter simulator test DOB (MM/DD/YYYY): ")

    encrypted_payload = {
        "encrypted_ssn": encrypt_with_public_key(ssn),
        "encrypted_dob": encrypt_with_public_key(dob)
    }

    print("\nEncrypted identity payload:")
    print(json.dumps(encrypted_payload, indent=2))

    print("\nCopy the encrypted values into your Swagger request.")
    print("Do not share or log the plaintext values.")


if __name__ == "__main__":
    main()
