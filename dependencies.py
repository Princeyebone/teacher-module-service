from fastapi import HTTPException, Depends, status, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from config import settings
from typing import Callable, Any
from functools import wraps
from model import UserRole, TeacherProfile
from sqlmodel import Session, select
from database import get_db 
from jose import jwt, JWTError
from logger import logger
from schemas import TokenData




ROLE_HIERARCHY={
    UserRole.SUPERUSER :4,
    UserRole.ADMIN :2,
    UserRole.SCH_TEACHER :1,
}



async def get_current_teacher(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    logger.debug("Validating access token")
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid Activation Token",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    access_token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        email = payload.get("sub")
        if email is None:
            logger.warning("Missing email in token payload")
            raise credentials_exception
            
        role = payload.get("role")
        school_id = payload.get("school_id")
        Individual_id = payload.get("individual_id")
        logger.info(f"Token decoded: {email} (Role: {role}, School: {school_id}, individual ID: {Individual_id})")
        
        token_data = TokenData(email=email, role=role, school_id=school_id, individual_id=Individual_id)
    except JWTError as e:
        logger.error(f"Token validation error: {str(e)}")
        raise credentials_exception
    
    user = db.exec(select(TeacherProfile).where(TeacherProfile.individual_id == token_data.individual_id)).first()
    if user is None:
        logger.warning(f"Token user not found: {token_data.email}")
        raise credentials_exception
    
    logger.info(f"Current user resolved: {token_data.email} (ID: {user.id})")
    return user


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
                    detail={
                        "Error":"Insufficient Permission",
                        "required":min_role.value,
                        "current":current_user.get("role"),
                        "Hierarchy":{role.value: lvl for role, lvl in ROLE_HIERARCHY.items()},
                    }
                )
            return await func(current_user, *args, **kwargs)
        return wrapper
    return decorator

