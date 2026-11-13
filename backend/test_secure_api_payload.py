import json
from dotenv import load_dotenv

from app.services.secure_data_service import encrypt_sensitive_data

load_dotenv()

payload = {
    "encrypted_ssn": encrypt_sensitive_data("123-45-6789", "ssn"),
    "encrypted_dob": encrypt_sensitive_data("01/15/1990", "dob")
}

print(json.dumps(payload, indent=2))