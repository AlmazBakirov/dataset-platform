from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        username = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user


def require_roles(allowed: list[str]):
    def _inner(user: User = Depends(get_current_user)) -> User:
        if user.role in allowed or user.role in ["admin", "universal"]:
            return user
        raise HTTPException(status_code=403, detail="No access for your role")

    return _inner
