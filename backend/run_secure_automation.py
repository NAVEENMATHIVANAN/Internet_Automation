
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
import time
from datetime import datetime, date
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 3
MAX_WAIT_SECONDS = 30 * 60

TERMINAL_STATUSES = {
    "ORDER_PLACED",
    "MANUAL_REVIEW_REQUIRED",
    "FAILED",
    "CANCELLED",
}


def api_request(url: str, method: str = "GET", payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")

    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8") or "{}")
            return response.status, data

    except HTTPError as exc:
        try:
            response_data = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            response_data = {}

        detail = response_data.get("detail", "Request rejected by API")
        raise RuntimeError(
            f"API returned HTTP {exc.code}: {detail}"
        ) from None

    except URLError:
        raise RuntimeError(
            "Could not connect to the API. Check the server URL and that FastAPI is running."
        ) from None

    except TimeoutError:
        raise RuntimeError(
            "The API request timed out. Check the order status before trying again."
        ) from None


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
    _, response = api_request(
        f"{base_url}/api/orders/security/public-key"
    )

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

    card_type = prompt_secret(
        "Simulator card type (Visa/MasterCard/American Express/Discover)"
    )

    allowed = {
        "Visa",
        "MasterCard",
        "American Express",
        "Discover",
    }

    if card_type not in allowed:
        raise ValueError(
            "Card type must be Visa, MasterCard, American Express, or Discover."
        )

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
            "encrypted_card_number": encrypt_value(
                public_key, normalized_number
            ),
            "encrypted_cardholder_name": encrypt_value(
                public_key, cardholder
            ),
            "encrypted_expiry_month": encrypt_value(public_key, month),
            "encrypted_expiry_year": encrypt_value(public_key, year),
        },
        "encrypted_cvv": encrypt_value(public_key, cvv),
    }


def print_result(result: dict) -> None:
    """Print only the backend response, never the submitted sensitive values."""
    print("\nBackend response:")
    print(json.dumps(result, indent=2))


def get_suggestions(result: dict) -> list[dict]:
    suggestions = result.get("address_suggestions") or []

    if not isinstance(suggestions, list):
        return []

    return [
        item for item in suggestions
        if isinstance(item, dict)
        and item.get("suggestion_id")
        and item.get("address")
    ]


def choose_address(suggestions: list[dict]) -> str:
    print("\n" + "=" * 60)
    print("ADDRESS NOT MATCHED")
    print("=" * 60)
    print("Please select one of the suggested addresses:\n")

    for index, suggestion in enumerate(suggestions, start=1):
        print(f"{index}. {suggestion['address']}")

    none_option = len(suggestions) + 1
    print(f"{none_option}. None of these")

    while True:
        choice = input(
            f"\nChoose an option [1-{none_option}]: "
        ).strip()

        if not choice.isdigit():
            print("Enter a valid option number.")
            continue

        selected = int(choice)

        if 1 <= selected <= len(suggestions):
            return suggestions[selected - 1]["suggestion_id"]

        if selected == none_option:
            return "NONE_OF_THESE"

        print("Invalid selection. Please choose one of the displayed options.")


def get_providers(result: dict) -> list[str]:
    providers = result.get("available_providers") or []

    if not isinstance(providers, list):
        return []

    cleaned = []
    seen = set()

    for provider in providers:
        if not isinstance(provider, str) or not provider.strip():
            continue

        value = provider.strip()
        key = value.casefold()

        if key not in seen:
            seen.add(key)
            cleaned.append(value)

    return cleaned


def choose_provider(providers: list[str]) -> str:
    print("\n" + "=" * 60)
    print("PROVIDER CONFIRMATION")
    print("=" * 60)
    print("The portal returned these available providers:\n")

    for index, provider in enumerate(providers, start=1):
        print(f"{index}. {provider}")

    while True:
        choice = input(
            f"\nChoose a provider [1-{len(providers)}]: "
        ).strip()

        if not choice.isdigit():
            print("Enter a valid option number.")
            continue

        selected = int(choice)

        if 1 <= selected <= len(providers):
            return providers[selected - 1]

        print("Invalid selection. Choose one of the displayed providers.")


def submit_provider_selection(
    base_url: str,
    order_id: str,
    provider: str,
) -> dict:
    encoded_order_id = quote(order_id, safe="")
    url = (
        f"{base_url}/api/orders/{encoded_order_id}/provider-selection"
    )

    _, result = api_request(
        url,
        method="POST",
        payload={"provider": provider},
    )

    return result


def get_order_status(base_url: str, order_id: str) -> dict:
    encoded_order_id = quote(order_id, safe="")
    url = f"{base_url}/api/orders/{encoded_order_id}/status"

    _, result = api_request(url)
    return result


def submit_address_selection(
    base_url: str,
    order_id: str,
    suggestion_id: str,
) -> dict:
    encoded_order_id = quote(order_id, safe="")
    url = (
        f"{base_url}/api/orders/{encoded_order_id}/address-selection"
    )

    _, result = api_request(
        url,
        method="POST",
        payload={"suggestion_id": suggestion_id},
    )

    return result


