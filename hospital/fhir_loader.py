import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def fhir_root() -> Path:
    return Path(settings.FHIR_DATA_DIR)


def parse_uuid_from_filename(path: Path) -> tuple[str | None, str]:
    stem = path.stem
    head, sep, tail = stem.rpartition('_')
    if sep and UUID_RE.match(tail):
        label = head.replace('_', ' ')
        return tail.lower(), label
    return None, stem


@lru_cache(maxsize=1)
def list_bundle_files() -> tuple[tuple[str, str, str], ...]:
    root = fhir_root()
    if not root.is_dir():
        return ()
    rows: list[tuple[str, str, str]] = []
    for p in sorted(root.glob('*.json')):
        uid, label = parse_uuid_from_filename(p)
        if uid:
            rows.append((uid, label, p.name))
    return tuple(rows)


def resolve_bundle_path(patient_uuid: str) -> Path | None:
    uid = patient_uuid.lower()
    for _, _, fname in list_bundle_files():
        stem = Path(fname).stem
        _, sep, tail = stem.rpartition('_')
        if sep and tail.lower() == uid:
            return fhir_root() / fname
    return None


def load_bundle(patient_uuid: str) -> dict | None:
    path = resolve_bundle_path(patient_uuid)
    if not path or not path.is_file():
        return None
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def get_patient_resource(bundle: dict) -> dict | None:
    for ent in bundle.get('entry') or []:
        res = ent.get('resource') or {}
        if res.get('resourceType') == 'Patient':
            return res
    return None


def resources_by_type(bundle: dict, resource_type: str) -> list[dict]:
    if bundle.get('resourceType') != 'Bundle':
        return []
    out: list[dict] = []
    for ent in bundle.get('entry') or []:
        res = ent.get('resource') or {}
        if res.get('resourceType') == resource_type:
            out.append(res)
    return out


def count_by_resource_type(bundle: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ent in bundle.get('entry') or []:
        res = ent.get('resource') or {}
        rt = res.get('resourceType')
        if isinstance(rt, str):
            counts[rt] = counts.get(rt, 0) + 1
    return counts
