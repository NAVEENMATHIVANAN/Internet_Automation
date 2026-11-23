
import json
import re
from datetime import date, datetime

from app.services.rsa_encryption_service import decrypt_with_private_key
from app.services.browser_service import BrowserService


def validate_identity(ssn: str, dob: str) -> None:
    if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
        raise ValueError("Invalid identity details.")

    try:
        birth_date = datetime.strptime(dob, "%m/%d/%Y").date()
    except ValueError:
        raise ValueError("Invalid identity details.")

    if birth_date >= date.today():
        raise ValueError("Invalid identity details.")


def decrypt_and_validate_payment(
    encrypted_payment_data: str,
    encrypted_cvv: str
) -> tuple[dict[str, str], str]:

    try:
        encrypted_fields = json.loads(encrypted_payment_data)

        required = {
            "encrypted_card_type",
            "encrypted_card_number",
            "encrypted_cardholder_name",
            "encrypted_expiry_month",
            "encrypted_expiry_year",
        }

        if (
            not isinstance(encrypted_fields, dict)
            or set(encrypted_fields) != required
        ):
            raise ValueError("Invalid encrypted payment structure.")

        payment_data = {
            "card_type": decrypt_with_private_key(
                encrypted_fields["encrypted_card_type"]
            ),
            "card_number": decrypt_with_private_key(
                encrypted_fields["encrypted_card_number"]
            ),
            "cardholder_name": decrypt_with_private_key(
                encrypted_fields["encrypted_cardholder_name"]
            ),
            "expiry_month": decrypt_with_private_key(
                encrypted_fields["encrypted_expiry_month"]
            ),
            "expiry_year": decrypt_with_private_key(
                encrypted_fields["encrypted_expiry_year"]
            ),
        }

        cvv = decrypt_with_private_key(encrypted_cvv)

        allowed_card_types = {
            "Visa",
            "MasterCard",
            "American Express",
            "Discover",
        }

        if payment_data["card_type"] not in allowed_card_types:
            raise ValueError("Invalid card type.")

        number = re.sub(r"[\s-]", "", payment_data["card_number"])

        if not number.isdigit() or not 12 <= len(number) <= 19:
            raise ValueError("Invalid card number.")

        payment_data["card_number"] = number

        if not payment_data["cardholder_name"].strip():
            raise ValueError("Invalid cardholder name.")

        month = payment_data["expiry_month"]

        if not month.isdigit() or not 1 <= int(month) <= 12:
            raise ValueError("Invalid expiry month.")

        if not re.fullmatch(r"\d{4}", payment_data["expiry_year"]):
            raise ValueError("Invalid expiry year.")

        if not cvv.isdigit() or len(cvv) not in (3, 4):
            raise ValueError("Invalid CVV.")

        return payment_data, cvv

    except Exception:
        raise ValueError(
            "Encrypted payment details could not be validated."
        )



def execute_order_automation(
    db,
    order,
    encrypted_cvv: str | None = None
) -> dict:

    identity_data = None
    payment_data = None
    ssn = None
    dob = None
    cvv = None

    try:
        qualification = order.qualification or {}
        ez_enroll = qualification.get("ez_enroll", False)

        # --------------------------------------------
        # 1. Decrypt identity or payment information
        # --------------------------------------------

        if not ez_enroll:

            if encrypted_cvv is not None:
                raise ValueError(
                    "CVV is not accepted for the standard credit-check path."
                )

            if not order.encrypted_ssn or not order.encrypted_dob:
                raise ValueError(
                    "Encrypted identity details are missing."
                )

            ssn = decrypt_with_private_key(order.encrypted_ssn)
            dob = decrypt_with_private_key(order.encrypted_dob)

            validate_identity(ssn, dob)

            identity_data = {
                "ssn": ssn,
                "dob": dob,
            }

        else:

            if not order.encrypted_payment_data or not encrypted_cvv:
                raise ValueError(
                    "Encrypted payment details are missing."
                )

            payment_data, cvv = decrypt_and_validate_payment(
                order.encrypted_payment_data,
                encrypted_cvv,
            )

        # --------------------------------------------
        # 2. Mark automation as in progress
        # --------------------------------------------

        order.status = "IN_PROGRESS"
        order.automation_status = "IN_PROGRESS"
        db.commit()

        # --------------------------------------------
        # 3. Build browser automation payload
        # --------------------------------------------

        payload = {
            "customer": order.customer_data,
            "service_address": order.service_address,
            "order": order.order_data,
            "qualification": order.qualification,
            "installation": order.installation,
            "disclosures": order.disclosures,
        }

        # --------------------------------------------
        # 4. Execute browser automation exactly once
        # --------------------------------------------

        result = BrowserService().run_full_order(
            payload,
            identity_data=identity_data,
            payment_data=payment_data,
            cvv=cvv,
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                "Browser automation returned an invalid result."
            )

        automation_result = result.get(
            "status",
            "MANUAL_REVIEW_REQUIRED",
        )

        # --------------------------------------------
        # 5. Update database based on actual result
        # --------------------------------------------

        if automation_result in ("ORDER_PLACED", "ORDER_SUBMITTED"):

            # Both values are accepted for compatibility.
            order.status = "ORDER_PLACED"
            order.automation_status = "ORDER_PLACED"

            # Remove encrypted payment and identity information
            # after successful order placement.
            order.encrypted_ssn = None
            order.encrypted_dob = None
            order.encrypted_payment_data = None

        else:

            # Order Summary alone is not successful placement.
            order.status = "MANUAL_REVIEW_REQUIRED"
            order.automation_status = "MANUAL_REVIEW_REQUIRED"

        db.commit()

        # --------------------------------------------
        # 6. Return the complete browser result
        # --------------------------------------------

        return result

    except Exception as exc:

        db.rollback()

        order.status = "MANUAL_REVIEW_REQUIRED"
        order.automation_status = "MANUAL_REVIEW_REQUIRED"

        db.commit()

        return {
            "status": "MANUAL_REVIEW_REQUIRED",
            "message": (
                "Automation could not be completed. "
                "Manual review is required."
            ),
            "error": str(exc),
            "current_url": None,
            "portal_order_id": None,
            "steps": [],
            "screenshot": None,
        }

    finally:

        if identity_data is not None:
            identity_data.clear()

        if payment_data is not None:
            payment_data.clear()

        ssn = None
        dob = None
        cvv = None
        identity_data = None
        payment_data = None
        encrypted_cvv = None
