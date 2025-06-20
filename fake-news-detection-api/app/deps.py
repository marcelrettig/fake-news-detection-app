from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin.auth

# HTTPBearer will look for Authorization: Bearer <token>
bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    if not cred or cred.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    id_token = cred.credentials
    try:
        decoded_token = firebase_admin.auth.verify_id_token(id_token)
        return decoded_token
    except firebase_admin.auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ID token",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
