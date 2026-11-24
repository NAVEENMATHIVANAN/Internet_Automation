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


def decrypt_and_validate_payment(encrypted_payment: dict, encrypted_cvv: str):
    required = {
        "encrypted_card_type", "encrypted_card_number",
        "encrypted_cardholder_name", "encrypted_expiry_month",
        "encrypted_expiry_year",
    }
    if not isinstance(encrypted_payment, dict) or set(encrypted_payment) != required:
        raise ValueError("Invalid encrypted payment structure.")

    try:
        payment_data = {
            "card_type": decrypt_with_private_key(encrypted_payment["encrypted_card_type"]),
            "card_number": decrypt_with_private_key(encrypted_payment["encrypted_card_number"]),
            "cardholder_name": decrypt_with_private_key(encrypted_payment["encrypted_cardholder_name"]),
            "expiry_month": decrypt_with_private_key(encrypted_payment["encrypted_expiry_month"]),
            "expiry_year": decrypt_with_private_key(encrypted_payment["encrypted_expiry_year"]),
        }
        cvv = decrypt_with_private_key(encrypted_cvv)
        allowed = {"Visa", "MasterCard", "American Express", "Discover"}
        if payment_data["card_type"] not in allowed:
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
        raise ValueError("Encrypted payment details could not be validated.") from None


def execute_order_automation(db, order, run_request) -> dict:
    identity_data = None
    payment_data = None
    ssn = dob = cvv = None
    try:
        ez_enroll = bool((order.qualification or {}).get("ez_enroll", False))

        if ez_enroll:
            if run_request.encrypted_identity is not None:
                raise ValueError("Identity details are not accepted for EZ-Enroll.")
            if run_request.encrypted_payment is None or not run_request.encrypted_cvv:
                raise ValueError("Encrypted payment details and CVV are required.")
            payment_data, cvv = decrypt_and_validate_payment(
                run_request.encrypted_payment.model_dump(),
                run_request.encrypted_cvv,
            )
        else:
            if run_request.encrypted_payment is not None or run_request.encrypted_cvv is not None:
                raise ValueError("Payment details are not accepted for the credit-check workflow.")
            if run_request.encrypted_identity is None:
                raise ValueError("Encrypted SSN and DOB are required.")
            ssn = decrypt_with_private_key(run_request.encrypted_identity.encrypted_ssn)
            dob = decrypt_with_private_key(run_request.encrypted_identity.encrypted_dob)
            validate_identity(ssn, dob)
            identity_data = {"ssn": ssn, "dob": dob}

        order.status = "IN_PROGRESS"
        order.automation_status = "IN_PROGRESS"
        # Ensure legacy sensitive columns remain empty. Never persist request data.
        order.encrypted_ssn = None
        order.encrypted_dob = None
        order.encrypted_payment_data = None
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
            payload, identity_data=identity_data,
            payment_data=payment_data, cvv=cvv,
        )
        if not isinstance(result, dict):
            raise RuntimeError("Browser automation returned an invalid result.")

        if result.get("status") in ("ORDER_PLACED", "ORDER_SUBMITTED"):
            order.status = "ORDER_PLACED"
            order.automation_status = "ORDER_PLACED"
        else:
            order.status = "MANUAL_REVIEW_REQUIRED"
            order.automation_status = "MANUAL_REVIEW_REQUIRED"
        db.commit()
        return result

    except Exception:
        db.rollback()
        order.status = "MANUAL_REVIEW_REQUIRED"
        order.automation_status = "MANUAL_REVIEW_REQUIRED"
        order.encrypted_ssn = None
        order.encrypted_dob = None
        order.encrypted_payment_data = None
        db.commit()
        return {
            "status": "MANUAL_REVIEW_REQUIRED",
            "message": "Automation could not be completed. Manual review is required.",
            "error": "Sensitive data validation or automation failed. Review server-side operational logs without recording request values.",
            "current_url": None, "portal_order_id": None,
            "steps": [], "screenshot": None,
        }
    finally:
        if identity_data is not None:
            identity_data.clear()
        if payment_data is not None:
            payment_data.clear()
        ssn = dob = cvv = None
        identity_data = payment_data = None
