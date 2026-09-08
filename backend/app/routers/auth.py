from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from ..auth import authenticate, create_session_token, read_session_token
from ..config import get_settings
from ..schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def require_user(request: Request) -> str:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = read_session_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


@router.post("/login")
def login(body: LoginRequest, response: Response):
    if not authenticate(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    settings = get_settings()
    token = create_session_token(body.username)
    response = JSONResponse({"ok": True, "user": body.username})
    response.set_cookie(
        key=settings.session_cookie,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age,
        path="/",
    )
    return response


@router.post("/logout")
def logout(response: Response):
    settings = get_settings()
    response = JSONResponse({"ok": True})
    response.delete_cookie(settings.session_cookie, path="/")
    return response


@router.get("/me")
def me(user: str = Depends(require_user)):
    return {"user": user}
