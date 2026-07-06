from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .download import file_sha256


def canonical_json_sha256(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_manifest(dataset_id: str, role: str, source: Path, processing_config: dict, **metadata):
    source = Path(source).resolve()
    return {
        "dataset_id": dataset_id,
        "role": role,
        "filename": str(source),
        "byte_size": source.stat().st_size,
        "sha256": file_sha256(source),
        "processing_config_sha256": canonical_json_sha256(processing_config),
        "generated_outputs": [],
        "manifest_created_at_utc": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }


def verify_manifest(manifest: dict) -> bool:
    source = Path(manifest["filename"])
    return source.is_file() and source.stat().st_size == manifest["byte_size"] and file_sha256(source) == manifest["sha256"]


def write_manifest(manifest: dict, output: Path):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
