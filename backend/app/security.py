import hashlib
import hmac
import secrets
from sqlalchemy.orm import Session

from .models import SessionToken, User

_ITERATIONS = 210_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), _ITERATIONS).hex()
    return f'{salt}${digest}'


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split('$', 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), _ITERATIONS).hex()
    return hmac.compare_digest(candidate, digest)


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(SessionToken(token=token, user_id=user.id))
    db.commit()
    return token


def get_user_by_token(db: Session, token: str) -> User | None:
    session = db.query(SessionToken).filter(SessionToken.token == token).first()
    return session.user if session else None
