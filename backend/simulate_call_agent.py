
import requests
import json

API_URL = "http://127.0.0.1:8000/api/orders/create"

# Simulated information collected during a customer call.
# Replace these synthetic values with the actual call-agent output.
customer_order = {
    "customer": {
        "prefix": "Mr",
        "first_name": "John",
        "middle_initial": "A",
        "last_name": "Smith",
        "phone": "5551234567",
        "email": "john@example.com"
    },
    "service_address": {
        "zip_code": "12345",
        "address_line_1": "123 Example Street",
        "city": "Example City",
        "state": "CA",
        "dwelling_type": "HOUSE",
        "ownership": "OWN",
        "moving_status": False
    },
    "order": {
        "provider": "XFINITY",
        "customer_type": "NEW",
        "service_category": "INTERNET",
        "internet_speed_mbps": 300,
        "pricing_term": "1_YEAR",
        "video_service": False,
        "phone_service": False,
        "equipment_type": "LEASED_GATEWAY"
    },
    "qualification": {
        "account_holder_name": "John Smith",
        "speaking_to_account_holder": True,
        "existing_provider_customer": False,
        "ez_enroll": False,
        "autopay_paperless_discount": False,
        "mailing_same_as_service": True,
        "shipping_same_as_service": True
    },
    "installation": {
        "installation_type": "STANDARD_SHIPPING",
        "preferred_date": None,
        "preferred_time": None
    },
    "disclosures": {
        "broadband_label_choice": "NOT_REQUESTED",
        "broadband_label_acknowledged": True
    }
}


def submit_customer_order():
    print("Submitting call-agent data to Internet Order API...")

    try:
        response = requests.post(
            API_URL,
            json=customer_order,
            timeout=30
        )

        print("HTTP Status:", response.status_code)

        if response.status_code == 201:
            result = response.json()

            print("\nORDER SUBMITTED SUCCESSFULLY")
            print("Order ID:", result["order_id"])
            print("Order Status:", result["status"])
            print("Automation Status:", result["automation_status"])

            print("\nFull API Response:")
            print(json.dumps(result, indent=4))

        else:
            print("\nORDER SUBMISSION FAILED")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("Cannot connect to FastAPI. Check whether the backend is running.")

    except requests.exceptions.Timeout:
        print("The API request timed out.")

    except requests.exceptions.RequestException as error:
        print("Request error:", error)


if __name__ == "__main__":
    submit_customer_order()
