from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import event, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria
from sqlalchemy.sql.elements import TextClause

from app.core.tenant import TenantContext, TenantPrincipal
from app.db.models import Shop, TenantOwned
from app.db.session import SessionLocal, engine


class TenantScopeError(RuntimeError):
    """Raised when tenant-owned data is queried without enforced scope."""


class TenantSession(Session):
    pass


TenantSessionLocal = sessionmaker(
    bind=engine,
    class_=TenantSession,
    autoflush=False,
    autocommit=False,
)


@event.listens_for(TenantSession, "do_orm_execute")
def _enforce_tenant_scope(execute_state) -> None:
    shop_id = execute_state.session.info.get("shop_id")
    if not isinstance(shop_id, int):
        raise TenantScopeError("Tenant session has no shop context.")
    if isinstance(execute_state.statement, TextClause):
        raise TenantScopeError(
            "Raw SQL is prohibited in merchant-facing tenant sessions."
        )
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantOwned,
            lambda model: model.shop_id == shop_id,
            include_aliases=True,
        )
    )


def register_or_get_tenant(principal: TenantPrincipal) -> TenantContext:
    statement = (
        insert(Shop)
        .values(
            shop_domain=principal.shop_domain,
            status="active",
            sync_status="pending",
        )
        .on_conflict_do_update(
            constraint="uq_shops_shop_domain",
            set_={
                "status": "active",
                "uninstalled_at": None,
                "updated_at": func.now(),
            },
        )
        .returning(Shop.id, Shop.shop_domain)
    )
    with SessionLocal.begin() as db:
        row = db.execute(statement).one()
    return TenantContext(shop_id=row.id, shop_domain=row.shop_domain)


def get_tenant_context(request: Request) -> TenantContext:
    principal = getattr(request.state, "tenant_principal", None)
    if not isinstance(principal, TenantPrincipal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated tenant context is required.",
        )
    return register_or_get_tenant(principal)


def get_tenant_db(
    tenant: TenantContext = Depends(get_tenant_context),
) -> Generator[TenantSession, None, None]:
    db = TenantSessionLocal(info={"shop_id": tenant.shop_id})
    try:
        yield db
    finally:
        db.close()
