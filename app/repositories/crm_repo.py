"""Read-only CRM adapter.

The real deployment reads the S2-CRM schema; the interface is narrow on purpose so
a stub can replace it while S2-CRM is still being built (see README, integration
points).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.completeness import EnterpriseRow
from app.models.crm import CapabilityCard, Contact, Enterprise


@dataclass(frozen=True, slots=True)
class CrmBundle:
    enterprises: list[Enterprise]
    contacts_by_enterprise: dict[uuid.UUID, Contact]
    cards: list[CapabilityCard]


class CrmReader(Protocol):
    def load(self, site_id: uuid.UUID, staff_id: uuid.UUID | None) -> CrmBundle: ...


class SqlCrmReader:
    """Batched SELECTs: one query for enterprises, one for contacts, one for cards."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self, site_id: uuid.UUID, staff_id: uuid.UUID | None) -> CrmBundle:
        stmt = select(Enterprise).where(
            Enterprise.site_id == site_id, Enterprise.deleted_at.is_(None)
        )
        if staff_id is not None:
            stmt = stmt.where(Enterprise.owner_staff_id == staff_id)
        stmt = stmt.order_by(Enterprise.name)
        enterprises = list(self._session.execute(stmt).scalars().all())

        ids = [row.id for row in enterprises]
        contacts_by_enterprise: dict[uuid.UUID, Contact] = {}
        cards: list[CapabilityCard] = []
        if ids:
            contact_stmt = (
                select(Contact)
                .where(Contact.enterprise_id.in_(ids), Contact.deleted_at.is_(None))
                .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
            )
            for contact in self._session.execute(contact_stmt).scalars().all():
                contacts_by_enterprise.setdefault(contact.enterprise_id, contact)

            card_stmt = select(CapabilityCard).where(
                CapabilityCard.enterprise_id.in_(ids), CapabilityCard.deleted_at.is_(None)
            )
            cards = list(self._session.execute(card_stmt).scalars().all())

        return CrmBundle(
            enterprises=enterprises, contacts_by_enterprise=contacts_by_enterprise, cards=cards
        )


class StubCrmReader:
    """In-memory stub used by tests and by the offline demo mode."""

    def __init__(self, bundles: dict[uuid.UUID, CrmBundle]) -> None:
        self._bundles = bundles

    def load(self, site_id: uuid.UUID, staff_id: uuid.UUID | None) -> CrmBundle:
        bundle = self._bundles.get(
            site_id,
            CrmBundle(enterprises=[], contacts_by_enterprise={}, cards=[]),
        )
        if staff_id is None:
            return bundle
        rows = [row for row in bundle.enterprises if row.owner_staff_id == staff_id]
        cards = [card for card in bundle.cards if card.enterprise_id in {row.id for row in rows}]
        return CrmBundle(
            enterprises=rows,
            contacts_by_enterprise={
                key: value
                for key, value in bundle.contacts_by_enterprise.items()
                if key in {r.id for r in rows}
            },
            cards=cards,
        )


def to_rows(bundle: CrmBundle) -> list[EnterpriseRow]:
    return [
        EnterpriseRow(enterprise=row, contact=bundle.contacts_by_enterprise.get(row.id))
        for row in bundle.enterprises
    ]


__all__ = [
    "CrmBundle",
    "CrmReader",
    "Sequence",
    "SqlCrmReader",
    "StubCrmReader",
    "selectinload",
    "to_rows",
]
