"""Collect simulator-only sensitive values, encrypt them locally, and start an order.

The plaintext values are never written to disk or printed. Use only with the
project's simulator/test environment. For remote hosts, HTTPS is mandatory.
"""
from __future__ import annotations

import base64
import getpass
import json
import re
import sys
from datetime import datetime, date
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 600  # Browser automation can take several minutes.


def api_request(url: str, method: str = "GET", payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8") or "{}")
    except HTTPError as exc:
        # Do not print request bodies or exception representations.
        try:
            response_data = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            response_data = {}
        detail = response_data.get("detail", "Request rejected by API")
        raise RuntimeError(f"API returned HTTP {exc.code}: {detail}") from None
    except URLError:
        raise RuntimeError("Could not connect to the API. Check the server URL and that FastAPI is running.") from None
    except TimeoutError:
        raise RuntimeError("The API request timed out. Check the order status before trying again.") from None


def encrypt_value(public_key, value: str) -> str:
    encrypted = public_key.encrypt(
        value.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(encrypted).decode("ascii")


def prompt_secret(label: str) -> str:
    value = getpass.getpass(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def get_public_key(base_url: str):
    _, response = api_request(f"{base_url}/api/orders/security/public-key")
    pem = response.get("public_key")
    if not isinstance(pem, str) or "BEGIN PUBLIC KEY" not in pem:
        raise RuntimeError("The API did not return a valid public key.")
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, rsa.RSAPublicKey):
        raise RuntimeError("The configured public key is not an RSA key.")
    if key.key_size < 2048:
        raise RuntimeError("The RSA key is too small; use at least 2048 bits.")
    return key


def validate_identity(ssn: str, dob: str) -> None:
    if not re.fullmatch(r"\d{3}-\d{2}-\d{4}", ssn):
        raise ValueError("SSN must use ###-##-#### format.")
    try:
        birth_date = datetime.strptime(dob, "%m/%d/%Y").date()
    except ValueError:
        raise ValueError("DOB must use MM/DD/YYYY format.") from None
    if birth_date >= date.today():
        raise ValueError("DOB must be a date in the past.")


def build_case1_payload(public_key) -> dict:
    print("\nCase 1 — Credit-check details")
    ssn = prompt_secret("Simulator SSN (###-##-####)")
    dob = prompt_secret("Simulator DOB (MM/DD/YYYY)")
    validate_identity(ssn, dob)
    return {
        "encrypted_identity": {
            "encrypted_ssn": encrypt_value(public_key, ssn),
            "encrypted_dob": encrypt_value(public_key, dob),
        }
    }


def build_case2_payload(public_key) -> dict:
    print("\nCase 2 — EZ-Enroll payment details")
    card_type = prompt_secret("Simulator card type (Visa/MasterCard/American Express/Discover)")
    allowed = {"Visa", "MasterCard", "American Express", "Discover"}
    if card_type not in allowed:
        raise ValueError("Card type must be Visa, MasterCard, American Express, or Discover.")

    card_number = prompt_secret("Simulator card number")
    normalized_number = re.sub(r"[\s-]", "", card_number)
    if not normalized_number.isdigit() or not 12 <= len(normalized_number) <= 19:
        raise ValueError("Card number must contain 12 to 19 digits.")

    cardholder = prompt_secret("Simulator cardholder name")
    month = prompt_secret("Expiry month (1-12)")
    year = prompt_secret("Expiry year (YYYY)")
    cvv = prompt_secret("Simulator CVV")
    if not month.isdigit() or not 1 <= int(month) <= 12:
        raise ValueError("Expiry month must be between 1 and 12.")
    if not re.fullmatch(r"\d{4}", year):
        raise ValueError("Expiry year must use YYYY format.")
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        raise ValueError("CVV must contain 3 or 4 digits.")

    return {
        "encrypted_payment": {
            "encrypted_card_type": encrypt_value(public_key, card_type),
            "encrypted_card_number": encrypt_value(public_key, normalized_number),
            "encrypted_cardholder_name": encrypt_value(public_key, cardholder),
            "encrypted_expiry_month": encrypt_value(public_key, month),
            "encrypted_expiry_year": encrypt_value(public_key, year),
        },
        "encrypted_cvv": encrypt_value(public_key, cvv),
    }


def main() -> int:
    print("Secure order automation launcher (simulator testing only)")
    print("Important: after submitting, wait for the complete browser workflow. Do not start the same order again.")
    base_url = input(f"API base URL [{DEFAULT_BASE_URL}]: ").strip() or DEFAULT_BASE_URL
    base_url = base_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        print("ERROR: API URL must start with http:// or https://.", file=sys.stderr)
        return 2
    if base_url.startswith("http://") and not any(
        host in base_url for host in ("http://127.0.0.1", "http://localhost", "http://[::1]")
    ):
        print("ERROR: Use HTTPS for any non-local API host.", file=sys.stderr)
        return 2

    order_id = input("Order ID from POST /api/orders/create: ").strip()
    if not order_id:
        print("ERROR: Order ID is required.", file=sys.stderr)
        return 2

    print("\nSelect the existing order workflow:")
    print("1. Case 1 — EZ-Enroll disabled (SSN + DOB)")
    print("2. Case 2 — EZ-Enroll enabled (card + CVV)")
    choice = input("Workflow [1/2]: ").strip()
    if choice not in {"1", "2"}:
        print("ERROR: Choose 1 or 2.", file=sys.stderr)
        return 2

    try:
        public_key = get_public_key(base_url)
        payload = build_case1_payload(public_key) if choice == "1" else build_case2_payload(public_key)
        # One POST: encrypted fields are attached automatically by this launcher.
        # The plaintext values are not included in this request.
        url = f"{base_url}/api/orders/{quote(order_id, safe='')}/run"
        status_code, result = api_request(url, method="POST", payload=payload)
        print(f"\nAutomation request completed (HTTP {status_code}).")
        # Only show response returned by the backend; never echo the input values.
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
