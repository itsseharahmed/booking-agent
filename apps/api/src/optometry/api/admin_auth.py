# administrator login endpoint.

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from optometry.auth.admin_service import authenticate_admin
from optometry.core.config import get_jwt_secret_key
from optometry.core.security import create_admin_access_token
from optometry.db.session import get_db
from optometry.schemas.admin import AdminLogin
from optometry.schemas.auth import TokenRead

# router for this api module.
router = APIRouter(prefix="/admin/auth", tags=["admin-authentication"])

# database session dependency used by this module.
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=TokenRead)
# logs the user in and returns a token.
def login(
    payload: AdminLogin,
    db: DbSession,
) -> TokenRead:
    # validate the supplied admin credentials against the configured auth service.
    admin = authenticate_admin(db, payload)

    # issue a JWT containing the authenticated admin ID for downstream authorization checks.
    token = create_admin_access_token(
        admin_id=admin.id,
        secret_key=get_jwt_secret_key(),
    )

    return TokenRead(access_token=token)
