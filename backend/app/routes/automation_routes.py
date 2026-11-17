
import logging

logger = logging.getLogger(__name__)

import re
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.services.api_auth_service import verify_secure_api_token
from app.services.rsa_encryption_service import decrypt_with_private_key
from app.services.browser_service import BrowserService

router = APIRouter(prefix="/api/automation", tags=["Browser Automation"])


class EncryptedIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encrypted_ssn: str = Field(min_length=1, max_length=2000)
    encrypted_dob: str = Field(min_length=1, max_length=2000)


class EncryptedTestCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encrypted_cardholder_name: str = Field(min_length=1, max_length=2000)
    encrypted_card_number: str = Field(min_length=1, max_length=2000)
    encrypted_expiry_month: str = Field(min_length=1, max_length=2000)
    encrypted_expiry_year: str = Field(min_length=1, max_length=2000)
    encrypted_cvv: str = Field(min_length=1, max_length=2000)

    # Card type is a non-secret selector value, not a card credential.
    card_type: str = Field(pattern=r"^(Visa|Mastercard|American Express|Discover)$")


class AutomationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encrypted_identity: EncryptedIdentity | None = None
    encrypted_test_card: EncryptedTestCard | None = None


def validate_identity(ssn: str, dob: str) -> None:
    if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
        raise ValueError("Invalid identity details.")

    try:
        birth_date = datetime.strptime(dob, "%m/%d/%Y").date()
    except ValueError:
        raise ValueError("Invalid identity details.")

    if birth_date >= date.today():
        raise ValueError("Invalid identity details.")


def decrypt_test_card(encrypted_card: EncryptedTestCard) -> dict:
    card = {
        "cardholder_name": decrypt_with_private_key(
            encrypted_card.encrypted_cardholder_name
        ),
        "card_number": decrypt_with_private_key(
            encrypted_card.encrypted_card_number
        ),
        "expiry_month": decrypt_with_private_key(
            encrypted_card.encrypted_expiry_month
        ),
        "expiry_year": decrypt_with_private_key(
            encrypted_card.encrypted_expiry_year
        ),
        "cvv": decrypt_with_private_key(
            encrypted_card.encrypted_cvv
        ),
        "card_type": encrypted_card.card_type,
    }

    if not card["cardholder_name"].strip():
        raise ValueError("Invalid test card.")

    if not re.fullmatch(r"\d{12,19}", card["card_number"]):
        raise ValueError("Invalid test card.")

    if not re.fullmatch(r"(0[1-9]|1[0-2])", card["expiry_month"]):
        raise ValueError("Invalid test card.")

    if not re.fullmatch(r"\d{4}", card["expiry_year"]):
        raise ValueError("Invalid test card.")

    if not re.fullmatch(r"\d{3,4}", card["cvv"]):
        raise ValueError("Invalid test card.")

    expiry = date(
        int(card["expiry_year"]),
        int(card["expiry_month"]),
        1
    )
    current_month = date.today().replace(day=1)

    if expiry < current_month:
        raise ValueError("Invalid test card.")

    return card


@router.post("/run/{order_id}")
def run_full_order(
    order_id: str,
    request: AutomationRunRequest,
    authenticated: bool = Depends(verify_secure_api_token),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.order_id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.automation_status == "IN_PROGRESS":
        raise HTTPException(
            status_code=409,
            detail="Automation is already running for this order."
        )

    qualification = order.qualification or {}
    ez_enroll = qualification.get("ez_enroll", False)

    if not ez_enroll and request.encrypted_identity is None:
        raise HTTPException(
            status_code=422,
            detail="Encrypted identity details are required when EZ-Enroll is disabled."
        )

    if ez_enroll and request.encrypted_identity is not None:
        raise HTTPException(
            status_code=422,
            detail="Identity details must not be supplied for the EZ-Enroll path."
        )

    identity_data = None
    payment_data = None
    ssn = None
    dob = None

    try:
        if request.encrypted_identity is not None:
            try:
                ssn = decrypt_with_private_key(
                    request.encrypted_identity.encrypted_ssn
                )
                dob = decrypt_with_private_key(
                    request.encrypted_identity.encrypted_dob
                )
                validate_identity(ssn, dob)
                identity_data = {"ssn": ssn, "dob": dob}
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail="Encrypted identity details could not be validated."
                )

        if request.encrypted_test_card is not None:
            try:
                payment_data = decrypt_test_card(
                    request.encrypted_test_card
                )
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail="Encrypted simulator payment details could not be validated."
                )

        order.status = "IN_PROGRESS"
        order.automation_status = "IN_PROGRESS"
        db.commit()

        payload = {
            "customer": order.customer_data,
            "service_address": order.service_address,
            "order": order.order_data,
            "qualification": order.qualification,
            "installation": order.installation,
            "disclosures": order.disclosures,
        }

        result = BrowserService().run_full_order(
            payload,
            identity_data=identity_data
        )

        order.automation_status = result.get(
            "status", "MANUAL_REVIEW_REQUIRED"
        )
        order.status = (
            "READY_FOR_REVIEW"
            if result.get("status") == "ORDER_SUMMARY_REACHED"
            else "MANUAL_REVIEW_REQUIRED"
        )
        db.commit()

        # Do not return payment or identity data.
        return {
            "order_id": order.order_id,
            "status": result.get("status"),
            "current_url": result.get("current_url"),
            "steps": result.get("steps", []),
            "screenshot": result.get("screenshot"),
            "message": result.get("message"),
            "error": result.get("error"),
        }

    except HTTPException:
        raise

    except Exception:
        # Print the full error and traceback in the Uvicorn terminal.
        logger.exception(
            "Automation failed for order_id=%s",
            order_id,
        )

        db.rollback()

        # Do not leave a failed attempt marked as running.
        failed_order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        if failed_order:
            failed_order.status = "MANUAL_REVIEW_REQUIRED"
            failed_order.automation_status = "MANUAL_REVIEW_REQUIRED"
            db.commit()

        raise HTTPException(
            status_code=500,
            detail="Automation failed. Check the backend terminal for details.",
        )

    finally:
        if identity_data is not None:
            identity_data.clear()

        if payment_data is not None:
            payment_data.clear()

        ssn = None
        dob = None
        payment_data = None
        identity_data = None