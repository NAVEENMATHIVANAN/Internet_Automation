
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.schemas.order_schema import (
    OrderCreateSchema,
    OrderResponseSchema,
    OrderStatusSchema,
)
from app.services.order_automation_service import execute_order_automation


router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)


@router.post(
    "/create",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    request: OrderCreateSchema,
    db: Session = Depends(get_db),
):
    try:
        encrypted_payment_data = (
            json.dumps(request.encrypted_payment.model_dump())
            if request.encrypted_payment
            else None
        )

        new_order = Order(
            customer_data=request.customer.model_dump(),
            service_address=request.service_address.model_dump(),
            order_data=request.order.model_dump(),
            qualification=request.qualification.model_dump(),
            installation=request.installation.model_dump(),
            disclosures=request.disclosures.model_dump(),

            encrypted_ssn=(
                request.encrypted_identity.encrypted_ssn
                if request.encrypted_identity
                else None
            ),
            encrypted_dob=(
                request.encrypted_identity.encrypted_dob
                if request.encrypted_identity
                else None
            ),
            encrypted_payment_data=encrypted_payment_data,

            status="RECEIVED",
            automation_status="PENDING",
        )

        db.add(new_order)
        db.commit()
        db.refresh(new_order)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the order.",
        )

    # Case 2: EZ-Enroll payment automation starts in this same request.
    if request.qualification.ez_enroll:
        result = execute_order_automation(
            db=db,
            order=new_order,
            encrypted_cvv=request.encrypted_cvv,
        )

        return {
            "order_id": new_order.order_id,
            "status": new_order.status,
            "message": result.get(
                "message",
                "Order received. Automation processing finished.",
            ),
            "automation_status": new_order.automation_status,
        }

    # Case 1 remains unchanged: create first, then use the existing
    # secure automation endpoint to run the credit-check workflow.
    return {
        "order_id": new_order.order_id,
        "status": new_order.status,
        "message": "Customer order received and saved successfully.",
        "automation_status": new_order.automation_status,
    }


@router.get(
    "/{order_id}/status",
    response_model=OrderStatusSchema,
)
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.order_id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    return {
        "order_id": order.order_id,
        "status": order.status,
        "automation_status": order.automation_status,
        "created_at": (
            order.created_at.isoformat()
            if order.created_at
            else None
        ),
    }
