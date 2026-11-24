from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.schemas.order_schema import (
    OrderCreateSchema, AutomationRunSchema, OrderResponseSchema, OrderStatusSchema,
)
from app.services.order_automation_service import execute_order_automation
from app.services.rsa_encryption_service import KEY_DIR

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.get("/security/public-key", tags=["Security"])
def get_public_key():
    key_path = KEY_DIR / "public_key.pem"
    if not key_path.is_file():
        raise HTTPException(status_code=500, detail="Encryption public key is not configured.")
    return {"algorithm": "RSA-OAEP-SHA256", "public_key": key_path.read_text(encoding="utf-8")}


@router.post("/create", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
def create_order(request: OrderCreateSchema, db: Session = Depends(get_db)):
    try:
        new_order = Order(
            customer_data=request.customer.model_dump(),
            service_address=request.service_address.model_dump(),
            order_data=request.order.model_dump(),
            qualification=request.qualification.model_dump(),
            installation=request.installation.model_dump(),
            disclosures=request.disclosures.model_dump(),
            # Never store sensitive request fields. These legacy columns stay NULL.
            encrypted_ssn=None, encrypted_dob=None, encrypted_payment_data=None,
            status="RECEIVED", automation_status="PENDING",
        )
        db.add(new_order)
        db.commit()
        db.refresh(new_order)
        return {
            "order_id": new_order.order_id, "status": new_order.status,
            "message": "Order created. Submit encrypted sensitive details to the run endpoint to start automation.",
            "automation_status": new_order.automation_status,
        }
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to create the order.") from None


@router.post("/{order_id}/run", response_model=OrderResponseSchema)
def run_order_automation(order_id: str, request: AutomationRunSchema, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.automation_status != "PENDING":
        raise HTTPException(status_code=409, detail="Automation has already started or requires manual review. Create a new order rather than resubmitting this one.")
    result = execute_order_automation(db=db, order=order, run_request=request)
    return {
        "order_id": order.order_id, "status": order.status,
        "message": result.get("message") or result.get("confirmation_message") or "Automation processing finished.",
        "automation_status": order.automation_status,
        "portal_order_id": result.get("portal_order_id"),
        "current_url": result.get("current_url"),
        "steps": result.get("steps", []),
        "error": result.get("error"),
        "screenshot": result.get("screenshot"),
    }


@router.get("/{order_id}/status", response_model=OrderStatusSchema)
def get_order_status(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {
        "order_id": order.order_id, "status": order.status,
        "automation_status": order.automation_status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
