
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.services.browser_service import BrowserService

router = APIRouter(
    prefix="/api/automation",
    tags=["Browser Automation"]
)


class PortalInspectionRequest(BaseModel):
    url: HttpUrl | None = None


@router.post("/inspect")
def inspect_portal(request: PortalInspectionRequest):

    try:
        service = BrowserService()

        result = service.inspect_portal(
            str(request.url) if request.url else None
        )

        return result

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )
