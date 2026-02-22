import hashlib
import secrets

from app.utils.security import b64url


def generate_code_verifier(length: int = 64) -> str:
    # RFC 7636 recommends length between 43 and 128 characters.
    raw = secrets.token_urlsafe(length)
    return raw[:128]


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return b64url(digest)