def monitor_order(
    base_url: str,
    order_id: str,
    initial_result: dict,
) -> dict:
    """Handle address/provider decisions and monitor the same order to completion."""

    result = initial_result
    started_at = time.monotonic()
    last_status = None

    while time.monotonic() - started_at < MAX_WAIT_SECONDS:
        automation_status = (
            result.get("automation_status")
            or result.get("status")
            or ""
        ).upper()

        # Address suggestion pause: ask the caller and resume the same session.
        if automation_status == "ADDRESS_SELECTION_REQUIRED":
            suggestions = get_suggestions(result)

            if not suggestions:
                result = get_order_status(base_url, order_id)
                suggestions = get_suggestions(result)

            if not suggestions:
                raise RuntimeError(
                    "The backend requires an address selection but returned "
                    "no address suggestions. Check the order status endpoint."
                )

            selected_id = choose_address(suggestions)

            print("\nSubmitting your address selection...")

            selection_result = submit_address_selection(
                base_url,
                order_id,
                selected_id,
            )

            print(
                selection_result.get(
                    "message",
                    "Address selection received by the backend.",
                )
            )

            if selected_id == "NONE_OF_THESE":
                print(
                    "\nYou selected 'None of these'. "
                    "The order should be sent for manual review."
                )

            # Do not call /run again. Wait for the existing worker to resume.
            result = get_order_status(base_url, order_id)
            last_status = None

            while (
                result.get("automation_status", result.get("status", "")).upper()
                == "ADDRESS_SELECTION_REQUIRED"
            ):
                if time.monotonic() - started_at >= MAX_WAIT_SECONDS:
                    raise RuntimeError(
                        "Timed out while waiting for the browser to resume "
                        "after address selection."
                    )

                time.sleep(POLL_INTERVAL_SECONDS)
                result = get_order_status(base_url, order_id)

            continue

        # Provider confirmation pause (A3).
        if automation_status == "PROVIDER_SELECTION_REQUIRED":
            providers = get_providers(result)

            if not providers:
                # The status endpoint may publish options after the initial
                # run response, so refresh once before treating it as invalid.
                result = get_order_status(base_url, order_id)
                providers = get_providers(result)

            if not providers:
                raise RuntimeError(
                    "The backend requires provider confirmation but returned "
                    "no available providers. Check the order status endpoint."
                )

            selected_provider = choose_provider(providers)

            print(f"\nConfirming {selected_provider} with the backend...")

            selection_result = submit_provider_selection(
                base_url,
                order_id,
                selected_provider,
            )

            print(
                selection_result.get(
                    "message",
                    "Provider confirmation received by the backend.",
                )
            )

            # Do not call /run again. Wait for the same browser worker.
            result = get_order_status(base_url, order_id)
            last_status = None

            while (
                result.get("automation_status", result.get("status", "")).upper()
                == "PROVIDER_SELECTION_REQUIRED"
            ):
                if time.monotonic() - started_at >= MAX_WAIT_SECONDS:
                    raise RuntimeError(
                        "Timed out while waiting for the browser to resume "
                        "after provider confirmation."
                    )

                time.sleep(POLL_INTERVAL_SECONDS)
                result = get_order_status(base_url, order_id)

            continue

        # A terminal status means the backend has finished processing.
        if automation_status in TERMINAL_STATUSES:
            return result

        # Show progress only when the status changes.
        if automation_status and automation_status != last_status:
            print(f"\nOrder status: {automation_status}")
            last_status = automation_status

        time.sleep(POLL_INTERVAL_SECONDS)
        result = get_order_status(base_url, order_id)

    raise RuntimeError(
        "The order has not reached a final status within 30 minutes. "
        "Check the order status endpoint before taking further action."
    )


def main() -> int:
    print("Secure order automation launcher (simulator testing only)")
    print(
        "Important: after submitting, wait for the complete browser workflow. "
        "Do not start the same order again. Provider confirmation and "
        "address selection will be handled during this run."
    )

    base_url = (
        input(f"API base URL [{DEFAULT_BASE_URL}]: ").strip()
        or DEFAULT_BASE_URL
    )
    base_url = base_url.rstrip("/")

    if not base_url.startswith(("http://", "https://")):
        print(
            "ERROR: API URL must start with http:// or https://.",
            file=sys.stderr,
        )
        return 2

    if base_url.startswith("http://") and not any(
        host in base_url
        for host in (
            "http://127.0.0.1",
            "http://localhost",
            "http://[::1]",
        )
    ):
        print(
            "ERROR: Use HTTPS for any non-local API host.",
            file=sys.stderr,
        )
        return 2

    order_id = input(
        "Order ID from POST /api/orders/create: "
    ).strip()

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

        payload = (
            build_case1_payload(public_key)
            if choice == "1"
            else build_case2_payload(public_key)
        )

        encoded_order_id = quote(order_id, safe="")
        run_url = f"{base_url}/api/orders/{encoded_order_id}/run"

        print("\nStarting order automation...")

        status_code, result = api_request(
            run_url,
            method="POST",
            payload=payload,
        )

        print(f"\nAutomation request received (HTTP {status_code}).")

        # Remove local references to encrypted request data when no longer needed.
        payload.clear()
        payload = None

        final_result = monitor_order(
            base_url,
            order_id,
            result,
        )

        print("\n" + "=" * 60)
        print("ORDER AUTOMATION FINISHED")
        print("=" * 60)
        print_result(final_result)

        final_status = (
            final_result.get("automation_status")
            or final_result.get("status")
            or ""
        ).upper()

        if final_status == "ORDER_PLACED":
            print("\nOrder automation completed successfully.")
            return 0

        print("\nAutomation did not complete successfully. Review the backend response.")
        return 1

    except KeyboardInterrupt:
        print(
            "\nInterrupted by user. The backend may still be processing "
            "the order. Check its status before taking further action.",
            file=sys.stderr,
        )
        return 130

    except (ValueError, RuntimeError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    raise SystemExit(main())
