from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import REFRESH_COOKIE_NAME, decode_token
from app.db.session import get_db
from app.models import User, UserRole, UserStatus

DbSession = Annotated[Session, Depends(get_db)]


def _load_user_from_token(db: Session, token: str, token_type: str) -> User:
    try:
        payload = decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效") from exc

    if payload.get("token_type") != token_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")

    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或令牌缺失")
    token = authorization.removeprefix("Bearer ").strip()
    return _load_user_from_token(db, token, "access")


def get_refresh_user(
    db: DbSession,
    request: Request,
) -> User:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或令牌缺失")
    return _load_user_from_token(db, token, "refresh")


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_owner(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问")
    return current_user


OwnerUser = Annotated[User, Depends(require_owner)]
