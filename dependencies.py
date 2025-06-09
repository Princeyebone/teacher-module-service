
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from config import settings
from typing import Annotated
import httpx
from typing import Callable, Any
from functools import wraps
from model import UserRole


ROLE_HIERARCHY={
    UserRole.SUPERUSER :4,
    UserRole.ADMIN :2,
    UserRole.TEACHER :1,
}

security = HTTPBearer()

async def get_current_teacher(
        credentials :Annotated[HTTPAuthorizationCredentials, Depends(security)]
):
    token = credentials.credentials
    auth_url = f"{settings.AUTH_SERVICE_URL}/api/me"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            auth_url,
            headers={"Authorization":f"Bearer {token}"}
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authorization":"Bearer"}
        ) 
    
    return response.json()

def requires_role(*required_roles:UserRole):
    def decorator(func:Callable[...,Any]) -> Callable[...,Any]:
        @wraps(func)
        async def wrapper(
            current_user = Depends(get_current_teacher),
            *args:Any,
            **kwargs:Any,
        )-> Any:
            if current_user.get("role") not in required_roles:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                    "Error":"Insufficient Permission",
                    "required":[r.value for r in required_roles],
                    "current":current_user.get("role")
                    }
                )
            return await func(current_user, *args, **kwargs)
        return wrapper
    return decorator

def required_min_role(min_role:UserRole):
    def decorator(func:Callable[..., Any])-> Callable[...,Any]:
        @wraps(func)
        async def wrapper(
            current_user = Depends(get_current_teacher),
            *args:Any,
            **kwargs:Any,
        )->Any:
            if ROLE_HIERARCHY[current_user.get("role")] < ROLE_HIERARCHY[min_role]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    details={
                        "Error":"Insufficient Permission",
                        "required":min_role.value,
                        "current":current_user.get("role"),
                        "Hierarchy":{role.value: lvl for role, lvl in ROLE_HIERARCHY.items()},
                    }
                )
            return await func(current_user, *args, **kwargs)
        return wrapper
    return decorator

