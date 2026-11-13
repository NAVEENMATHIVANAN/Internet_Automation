import re
from datetime import datetime

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pathlib import Path
from fastapi.responses import PlainTextResponse
from fastapi import Depends
from app.services.api_auth_service import verify_secure_api_token

from app.services.rsa_encryption_service import decrypt_with_private_key

from app.services.secure_data_service import decrypt_sensitive_data

load_dotenv()

router = APIRouter(
    prefix="/api/secure-data",
    tags=["Secure Data"]
)


class EncryptedIdentityRequest(BaseModel):
    encrypted_ssn: str = Field(min_length=1)
    encrypted_dob: str = Field(min_length=1)



@router.get("/public-key", response_class=PlainTextResponse)
def get_public_key():
    public_key_path = (
        Path(__file__).resolve().parents[2]
        / "keys"
        / "public_key.pem"
    )

    if not public_key_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Public key is not configured."
        )

    return public_key_path.read_text()



@router.post("/validate")
def validate_encrypted_identity(
    data: EncryptedIdentityRequest,
    authenticated: bool = Depends(verify_secure_api_token)
):
    try:
        ssn = decrypt_sensitive_data(data.encrypted_ssn, "ssn")
        dob = decrypt_sensitive_data(data.encrypted_dob, "dob")

        # Basic US SSN format validation
        if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
            raise ValueError("Invalid SSN format.")

        # Validate DOB format
        parsed_dob = datetime.strptime(dob, "%m/%d/%Y")

        if parsed_dob.date() >= datetime.now().date():
            raise ValueError("DOB must be in the past.")

        # Do not return or store ssn or dob.
        del ssn
        del dob

        return {
            "success": True,
            "message": "Encrypted identity data validated successfully.",
            "plaintext_returned": False,
            "database_storage": False
        }

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Encrypted identity validation failed."
        )

@router.post("/validate-rsa")
def validate_rsa_identity(
    data: EncryptedIdentityRequest,
    authenticated: bool = Depends(verify_secure_api_token)
):
    try:
        ssn = decrypt_with_private_key(data.encrypted_ssn)
        dob = decrypt_with_private_key(data.encrypted_dob)

        if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
            raise ValueError("Invalid SSN format.")

        parsed_dob = datetime.strptime(dob, "%m/%d/%Y")

        if parsed_dob.date() >= datetime.now().date():
            raise ValueError("DOB must be in the past.")

        del ssn
        del dob

        return {
            "success": True,
            "message": "RSA-encrypted identity data validated successfully.",
            "plaintext_returned": False,
            "database_storage": False
        }

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Encrypted identity validation failed."
        )

