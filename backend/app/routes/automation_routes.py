
import re
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.services.api_auth_service import verify_secure_api_token
from app.services.rsa_encryption_service import decrypt_with_private_key
from app.services.browser_service import BrowserService


router = APIRouter(
    prefix="/api/automation",
    tags=["Browser Automation"]
)


def validate_identity(ssn: str, dob: str) -> None:
    if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
        raise ValueError("Invalid identity details.")

    try:
        birth_date = datetime.strptime(dob, "%m/%d/%Y").date()
    except ValueError:
        raise ValueError("Invalid identity details.")

    if birth_date >= date.today():
        raise ValueError("Invalid identity details.")


@router.post("/run/{order_id}")
def run_full_order(
    order_id: str,
    authenticated: bool = Depends(verify_secure_api_token),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.order_id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found."
        )

    if order.automation_status == "IN_PROGRESS":
        raise HTTPException(
            status_code=409,
            detail="Automation is already running for this order."
        )

    qualification = order.qualification or {}
    ez_enroll = qualification.get("ez_enroll", False)

    identity_data = None
    ssn = None
    dob = None

    # Retrieve identity data from the order record.
    if not ez_enroll:

        if not order.encrypted_ssn or not order.encrypted_dob:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Encrypted identity details are missing "
                    "for the standard credit-check path."
                )
            )

        try:
            ssn = decrypt_with_private_key(order.encrypted_ssn)
            dob = decrypt_with_private_key(order.encrypted_dob)

            validate_identity(ssn, dob)

            identity_data = {
                "ssn": ssn,
                "dob": dob
            }

        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Stored identity details could not be validated."
            )

    # EZ-Enroll does not require SSN/DOB for this workflow.
    else:
        identity_data = None

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

    try:
        result = BrowserService().run_full_order(
            payload,
            identity_data=identity_data
        )

        automation_result = result.get(
            "status",
            "MANUAL_REVIEW_REQUIRED"
        )

        order.automation_status = automation_result

        order.status = (
            "READY_FOR_REVIEW"
            if automation_result == "ORDER_SUMMARY_REACHED"
            else "MANUAL_REVIEW_REQUIRED"
        )

        # Remove encrypted identity after successful completion
        # of the automation flow to minimize retention.
        if automation_result == "ORDER_SUMMARY_REACHED":
            order.encrypted_ssn = None
            order.encrypted_dob = None

        db.commit()

        return {
            "order_id": order.order_id,
            **result
        }

    except Exception:
        db.rollback()

        order = db.query(Order).filter(
            Order.order_id == order_id
        ).first()

        if order:
            order.status = "MANUAL_REVIEW_REQUIRED"
            order.automation_status = "MANUAL_REVIEW_REQUIRED"
            db.commit()

        raise HTTPException(
            status_code=500,
            detail="Automation could not be completed."
        )

    finally:
        # Clear temporary plaintext identity references.
        if identity_data is not None:
            identity_data.clear()

        ssn = None
        dob = None
        identity_data = None
