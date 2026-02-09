import hashlib
import hmac
from urllib.parse import parse_qsl

def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Verifies the integrity of the data received from the Telegram Mini App.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        vals = dict(parse_qsl(init_data))
        if "hash" not in vals:
            return False
            
        auth_hash = vals.pop("hash")
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(vals.items())
        )
        
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        
        return calculated_hash == auth_hash
    except Exception:
        return False
