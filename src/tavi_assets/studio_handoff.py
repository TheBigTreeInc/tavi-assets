"""Unprivileged Asset Studio submission envelopes; never authorizes ingestion or publication."""
import hashlib
import json
import re
from pathlib import Path

PACK = re.compile(r"^[a-z0-9][a-z0-9._-]{0,126}$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
SCHEMA = "tavi.assets.studio-submission/v1"
MAX_PACK_BYTES = 64 * 1024 * 1024

def make_submission(pack_path, pack_id, version, destination="staging"):
    """Create a content-bound request for a trusted host, without uploading."""
    path = Path(pack_path)
    if not path.is_file() or path.suffix.lower() != ".tavia":
        raise ValueError("a local .tavia file is required")
    if not PACK.fullmatch(pack_id) or not VERSION.fullmatch(version):
        raise ValueError("invalid pack ID or version")
    if destination != "staging":
        raise ValueError("Studio may request staging only; publish is a separate admin action")
    size = path.stat().st_size
    if not 0 < size <= MAX_PACK_BYTES:
        raise ValueError("invalid pack size")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema": SCHEMA, "operation": "request_stage",
            "packId": pack_id, "version": version,
            "archiveSha256": digest, "archiveBytes": size,
            "destination": "staging", "requiresHostApproval": True,
            "requiresServerAuthorization": True}

def validate_submission(data):
    if not isinstance(data, dict) or set(data) != {
        "schema", "operation", "packId", "version", "archiveSha256",
        "archiveBytes", "destination", "requiresHostApproval", "requiresServerAuthorization"
    }:
        raise ValueError("invalid Studio submission fields")
    if (data["schema"] != SCHEMA or data["operation"] != "request_stage" or
        data["destination"] != "staging" or data["requiresHostApproval"] is not True or
        data["requiresServerAuthorization"] is not True or
        not isinstance(data["packId"], str) or not PACK.fullmatch(data["packId"]) or
        not isinstance(data["version"], str) or not VERSION.fullmatch(data["version"]) or
        not isinstance(data["archiveSha256"], str) or not DIGEST.fullmatch(data["archiveSha256"]) or
        type(data["archiveBytes"]) is not int or not 0 < data["archiveBytes"] <= MAX_PACK_BYTES):
        raise ValueError("invalid Studio submission")
    return data
