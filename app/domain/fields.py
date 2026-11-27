"""Field catalogue.

The catalogue only knows how to read a field key; it deliberately does not decide
*which* keys the dashboard scores. That list comes from the caliber library
(app.repositories.caliber_repo) at request time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.crm import Contact, Enterprise

Source = Literal["enterprise", "primary_contact"]


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    label: str
    source: Source
    attribute: str
    openapi_example: str


FIELD_CATALOG: dict[str, FieldSpec] = {
    "enterprise.industry": FieldSpec(
        key="enterprise.industry",
        label="行业",
        source="enterprise",
        attribute="industry",
        openapi_example="高端装备制造",
    ),
    "enterprise.track": FieldSpec(
        key="enterprise.track",
        label="赛道",
        source="enterprise",
        attribute="track",
        openapi_example="工业机器人",
    ),
    "enterprise.stage": FieldSpec(
        key="enterprise.stage",
        label="阶段",
        source="enterprise",
        attribute="stage",
        openapi_example="成长期",
    ),
    "enterprise.registered_location": FieldSpec(
        key="enterprise.registered_location",
        label="注册地",
        source="enterprise",
        attribute="registered_location",
        openapi_example="苏州工业园区",
    ),
    "enterprise.business_summary": FieldSpec(
        key="enterprise.business_summary",
        label="主营简介",
        source="enterprise",
        attribute="business_summary",
        openapi_example="精密减速器研发与量产",
    ),
    "enterprise.owner_staff_id": FieldSpec(
        key="enterprise.owner_staff_id",
        label="负责人",
        source="enterprise",
        attribute="owner_staff_id",
        openapi_example="2f1d0c44-8a4b-4f2e-9d19-2c6a1b3e4d55",
    ),
    "contact.job_title": FieldSpec(
        key="contact.job_title",
        label="职位",
        source="primary_contact",
        attribute="job_title",
        openapi_example="运营总监",
    ),
    "contact.decision_role": FieldSpec(
        key="contact.decision_role",
        label="决策角色",
        source="primary_contact",
        attribute="decision_role",
        openapi_example="决策者",
    ),
}


def get_field_spec(key: str) -> FieldSpec:
    try:
        return FIELD_CATALOG[key]
    except KeyError:  # pragma: no cover - defensive, validated at caliber load
        raise LookupError(f"unknown field key: {key}") from None


def is_filled(value: object) -> bool:
    """A cell counts as filled only when it holds a non-blank value."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def read_cell(enterprise: Enterprise, contact: Contact | None, spec: FieldSpec) -> object:
    if spec.source == "enterprise":
        return getattr(enterprise, spec.attribute)
    if contact is None:
        return None
    return getattr(contact, spec.attribute)
