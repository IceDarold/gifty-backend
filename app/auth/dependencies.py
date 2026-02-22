from fastapi import Header, HTTPException, Depends
from app.config import get_settings, Settings

async def verify_internal_token(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
    settings: Settings = Depends(get_settings)
):
    """
    Verify the internal API token for worker and administrative routes.
    """
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=403, detail="Invalid internal API token")
    return x_internal_token
