
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.services.api_auth_service import verify_secure_api_token
from app.services.order_automation_service import execute_order_automation


router = APIRouter(
    prefix="/api/automation",
    tags=["Browser Automation"],
)





@router.post("/run/{order_id}")
def run_full_order(
    order_id: str,
    authenticated: bool = Depends(verify_secure_api_token),
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

    if order.automation_status == "IN_PROGRESS":
        raise HTTPException(
            status_code=409,
            detail="Automation is already running for this order.",
        )

    ez_enroll = (order.qualification or {}).get(
        "ez_enroll", False
    )

    if ez_enroll:
        raise HTTPException(
            status_code=422,
            detail=(
                "EZ-Enroll automation must be started through "
                "POST /api/orders/create with encrypted CVV."
            ),
        )

    result = execute_order_automation(
        db=db,
        order=order,
        encrypted_cvv=None,
    )

    return {
        "order_id": order.order_id,
        **result,
    }

