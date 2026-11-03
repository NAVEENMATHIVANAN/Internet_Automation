
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from pydantic import field_validator, model_validator
import re


class CustomerSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prefix: str | None = None
    first_name: str = Field(min_length=1, max_length=50)
    middle_initial: str | None = None
    last_name: str = Field(min_length=1, max_length=50)
    suffix: str | None = None

    phone: str
    email: EmailStr

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        digits = re.sub(r"\D", "", value)

        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        if len(digits) != 10:
            raise ValueError("Enter a valid US phone number")

        return digits


class ServiceAddressSchema(BaseModel):
    zip_code: str
    address_line_1: str
    unit_type: str | None = None
    unit_number: str | None = None
    city: str
    state: str
    dwelling_type: Literal[
        "HOUSE", "CONDO", "TOWNHOUSE", "APARTMENT"
    ]
    ownership: Literal["OWN", "RENT"]
    moving_status: bool

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, value):
        if not re.fullmatch(r"\d{5}(-\d{4})?", value):
            raise ValueError("Invalid US ZIP code")
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value):
        value = value.upper()

        if not re.fullmatch(r"[A-Z]{2}", value):
            raise ValueError("State must be a two-letter code")

        return value


class OrderSchema(BaseModel):
    provider: str
    customer_type: Literal["NEW", "TRANSFER"]
    service_category: Literal["INTERNET"]
    internet_speed_mbps: int = Field(gt=0)
    pricing_term: Literal["1_YEAR", "5_YEAR"]
    video_service: bool = False
    phone_service: bool = False
    equipment_type: Literal[
        "LEASED_GATEWAY", "CUSTOMER_OWNED"
    ]

class AdditionalAddressSchema(BaseModel):
    address_line_1: str
    unit_type: str | None = None
    unit_number: str | None = None
    city: str
    state: str
    zip_code: str

class QualificationSchema(BaseModel):
    account_holder_name: str
    speaking_to_account_holder: bool
    existing_provider_customer: bool
    ez_enroll: bool
    autopay_paperless_discount: bool
    mailing_same_as_service: bool
    shipping_same_as_service: bool
    mailing_address: AdditionalAddressSchema | None = None
    shipping_address: AdditionalAddressSchema | None = None


class InstallationSchema(BaseModel):
    installation_type: Literal[
        "STANDARD_SHIPPING", "PRO_INSTALL"
    ]
    preferred_date: str | None = None
    preferred_time: str | None = None


class DisclosureSchema(BaseModel):
    broadband_label_choice: Literal[
        "REQUESTED", "NOT_REQUESTED"
    ]
    broadband_label_acknowledged: bool


class OrderCreateSchema(BaseModel):
    customer: CustomerSchema
    service_address: ServiceAddressSchema
    order: OrderSchema
    qualification: QualificationSchema
    installation: InstallationSchema
    disclosures: DisclosureSchema

    @model_validator(mode="after")
    def validate_additional_addresses(self):
        if (
            not self.qualification.mailing_same_as_service
            and not self.qualification.mailing_address
        ):
            raise ValueError("Mailing address is required")

        if (
            not self.qualification.shipping_same_as_service
            and not self.qualification.shipping_address
        ):
            raise ValueError("Shipping address is required")

        return self


class OrderResponseSchema(BaseModel):
    order_id: str
    status: str
    message: str
    automation_status: str


class OrderStatusSchema(BaseModel):
    order_id: str
    status: str
    automation_status: str
    created_at: str | None = None
