"""Read-only mirror of the S2-CRM objects this dashboard aggregates.

The service only ever SELECTs from this schema; writes belong to the CRM
workstream. All rows in the shipped fixtures are fictional.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import AuditMixin, IdentityNameMixin


class Enterprise(Base, AuditMixin, IdentityNameMixin):
    __tablename__ = "crm_enterprises"
    __table_args__ = (
        Index("ix_crm_enterprises_site_owner", "site_id", "owner_staff_id"),
        Index("ix_crm_enterprises_site_active", "site_id", "deleted_at"),
    )

    #: 会员经理 (member manager) responsible for the enterprise.
    owner_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: 行业
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: 赛道
    track: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: 阶段
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: 注册地
    registered_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: 主营简介
    business_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacts: Mapped[list[Contact]] = relationship(back_populates="enterprise")
    capability_cards: Mapped[list[CapabilityCard]] = relationship(back_populates="enterprise")


class Contact(Base, AuditMixin):
    __tablename__ = "crm_contacts"

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_enterprises.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: 职位
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: 决策角色
    decision_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    enterprise: Mapped[Enterprise] = relationship(back_populates="contacts")


class CapabilityCard(Base, AuditMixin):
    __tablename__ = "crm_capability_cards"

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_enterprises.id", ondelete="CASCADE"), nullable=False
    )
    #: Title of the capability card, e.g. 产能规模 / 交付周期.
    card_key: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Null means the card was created but never confirmed by the member manager.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    enterprise: Mapped[Enterprise] = relationship(back_populates="capability_cards")


__all__ = ["CapabilityCard", "Contact", "Enterprise", "uuid"]
