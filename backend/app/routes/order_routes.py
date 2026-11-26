
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.order import Order
from app.schemas.order_schema import (
    OrderCreateSchema,
    AutomationRunSchema,
    OrderResponseSchema,
    OrderStatusSchema,
    AddressSelectionSchema,
    ProviderSelectionSchema,
)
from app.services.order_automation_service import execute_order_automation
from app.services.address_session_manager import address_session_manager
from app.services.rsa_encryption_service import KEY_DIR


router = APIRouter(prefix="/api/orders", tags=["Orders"])


def _worker(
    order_id: str,
    run_request: AutomationRunSchema,
    session,
):
    db = SessionLocal()

    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        if not order:
            raise RuntimeError("Order not found by automation worker.")

        def address_callback(suggestions):
            order.status = "ADDRESS_SELECTION_REQUIRED"
            order.automation_status = "ADDRESS_SELECTION_REQUIRED"
            db.commit()

            selected_id = session.publish_and_wait(
                suggestions,
                timeout=600,
            )

            if selected_id != "NONE_OF_THESE":
                order.status = "IN_PROGRESS"
                order.automation_status = "IN_PROGRESS"
                db.commit()

            return selected_id
        def provider_callback(providers):
            order.status = "PROVIDER_SELECTION_REQUIRED"
            order.automation_status = "PROVIDER_SELECTION_REQUIRED"
            db.commit()

            selected_provider = session.publish_providers_and_wait(
                providers,
                timeout=600,
            )

            order.status = "IN_PROGRESS"
            order.automation_status = "IN_PROGRESS"
            db.commit()

            return selected_provider

        result = execute_order_automation(
            db=db,
            order=order,
            run_request=run_request,
            address_selection_callback=address_callback,
            provider_selection_callback=provider_callback,
        )

        session.finish(result)

    except Exception:
        db.rollback()

        try:
            order = (
                db.query(Order)
                .filter(Order.order_id == order_id)
                .first()
            )

            if order:
                order.status = "MANUAL_REVIEW_REQUIRED"
                order.automation_status = "MANUAL_REVIEW_REQUIRED"
                db.commit()
        except Exception:
            db.rollback()

        session.finish({
            "status": "MANUAL_REVIEW_REQUIRED",
            "message": "Automation could not be completed. Manual review is required.",
            "error": "Automation worker failed.",
            "steps": [],
            "portal_order_id": None,
            "current_url": None,
            "screenshot": None,
        })

    finally:
        db.close()


def _response(
    order,
    result=None,
    suggestions=None,
    providers=None,
):
    result = result or {}

    if suggestions is not None:
        message = "Choose one of the suggested addresses to continue."
    elif providers is not None:
        message = "Confirm an available provider to continue."
    else:
        message = (
            result.get("message")
            or result.get("confirmation_message")
            or "Automation processing."
        )

    return {
        "order_id": order.order_id,
        "status": order.status,
        "message": message,
        "automation_status": order.automation_status,
        "portal_order_id": result.get("portal_order_id"),
        "current_url": result.get("current_url"),
        "steps": result.get("steps", []),
        "error": result.get("error"),
        "screenshot": result.get("screenshot"),
        "address_suggestions": suggestions,
        "available_providers": providers,
    }


@router.get("/security/public-key", tags=["Security"])
def get_public_key():
    key_path = KEY_DIR / "public_key.pem"

    if not key_path.is_file():
        raise HTTPException(
            status_code=500,
            detail="Encryption public key is not configured.",
        )

    return {
        "algorithm": "RSA-OAEP-SHA256",
        "public_key": key_path.read_text(encoding="utf-8"),
    }


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
        new_order = Order(
            customer_data=request.customer.model_dump(),
            service_address=request.service_address.model_dump(),
            order_data=request.order.model_dump(),
            qualification=request.qualification.model_dump(),
            installation=request.installation.model_dump(),
            disclosures=request.disclosures.model_dump(),
            encrypted_ssn=None,
            encrypted_dob=None,
            encrypted_payment_data=None,
            status="RECEIVED",
            automation_status="PENDING",
        )

        db.add(new_order)
        db.commit()
        db.refresh(new_order)

        return {
            "order_id": new_order.order_id,
            "status": new_order.status,
            "message": "Order created. Submit encrypted sensitive details to start automation.",
            "automation_status": new_order.automation_status,
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create the order.",
        ) from None


