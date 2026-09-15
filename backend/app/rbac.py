from fastapi import Header, HTTPException

from backend.app.config import get_settings
from backend.app.schemas import Principal, Role

PERMISSIONS: dict[str, set[str]] = {
    "owner": {"roi", "kill_global", "promote", "rollback", "export", "read"},
    "admin": {
        "roi",
        "kill_global",
        "activate",
        "guard_edit",
        "approve",
        "promote",
        "rollback",
        "export",
        "read",
        "trigger",
    },
    "tech": {"kill_scoped", "approve", "read"},
    "auditor": {"export", "read"},
}

DEMO_USERS = {
    "sofia": Principal(user_id="sofia", role="owner", tenant_id="northwind"),
    "arjun": Principal(user_id="arjun", role="admin", tenant_id="northwind"),
    "mia": Principal(user_id="mia", role="tech", tenant_id="northwind"),
    "david": Principal(user_id="david", role="auditor", tenant_id="northwind"),
}


def can(role: Role, perm: str) -> bool:
    return perm in PERMISSIONS.get(role, set())


def require(principal: Principal, perm: str) -> None:
    if not can(principal.role, perm):
        raise HTTPException(status_code=403, detail=f"Role {principal.role} cannot {perm}")


async def get_principal(
    x_api_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_role: Role | None = Header(default=None, alias="X-Role"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> Principal:
    """Demo identity. Replace with OIDC/SSO before production.

    Send `X-API-Key` plus optional `X-User-Id` / `X-Role` / `X-Tenant-Id`.
    Known demo users: sofia (owner), arjun (admin), mia (tech), david (auditor).
    """
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    if x_user_id and x_user_id in DEMO_USERS and not x_role:
        p = DEMO_USERS[x_user_id]
        if x_tenant_id:
            return p.model_copy(update={"tenant_id": x_tenant_id})
        return p
    return Principal(
        user_id=x_user_id or "arjun",
        role=x_role or "admin",
        tenant_id=x_tenant_id or "northwind",
    )
