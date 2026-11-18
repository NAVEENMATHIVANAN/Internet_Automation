
from getpass import getpass
from datetime import datetime, date
import re

from app.services.rsa_encryption_service import (
    encrypt_with_public_key,
    decrypt_with_private_key
)


def main():
    ssn = getpass("Enter simulator SSN (123-45-6789): ")
    dob = getpass("Enter simulator DOB (MM/DD/YYYY): ")

    print("\nChecking input formats...")

    if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
        print("FAILED: SSN format must be XXX-XX-XXXX.")
        return

    try:
        birth_date = datetime.strptime(dob, "%m/%d/%Y").date()
        if birth_date >= date.today():
            print("FAILED: DOB must be in the past.")
            return
    except ValueError:
        print("FAILED: DOB format must be MM/DD/YYYY.")
        return

    print("Input formats: PASS")

    try:
        encrypted_ssn = encrypt_with_public_key(ssn)
        encrypted_dob = encrypt_with_public_key(dob)

        print("Public-key encryption: PASS")

        decrypted_ssn = decrypt_with_private_key(encrypted_ssn)
        decrypted_dob = decrypt_with_private_key(encrypted_dob)

        print("Private-key decryption: PASS")

        if decrypted_ssn != ssn or decrypted_dob != dob:
            print("FAILED: Encryption round-trip mismatch.")
            return

        print("Encryption round-trip: PASS")
        print("\nYour RSA key pair and input formats are working.")

    except Exception as exc:
        print("ENCRYPTION TEST FAILED:", type(exc).__name__)


if __name__ == "__main__":
    main()
