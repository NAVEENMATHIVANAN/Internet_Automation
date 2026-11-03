from app.schemas.order_schema import OrderCreateSchema

sample_order = {
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
        "installation_type": "STANDARD_SHIPPING"
    },
    "disclosures": {
        "broadband_label_choice": "NOT_REQUESTED",
        "broadband_label_acknowledged": True
    }
}

validated = OrderCreateSchema(**sample_order)

print("Schema validation successful!")
print(validated.model_dump())