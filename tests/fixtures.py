"""The fictional dataset used by every test and by the demo seed.

Three member enterprises, eight caliber fields, six missing cells. The numbers are
small enough to be checked by hand:

    E1 星澜科技   manager A   missing: enterprise.stage                -> 7/8
    E2 云栖生物   manager A   missing: enterprise.track, contact.job_title
                                                                      -> 6/8
    E3 恒泰智造   manager B   missing: enterprise.track, enterprise.business_summary,
                                        contact.decision_role          -> 5/8
    ------------------------------------------------------------------
    overall  18/24 = 0.75        manager A 13/16 = 0.8125 (2 enterprises)
                                 manager B   5/8 = 0.625  (1 enterprise)

No real person, phone number or enterprise appears in this file: every name is
invented and every identifier is a constant that cannot belong to a real company.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.crm import CapabilityCard, Contact, Enterprise

SITE_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
SITE_EMPTY = uuid.UUID("22222222-2222-4222-8222-222222222222")

ORG_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MANAGER_A = uuid.UUID("33333333-3333-4333-8333-333333333333")
MANAGER_B = uuid.UUID("44444444-4444-4444-8444-444444444444")

E1 = uuid.UUID("e1000000-0000-4000-8000-000000000001")
E2 = uuid.UUID("e2000000-0000-4000-8000-000000000002")
E3 = uuid.UUID("e3000000-0000-4000-8000-000000000003")

FAKE_USCC = "91" + "0" * 15 + "X"
FAKE_PHONE = "10000000000"

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def _enterprise(
    eid: uuid.UUID,
    name: str,
    owner: uuid.UUID,
    *,
    industry: str | None,
    track: str | None,
    stage: str | None,
    location: str | None,
    summary: str | None,
) -> Enterprise:
    return Enterprise(
        id=eid,
        org_id=ORG_ID,
        site_id=SITE_ID,
        name=name,
        owner_staff_id=owner,
        industry=industry,
        track=track,
        stage=stage,
        registered_location=location,
        business_summary=summary,
        uscc=FAKE_USCC,
        contact_phone=FAKE_PHONE,
        created_at=NOW,
        updated_at=NOW,
    )


def _contact(
    eid: uuid.UUID, name: str, enterprise_id: uuid.UUID, job_title: str | None, role: str | None
) -> Contact:
    return Contact(
        id=eid,
        org_id=ORG_ID,
        site_id=SITE_ID,
        enterprise_id=enterprise_id,
        full_name=name,
        job_title=job_title,
        decision_role=role,
        phone=FAKE_PHONE,
        is_primary=True,
        created_at=NOW,
        updated_at=NOW,
    )


def build_enterprises() -> list[Enterprise]:
    return [
        _enterprise(
            E1,
            "星澜科技",
            MANAGER_A,
            industry="高端装备制造",
            track="工业机器人",
            stage=None,
            location="苏州工业园区",
            summary="精密减速器研发与量产",
        ),
        _enterprise(
            E2,
            "云栖生物",
            MANAGER_A,
            industry="生物医药",
            track=None,
            stage="成长期",
            location="杭州滨江",
            summary="体外诊断试剂与仪器",
        ),
        _enterprise(
            E3,
            "恒泰智造",
            MANAGER_B,
            industry="新材料",
            track=None,
            stage="扩张期",
            location="宁波北仑",
            summary=None,
        ),
    ]


def build_contacts() -> list[Contact]:
    return [
        _contact(
            uuid.UUID("c1000000-0000-4000-8000-000000000001"), "联系人甲", E1, "运营总监", "决策者"
        ),
        _contact(uuid.UUID("c2000000-0000-4000-8000-000000000002"), "联系人乙", E2, None, "影响者"),
        _contact(
            uuid.UUID("c3000000-0000-4000-8000-000000000003"), "联系人丙", E3, "技术负责人", None
        ),
    ]


def build_cards() -> list[CapabilityCard]:
    """Three cards, two confirmed, only one confirmed inside the 90-day window."""
    return [
        CapabilityCard(
            id=uuid.UUID("ca000000-0000-4000-8000-000000000001"),
            org_id=ORG_ID,
            site_id=SITE_ID,
            enterprise_id=E1,
            card_key="capacity",
            confirmed_at=NOW - timedelta(days=30),
            created_at=NOW - timedelta(days=40),
            updated_at=NOW - timedelta(days=30),
        ),
        CapabilityCard(
            id=uuid.UUID("ca000000-0000-4000-8000-000000000002"),
            org_id=ORG_ID,
            site_id=SITE_ID,
            enterprise_id=E2,
            card_key="delivery_cycle",
            confirmed_at=NOW - timedelta(days=200),
            created_at=NOW - timedelta(days=220),
            updated_at=NOW - timedelta(days=200),
        ),
        CapabilityCard(
            id=uuid.UUID("ca000000-0000-4000-8000-000000000003"),
            org_id=ORG_ID,
            site_id=SITE_ID,
            enterprise_id=E3,
            card_key="capacity",
            confirmed_at=None,
            created_at=NOW - timedelta(days=10),
            updated_at=NOW - timedelta(days=10),
        ),
    ]


def build_bundle() -> Any:
    from app.repositories.crm_repo import CrmBundle

    contacts = build_contacts()
    return CrmBundle(
        enterprises=build_enterprises(),
        contacts_by_enterprise={contact.enterprise_id: contact for contact in contacts},
        cards=build_cards(),
    )


def hand_table() -> list[dict[str, Any]]:
    """The table the AC1 test prints so a reviewer can check every number."""
    return [
        {"enterprise": "星澜科技", "manager": "A", "filled": 7, "cells": 8, "ratio": 7 / 8},
        {"enterprise": "云栖生物", "manager": "A", "filled": 6, "cells": 8, "ratio": 6 / 8},
        {"enterprise": "恒泰智造", "manager": "B", "filled": 5, "cells": 8, "ratio": 5 / 8},
        {"enterprise": "manager A", "manager": "A", "filled": 13, "cells": 16, "ratio": 13 / 16},
        {"enterprise": "manager B", "manager": "B", "filled": 5, "cells": 8, "ratio": 5 / 8},
        {"enterprise": "overall", "manager": "-", "filled": 18, "cells": 24, "ratio": 18 / 24},
    ]
