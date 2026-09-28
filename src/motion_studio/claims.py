"""Check claim ledgers against immutable local source excerpts, without judging truth.

Ported from motion-engine (MIT) with an `onScreen` field that links claims to on-screen copy.
"""
from __future__ import annotations

import json
import re
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from .util import StudioError as RevisionError, sha256_file as file_sha256


def resolve_local_file(item: dict[str, Any], root: str | Path, kind: str) -> Path:
    root = Path(root).resolve()
    uri = item.get("uri", "")
    relative = Path(uri)
    if not uri or relative.is_absolute() or ".." in relative.parts or ":" in uri or "\\" in uri:
        raise RevisionError(f"{kind} {item['id']}: expected a portable relative file URI")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise RevisionError(f"{kind} {item['id']}: file is missing or outside the ledger directory")
    return path


with resources.files("motion_studio").joinpath("schemas/claims.schema.json").open("r", encoding="utf-8") as stream:
    SCHEMA = json.load(stream)


def _iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("not an ISO date")
    return date.fromisoformat(value)


def verify_claims(ledger_path: str | Path) -> dict[str, Any]:
    path = Path(ledger_path).resolve()
    ledger = json.loads(path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(ledger), key=lambda issue: str(issue.path))
    if errors:
        return {"status": "failed", "issues": [{"code": "schema", "message": error.message} for error in errors]}
    issues: list[dict[str, str]] = []
    sources: dict[str, str] = {}
    seen: set[str] = set()
    for source in ledger["sources"]:
        source_id = source["id"]
        if source_id in seen:
            issues.append({"code": "duplicate_source", "message": f"duplicate source ID {source_id}"})
            continue
        seen.add(source_id)
        if not source["title"].strip() or not source["publisher"].strip():
            issues.append({"code": "missing_metadata", "message": f"source {source_id}: title and publisher must be nonblank"})
        dates = {}
        for field in ("retrievedDate", "publicationDate"):
            value = source[field]
            if value is not None:
                try:
                    dates[field] = _iso_date(value)
                except (TypeError, ValueError):
                    issues.append({"code": "invalid_date", "message": f"source {source_id}: {field} must be YYYY-MM-DD"})
        if dates.get("publicationDate") and dates.get("retrievedDate") and dates["retrievedDate"] < dates["publicationDate"]:
            issues.append({"code": "date_order", "message": f"source {source_id}: retrieval predates publication"})
        url = source["url"]
        if url is not None:
            try:
                parsed = urlsplit(url)
                valid_url = parsed.scheme in ("https", "http") and bool(parsed.hostname) and not parsed.username and not parsed.password
            except ValueError:
                valid_url = False
            if not valid_url:
                issues.append({"code": "invalid_url", "message": f"source {source_id}: URL must be a public HTTP(S) address without credentials"})
        try:
            source_file = resolve_local_file(source, path.parent, "claim source")
            if source_file.stat().st_size > 5_000_000:
                raise ValueError("source snapshot exceeds 5 MB")
            if file_sha256(source_file) != source["sha256"]:
                raise ValueError("SHA-256 mismatch")
            sources[source_id] = source_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError, ValueError, RevisionError) as exc:
            issues.append({"code": "source_invalid", "message": f"source {source_id}: {exc}"})
    claim_ids: set[str] = set()
    for claim in ledger["claims"]:
        claim_id = claim["id"]
        if claim_id in claim_ids:
            issues.append({"code": "duplicate_claim", "message": f"duplicate claim ID {claim_id}"})
        claim_ids.add(claim_id)
        if not claim["text"].strip():
            issues.append({"code": "blank_claim", "message": f"claim {claim_id}: text must be nonblank"})
        try:
            _iso_date(claim["eventDate"])
        except (TypeError, ValueError):
            issues.append({"code": "invalid_date", "message": f"claim {claim_id}: eventDate must be YYYY-MM-DD or null"})
        if not any(item["relation"] == "supports" for item in claim["evidence"]):
            issues.append({"code": "no_support", "message": f"claim {claim_id}: no supporting excerpt is declared"})
        for evidence in claim["evidence"]:
            source_id = evidence["sourceId"]
            content = sources.get(source_id)
            if not evidence["quote"].strip() or not evidence["location"].strip():
                issues.append({"code": "blank_evidence", "message": f"claim {claim_id}: quote and location must be nonblank"})
                continue
            if source_id not in seen:
                issues.append({"code": "unknown_source", "message": f"claim {claim_id}: unknown source {source_id}"})
            elif content is not None and evidence["quote"] not in content:
                issues.append({"code": "quote_mismatch", "message": f"claim {claim_id}: quoted text is absent from source {source_id}"})
    on_screen = [text for claim in ledger["claims"] for text in claim.get("onScreen", [])]
    return {
        "status": "failed" if issues else "source_linked",
        "onScreen": on_screen,
        "ledgerSha256": file_sha256(path),
        "sourceCount": len(ledger["sources"]),
        "claimCount": len(ledger["claims"]),
        "semanticReviewRequired": True,
        "note": "Exact source matching does not establish that a claim is true or that the excerpt supports it.",
        "issues": issues,
    }
