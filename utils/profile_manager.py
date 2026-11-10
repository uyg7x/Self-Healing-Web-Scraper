import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROFILE_ROOT = (Path(__file__).resolve().parent.parent / "data" / "profiles").resolve()
PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
META_FILE = PROFILE_ROOT / "_meta.json"

STALE_HOURS_DEFAULT = 24.0


def _load_meta() -> dict:
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_meta(meta: dict) -> None:
    try:
        META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning(f"Failed to save profile meta: {e}")


def _backfill_from_mtime() -> None:
 
    meta = _load_meta()
    changed = False
    for site_dir in PROFILE_ROOT.iterdir():
        if not site_dir.is_dir() or site_dir.name.startswith("_"):
            continue
        key = site_dir.name
        if key in meta:
            continue
        mtime = datetime.fromtimestamp(site_dir.stat().st_mtime)
        meta[key] = mtime.isoformat()
        changed = True
        logger.info(f"Backfilled {key} with mtime {meta[key]}")
    if changed:
        _save_meta(meta)


try:
    _backfill_from_mtime()
except Exception as e:
    logger.debug(f"Backfill skipped: {e}")


def profile_path(site_key: str) -> Path:
    p = PROFILE_ROOT / site_key
    p.mkdir(parents=True, exist_ok=True)
    return p


def has_profile(site_key: str) -> bool:
    p = PROFILE_ROOT / site_key
    if not p.exists():
        return False
    markers = ("cookies.sqlite", "cert9.db", "prefs.js", "Default")
    return any((p / m).exists() for m in markers)


def clear_profile(site_key: str) -> None:
    p = PROFILE_ROOT / site_key
    if p.exists():
        shutil.rmtree(p)
        logger.info(f"Cleared profile for {site_key}")
    meta = _load_meta()
    if site_key in meta:
        del meta[site_key]
        _save_meta(meta)


def mark_warmed(site_key: str) -> None:
    meta = _load_meta()
    meta[site_key] = datetime.now().isoformat()
    _save_meta(meta)
    logger.info(f"Marked {site_key} as warmed")


def last_warmed(site_key: str) -> datetime | None:
    ts = _load_meta().get(site_key)
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def hours_since_warmed(site_key: str) -> float | None:
    then = last_warmed(site_key)
    if then is None:
        return None
    return (datetime.now() - then).total_seconds() / 3600.0


def is_stale(site_key: str, max_hours: float = STALE_HOURS_DEFAULT) -> bool:
    h = hours_since_warmed(site_key)
    if h is None:
        return True
    return h > max_hours


def age_label(site_key: str) -> str:
    h = hours_since_warmed(site_key)
    if h is None:
        return "never warmed"
    if h < 1:
        return f"{int(h * 60)}m ago"
    if h < 24:
        return f"{h:.1f}h ago"
    return f"{h / 24:.1f}d ago"
