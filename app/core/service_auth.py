#erp_service_verification.py
from fastapi import Request, HTTPException, status
from app.core.config import settings
import logging
logger = logging.getLogger(__name__)

def verify_service_jwt(request:Request):

    auth_header=request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid auth header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detial="Missing or invalid Token"
        )
    
    token = auth_header.split(" ")[1]

    if token != settings.SERVICE_JWT:
        logger.error(f"Invalid service token received: {token[:6]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Service Token"
        )