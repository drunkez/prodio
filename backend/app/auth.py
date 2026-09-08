from datetime import datetime, timedelta
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from .config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="prodio-session")


def create_session_token(username: str) -> str:
    return _serializer().dumps({"u": username})


def read_session_token(token: str, max_age: Optional[int] = None) -> Optional[str]:
    settings = get_settings()
    try:
        data = _serializer().loads(token, max_age=max_age or settings.session_max_age)
        return data.get("u")
    except (BadSignature, SignatureExpired):
        return None


def authenticate(username: str, password: str) -> bool:
    settings = get_settings()
    return username == settings.admin_user and password == settings.admin_password
