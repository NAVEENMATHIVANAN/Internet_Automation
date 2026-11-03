
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.schemas.order_schema import (
    OrderCreateSchema,
    OrderResponseSchema,
    OrderStatusSchema
)

router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"]
)


@router.post(
    "/create",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED
)
def create_order(
    request: OrderCreateSchema,
    db: Session = Depends(get_db)
):
    try:
        new_order = Order(
            customer_data=request.customer.model_dump(),
            service_address=request.service_address.model_dump(),
            order_data=request.order.model_dump(),
            qualification=request.qualification.model_dump(),
            installation=request.installation.model_dump(),
            disclosures=request.disclosures.model_dump(),
            status="RECEIVED",
            automation_status="PENDING"
        )

        db.add(new_order)
        db.commit()
        db.refresh(new_order)

        return {
            "order_id": new_order.order_id,
            "status": new_order.status,
            "message": "Customer order received and saved successfully.",
            "automation_status": new_order.automation_status
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the order."
        )


@router.get(
    "/{order_id}/status",
    response_model=OrderStatusSchema
)
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.order_id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found."
        )

    return {
        "order_id": order.order_id,
        "status": order.status,
        "automation_status": order.automation_status,
        "created_at": (
            order.created_at.isoformat()
            if order.created_at else None
        )
    }
