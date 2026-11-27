"""Member-manager directory (read-only mirror of the CRM staff table)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import AuditMixin


class Staff(Base, AuditMixin):
    __tablename__ = "crm_staff"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: 会员经理岗位标记；本接口只统计这个角色的负责人。
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="member_manager")


__all__ = ["Staff"]
