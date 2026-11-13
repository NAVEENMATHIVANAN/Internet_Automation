
from typing import Literal
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from pydantic import field_validator, model_validator
import re

class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class CustomerSchema(StrictBaseModel):
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


class ServiceAddressSchema(StrictBaseModel):
    zip_code: str
    address_line_1: str
    unit_type: str | None = None
    unit_number: str | None = None
    city: str
    state: str
    dwelling_type: Literal[
        "HOUSE", "CONDO", "TOWNHOUSE", "APARTMENT", "DUPLEX"
    ]
    ownership: Literal["OWN", "RENT"]
    moving_status: bool
    move_in_date: str | None = None
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

    @field_validator("move_in_date")
    @classmethod
    def validate_move_in_date(cls, value):
        if value and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
           raise ValueError("Move-in date must use DD/MM/YYYY format")
        return value

class OrderSchema(StrictBaseModel):
    provider: str
    customer_type: Literal["NEW", "TRANSFER"]
    service_category: Literal["INTERNET"]
    internet_speed_mbps: int = Field(gt=0)
    pricing_term: Literal["1_YEAR", "5_YEAR"]
    video_service: bool = False
    video_package: Literal[
      "ULTIMATE_TV",
      "POPULAR_TV",
      "WORLD_SOCCER_TICKET"
    ] | None = None

    phone_service: bool = False
    phone_package: Literal[
    "PROVIDERXX_VOICE_PREMIER"
    ] | None = None

    now_tv: bool = False
    equipment_type: Literal[
        "LEASED_GATEWAY", "CUSTOMER_OWNED"
    ]

    @model_validator(mode="after")
    def validate_addon_packages(self):
        if self.video_service and not self.video_package:
            raise ValueError(
                "Select a video package when video_service is enabled"
            )

        if not self.video_service and self.video_package:
            raise ValueError(
                "video_package requires video_service=True"
            )

        if self.phone_service and not self.phone_package:
            raise ValueError(
                "Select a phone package when phone_service is enabled"
            )

        if not self.phone_service and self.phone_package:
            raise ValueError(
                "phone_package requires phone_service=True"
            )

        return self

class AdditionalAddressSchema(StrictBaseModel):
    address_line_1: str
    unit_type: str | None = None
    unit_number: str | None = None
    city: str
    state: str
    zip_code: str

class QualificationSchema(StrictBaseModel):
    account_holder_name: str
    speaking_to_account_holder: bool
    existing_provider_customer: bool
    ez_enroll: bool
    autopay_paperless_discount: bool
    mailing_same_as_service: bool
    shipping_same_as_service: bool
    mailing_address: AdditionalAddressSchema | None = None
    shipping_address: AdditionalAddressSchema | None = None
    account_disclosure_acknowledged: bool = False
    ez_enroll_disclosure_acknowledged: bool = False
    autopay_paperless_disclosure_acknowledged: bool = False


class InstallationSchema(StrictBaseModel):
    installation_type: Literal[
        "STANDARD_SHIPPING", "PRO_INSTALL"
    ]

    preferred_date: str | None = None

    preferred_time: Literal[
        "Morning",
        "Afternoon",
        "Evening"
    ] | None = None

    installation_disclosure_acknowledged: bool = False

    @field_validator("preferred_date")
    @classmethod
    def validate_preferred_date(cls, value):
        if value is None:
            return value

        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError(
                "Installation date must use YYYY-MM-DD format"
            )

        return value

    @model_validator(mode="after")
    def validate_installation_details(self):
        if self.installation_type == "PRO_INSTALL":
            if not self.preferred_date:
                raise ValueError(
                    "Professional installation requires a preferred date"
                )

            if not self.preferred_time:
                raise ValueError(
                    "Professional installation requires a preferred time"
                )

        return self


class DisclosureSchema(StrictBaseModel):
    broadband_label_choice: Literal[
        "REQUESTED", "NOT_REQUESTED"
    ]
    broadband_label_acknowledged: bool
    payment_disclosure_acknowledged: bool = False
    credit_card_billing_same_as_service: bool = False


class OrderCreateSchema(StrictBaseModel):
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


class OrderResponseSchema(StrictBaseModel):
    order_id: str
    status: str
    message: str
    automation_status: str


class OrderStatusSchema(StrictBaseModel):
    order_id: str
    status: str
    automation_status: str
    created_at: str | None = None
