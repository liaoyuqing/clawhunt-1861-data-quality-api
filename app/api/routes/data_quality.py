"""GET /api/dash/data-quality."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import Caller, assert_site_allowed, get_session, require_scope
from app.config import get_settings
from app.di import Composer
from app.errors import FieldListEmptyError, ValidationError
from app.repositories.caliber_repo import FieldListEmpty
from app.schemas.data_quality import DataQualityData
from app.schemas.envelope import Envelope

router = APIRouter(prefix="/dash", tags=["dashboard"])


def get_composer(request: Request) -> Composer:
    composer: Composer = request.app.state.composer
    return composer


@router.get(
    "/data-quality",
    response_model=Envelope[DataQualityData],
    summary="Enterprise profile completeness aggregate for the management dashboard",
    description=(
        "Aggregates the CRM read-only slice for one site: overall completeness against the "
        "95% target, per member-manager completeness and enterprise count, the five fields "
        "with the most gaps, capability-card completion and 90-day freshness, and the list of "
        "enterprises below 80% completeness projected to id and name only."
    ),
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Token lacks the dash.quality.read scope"},
        422: {"description": "Invalid query or an empty caliber field list (FIELD_LIST_EMPTY)"},
    },
)
def data_quality(
    request: Request,
    site_id: uuid.UUID = Query(description="Member-space site id (UUID)"),
    staff_id: uuid.UUID | None = Query(default=None, description="Optional member-manager id"),
    limit: int = Query(default=50, ge=1, le=200, description="Max rows in low_completeness"),
    session: Session = Depends(get_session),
    caller: Caller = Depends(require_scope(get_settings().required_scope)),
) -> Envelope[DataQualityData]:
    assert_site_allowed(caller, site_id)
    require_site_of(caller, site_id)

    service = get_composer(request).build(session)
    try:
        data = service.get(site_id, staff_id)
    except FieldListEmpty as exc:
        raise FieldListEmptyError() from exc

    if limit < len(data.low_completeness):
        data = data.model_copy(update={"low_completeness": data.low_completeness[:limit]})
    return Envelope[DataQualityData](data=data, request_id=getattr(request.state, "request_id", ""))


def require_site_of(caller: Caller, site_id: uuid.UUID) -> None:
    """Site must belong to the caller org; the token carries both."""
    if not caller.org_id:
        raise ValidationError("org_id missing from token")
