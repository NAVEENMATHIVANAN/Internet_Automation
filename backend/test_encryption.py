from dotenv import load_dotenv

from app.services.secure_data_service import (
    encrypt_sensitive_data,
    decrypt_sensitive_data,
)

load_dotenv()

# Synthetic test values only
test_ssn = "123-45-6789"
test_dob = "01/15/1990"

encrypted_ssn = encrypt_sensitive_data(test_ssn, "ssn")
encrypted_dob = encrypt_sensitive_data(test_dob, "dob")

print("Encrypted SSN:", encrypted_ssn)
print("Encrypted DOB:", encrypted_dob)

decrypted_ssn = decrypt_sensitive_data(encrypted_ssn, "ssn")
decrypted_dob = decrypt_sensitive_data(encrypted_dob, "dob")

print("SSN decryption successful:", decrypted_ssn == test_ssn)
print("DOB decryption successful:", decrypted_dob == test_dob)

# Verify that data encrypted for one purpose cannot be decrypted as another.
try:
    decrypt_sensitive_data(encrypted_ssn, "dob")
    print("ERROR: Purpose validation failed.")
except ValueError:
    print("Purpose validation successful.")