@router.post(
    "/{order_id}/run",
    response_model=OrderResponseSchema,
)
def run_order_automation(
    order_id: str,
    request: AutomationRunSchema,
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.order_id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if order.automation_status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Automation has already started or requires manual review.",
        )

    try:
        session = address_session_manager.create(order_id)

        order.status = "IN_PROGRESS"
        order.automation_status = "IN_PROGRESS"
        db.commit()

        worker = Thread(
            target=_worker,
            args=(
                order_id,
                request.model_copy(deep=True),
                session,
            ),
            daemon=True,
        )
        worker.start()

        initial = session.wait_for_initial_result(timeout=150)

        db.refresh(order)

        if initial["published"]:
            if initial["pending_type"] == "ADDRESS":
                return _response(
                    order,
                    suggestions=initial["suggestions"],
                )

            if initial["pending_type"] == "PROVIDER":
                return _response(
                    order,
                    providers=initial["providers"],
                )

        if initial["completed"]:
            return _response(
                order,
                result=initial["result"],
            )

        return {
            "order_id": order.order_id,
            "status": order.status,
            "message": "Automation is still running. Check the order status endpoint.",
            "automation_status": order.automation_status,
            "address_suggestions": None,
        }

    except Exception:
        db.rollback()
        address_session_manager.remove(order_id)

        raise HTTPException(
            status_code=500,
            detail="Unable to start order automation.",
        ) from None


@router.post("/{order_id}/address-selection")
def select_address(
    order_id: str,
    request: AddressSelectionSchema,
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.order_id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if order.automation_status != "ADDRESS_SELECTION_REQUIRED":
        raise HTTPException(
            status_code=409,
            detail="This order is not waiting for an address selection.",
        )

    session = address_session_manager.get(order_id)

    if not session:
        raise HTTPException(
            status_code=409,
            detail="The pending browser session is no longer available.",
        )

    try:
        session.choose(request.suggestion_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None

    if request.suggestion_id == "NONE_OF_THESE":
        return {
            "order_id": order_id,
            "message": "Address rejected. Automation will stop for manual review.",
            "automation_status": "ADDRESS_SELECTION_REQUIRED",
        }

    return {
        "order_id": order_id,
        "message": "Address selection received. The existing browser session is continuing.",
        "automation_status": "IN_PROGRESS",
    }

@router.post("/{order_id}/provider-selection")
def select_provider(
    order_id: str,
    request: ProviderSelectionSchema,
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.order_id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    if order.automation_status != "PROVIDER_SELECTION_REQUIRED":
        raise HTTPException(
            status_code=409,
            detail="This order is not waiting for provider confirmation.",
        )

    session = address_session_manager.get(order_id)

    if not session:
        raise HTTPException(
            status_code=409,
            detail="The pending browser session is no longer available.",
        )

    try:
        session.choose_provider(request.provider)

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None

    return {
        "order_id": order_id,
        "message": (
            "Provider confirmation received. "
            "The existing browser session is continuing."
        ),
        "automation_status": "IN_PROGRESS",
    }



@router.get(
    "/{order_id}/status",
    response_model=OrderStatusSchema,
)
def get_order_status(
    order_id: str,
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.order_id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found.",
        )

    session = address_session_manager.get(order_id)

    suggestions = None
    providers = None

    if session and not session.completed:
        if session.published:
            if session.pending_type == "ADDRESS":
                suggestions = session.suggestions

            elif session.pending_type == "PROVIDER":
                providers = session.providers

    return {
        "order_id": order.order_id,
        "status": order.status,
        "automation_status": order.automation_status,
        "created_at": (
            order.created_at.isoformat()
            if order.created_at else None
        ),
        "address_suggestions": suggestions,
        "available_providers": providers,
    }
