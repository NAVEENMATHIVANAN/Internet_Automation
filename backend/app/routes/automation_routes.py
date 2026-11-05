from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.order import Order
from app.services.browser_service import BrowserService

router = APIRouter(prefix='/api/automation', tags=['Browser Automation'])

@router.post('/run/{order_id}')
def run_full_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail='Order not found.')
    if order.automation_status == 'IN_PROGRESS':
        raise HTTPException(status_code=409, detail='Automation is already running for this order.')

    order.status = 'IN_PROGRESS'
    order.automation_status = 'IN_PROGRESS'
    db.commit()

    payload = {
        'customer': order.customer_data,
        'service_address': order.service_address,
        'order': order.order_data,
        'qualification': order.qualification,
        'installation': order.installation,
        'disclosures': order.disclosures,
    }
    result = BrowserService().run_full_order(payload)
    order.automation_status = result.get('status', 'MANUAL_REVIEW_REQUIRED')
    order.status = 'READY_FOR_REVIEW' if result.get('status') == 'ORDER_SUMMARY_REACHED' else 'MANUAL_REVIEW_REQUIRED'
    db.commit()
    return {'order_id': order.order_id, **result}
