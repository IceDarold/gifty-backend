import hashlib
import json
import uuid
from typing import Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMPayload, LLMPromptTemplate


def _sha256_text(value: str) -> str:
    h = hashlib.sha256()
    h.update(value.encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _sha256_json(value: Any) -> Tuple[str, str]:
    """
    Returns (sha256, canonical_json_string) for stable hashing/dedup.
    Falls back to stringification when JSON serialization fails.
    """
    try:
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        canonical = json.dumps({"_non_json": str(value)}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_text(canonical), canonical


async def get_or_create_prompt_template(
    db: AsyncSession,
    *,
    name: str,
    content: str,
    kind: Optional[str] = None,
) -> int:
    template_hash = _sha256_text(content)

    stmt = (
        pg_insert(LLMPromptTemplate)
        .values(
            name=name,
            kind=kind,
            template_hash=template_hash,
            content=content,
        )
        .on_conflict_do_nothing(constraint="uq_llm_prompt_templates_name_hash")
        .returning(LLMPromptTemplate.id)
    )
    res = await db.execute(stmt)
    new_id = res.scalar_one_or_none()
    if new_id is not None:
        return int(new_id)

    existing = await db.execute(
        select(LLMPromptTemplate.id).where(LLMPromptTemplate.name == name, LLMPromptTemplate.template_hash == template_hash)
    )
    return int(existing.scalar_one())


async def get_or_create_payload(
    db: AsyncSession,
    *,
    kind: str,
    content_text: Optional[str] = None,
    content_json: Any = None,
) -> uuid.UUID:
    if (content_text is None) == (content_json is None):
        raise ValueError("Exactly one of content_text or content_json must be provided")

    if content_text is not None:
        sha = _sha256_text(content_text)
        values = {
            "id": uuid.uuid4(),
            "kind": kind,
            "sha256": sha,
            "content_text": content_text,
            "content_json": None,
        }
    else:
        sha, _canonical = _sha256_json(content_json)
        values = {
            "id": uuid.uuid4(),
            "kind": kind,
            "sha256": sha,
            "content_text": None,
            "content_json": content_json,
        }

    stmt = (
        pg_insert(LLMPayload)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_llm_payloads_sha256")
        .returning(LLMPayload.id)
    )
    res = await db.execute(stmt)
    new_id = res.scalar_one_or_none()
    if new_id is not None:
        return new_id

    existing = await db.execute(select(LLMPayload.id).where(LLMPayload.sha256 == sha))
    return existing.scalar_one()

