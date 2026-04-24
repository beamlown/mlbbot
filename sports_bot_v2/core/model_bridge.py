from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger("core.model_bridge")

ENABLE_MODEL_BRIDGE = os.getenv("ENABLE_MODEL_BRIDGE", "false").strip().lower() in ("1", "true", "yes", "on")
APPROVED_MODEL_VERSIONS = {"mlb_winprob_v1_lgbm"}
MAX_REC_AGE_SECONDS = 120
MIN_EDGE = 0.05
MIN_CONFIDENCE = 0.25
MAX_GAME_STATE_AGE = 60
MAX_BOOK_AGE = 30
SOURCE_LABEL = "model_bridge"
SHADOW_LOG_PATH = Path(__file__).resolve().parents[2] / "mlb_model" / "logs" / "shadow_recommendations.jsonl"
REJECT_MARKET_KEYWORDS = ("nrfi", "spread", "total", "o/u", "prop")
MAX_LINES = 5000

# mtime-triggered cache — reparse only when shadow log changes. Cuts a ~5000-line
# read+split+json-parse sweep from every loop down to once-per-actual-update.
_CACHE: dict[str, object] = {"mtime": 0.0, "latest_by_slug": {}}


def _read_latest_by_slug() -> dict[str, dict]:
    try:
        stat = SHADOW_LOG_PATH.stat()
    except FileNotFoundError:
        _CACHE["mtime"] = 0.0
        _CACHE["latest_by_slug"] = {}
        return {}
    mtime = stat.st_mtime
    if mtime == _CACHE["mtime"]:
        return _CACHE["latest_by_slug"]  # type: ignore[return-value]
    try:
        lines = SHADOW_LOG_PATH.read_text(encoding="utf-8").splitlines()[-MAX_LINES:]
    except Exception as exc:
        logger.info("BRIDGE GATE REJECT [log_read] slug=- reason=%s", exc)
        return _CACHE["latest_by_slug"]  # type: ignore[return-value]
    latest_by_slug: dict[str, dict] = {}
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        action = obj.get("action")
        if action == "NO_TRADE":
            continue
        slug = str(obj.get("market_slug") or "").strip()
        if not slug:
            continue
        prev = latest_by_slug.get(slug)
        if prev is None or _pick_latest_timestamp(obj) >= _pick_latest_timestamp(prev):
            latest_by_slug[slug] = obj
    _CACHE["mtime"] = mtime
    _CACHE["latest_by_slug"] = latest_by_slug
    logger.info("BRIDGE shadow-log reparsed mtime=%.3f rows=%d slugs=%d", mtime, len(lines), len(latest_by_slug))
    return latest_by_slug


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _pick_latest_timestamp(rec: dict) -> datetime:
    return _parse_ts(rec.get("feature_timestamp")) or _parse_ts(rec.get("ts")) or datetime.fromtimestamp(0, tz=timezone.utc)


def _extract_slug_date(slug: str) -> date | None:
    parts = str(slug).split("-")
    if len(parts) < 3:
        return None
    try:
        return date.fromisoformat("-".join(parts[-3:]))
    except ValueError:
        return None


def _reject(gate: str, slug: str, reason: str) -> None:
    logger.info("BRIDGE GATE REJECT [%s] slug=%s reason=%s", gate, slug, reason)


def _pass(slug: str, side: str, edge: float, confidence: float) -> None:
    logger.info("BRIDGE GATE PASS slug=%s side=%s edge=%.4f confidence=%.4f", slug, side, edge, confidence)


def get_approved_intents(open_slugs: set[str]) -> list[dict]:
    if not ENABLE_MODEL_BRIDGE:
        logger.info("BRIDGE DISABLED — set ENABLE_MODEL_BRIDGE=True to activate")
        return []

    if not SHADOW_LOG_PATH.exists():
        logger.info("BRIDGE GATE REJECT [missing_log] slug=- reason=shadow_log_missing")
        return []

    latest_by_slug = _read_latest_by_slug()

    if not latest_by_slug:
        logger.info(
            "BRIDGE ALL STALE — no actionable recommendations found; shadow engine may not be running or all recs are stale"
        )
        return []

    intents: list[dict] = []
    approved_slugs: set[str] = set()
    now = datetime.now(timezone.utc)
    today = date.today()

    for slug, rec in sorted(latest_by_slug.items(), key=lambda kv: _pick_latest_timestamp(kv[1]), reverse=True):
        model_version = rec.get("model_version")
        if model_version not in APPROVED_MODEL_VERSIONS:
            _reject("model_version", slug, f"unapproved:{model_version}")
            continue

        action = rec.get("action")
        if action not in {"BUY_YES", "BUY_NO"}:
            _reject("action", slug, f"invalid:{action}")
            continue

        feature_ts = _pick_latest_timestamp(rec)
        rec_age = (now - feature_ts).total_seconds()
        if rec_age >= MAX_REC_AGE_SECONDS:
            _reject("rec_age", slug, f"age={rec_age:.1f}s")
            continue

        slug_l = slug.lower()
        if any(keyword in slug_l for keyword in REJECT_MARKET_KEYWORDS):
            _reject("market_type", slug, "non_moneyline")
            continue

        slug_date = _extract_slug_date(slug)
        if slug_date != today:
            _reject("slug_date", slug, f"date={slug_date} today={today}")
            continue

        edge = rec.get("edge_yes") if action == "BUY_YES" else rec.get("edge_no")
        try:
            edge = float(edge)
        except (TypeError, ValueError):
            _reject("edge", slug, f"missing:{edge}")
            continue
        if edge < MIN_EDGE:
            _reject("edge", slug, f"edge={edge:.4f}")
            continue

        try:
            confidence = float(rec.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < MIN_CONFIDENCE:
            _reject("confidence", slug, f"confidence={confidence:.4f}")
            continue

        try:
            game_state_age = float(rec.get("game_state_age_sec"))
        except (TypeError, ValueError):
            game_state_age = float("inf")
        if game_state_age >= MAX_GAME_STATE_AGE:
            _reject("game_state_age", slug, f"game_state_age={game_state_age}")
            continue

        try:
            book_age = float(rec.get("book_age_sec"))
        except (TypeError, ValueError):
            book_age = float("inf")
        if book_age >= MAX_BOOK_AGE:
            _reject("book_age", slug, f"book_age={book_age}")
            continue

        if slug in open_slugs:
            _reject("open_position", slug, "slug_already_open")
            continue

        if slug in approved_slugs:
            _reject("duplicate_batch", slug, "duplicate_slug_same_loop")
            continue

        entry_px = rec.get("market_yes_cost") if action == "BUY_YES" else rec.get("market_no_cost")
        try:
            entry_px = float(entry_px)
        except (TypeError, ValueError):
            _reject("entry_price", slug, f"invalid:{entry_px}")
            continue

        approved_slugs.add(slug)
        _pass(slug, action, edge, confidence)
        intents.append({
            "slug": slug,
            "market_slug": slug,
            "market_id": str(rec.get("market_id") or ""),
            "yes_token_id": str(rec.get("yes_token_id") or ""),
            "no_token_id": str(rec.get("no_token_id") or ""),
            "side": action,
            "action": action,
            "held_outcome_label": str(rec.get("tracked_team") or ("YES" if action == "BUY_YES" else "NO")),
            "home_team": rec.get("home_team"),
            "away_team": rec.get("away_team"),
            "tracked_team": rec.get("tracked_team"),
            "is_home_team": rec.get("is_home_team"),
            "fair_win_prob": rec.get("fair_win_prob"),
            "p_home": rec.get("p_home"),
            "pregame_win_prob": rec.get("pregame_win_prob"),
            "market_yes_cost": rec.get("market_yes_cost"),
            "market_no_cost": rec.get("market_no_cost"),
            "ask_yes": rec.get("ask_yes"),
            "ask_no": rec.get("ask_no"),
            "spread": rec.get("spread"),
            "thin_side_depth_usd": rec.get("thin_side_depth_usd"),
            "entry_px": entry_px,
            "edge": edge,
            "edge_yes": rec.get("edge_yes"),
            "edge_no": rec.get("edge_no"),
            "confidence": confidence,
            "size_tier": rec.get("size_tier"),
            "size_mult": rec.get("size_mult"),
            "recommended_size_dollars": rec.get("recommended_size_dollars"),
            "recommended_size_units": rec.get("recommended_size_units"),
            "tp_price": rec.get("tp_price"),
            "sl_price": rec.get("sl_price"),
            "reasons": rec.get("reasons") if isinstance(rec.get("reasons"), list) else [],
            "model_version": rec.get("model_version"),
            "data_quality": rec.get("data_quality"),
            "inning": rec.get("inning"),
            "inning_half": rec.get("inning_half"),
            "outs": rec.get("outs"),
            "score_diff": rec.get("score_diff"),
            "game_progress": rec.get("game_progress"),
            "game_status": rec.get("game_status"),
            "feature_timestamp": rec.get("feature_timestamp"),
            "game_state_timestamp": rec.get("game_state_timestamp"),
            "book_timestamp": rec.get("book_timestamp"),
            "game_state_age_sec": rec.get("game_state_age_sec"),
            "book_age_sec": rec.get("book_age_sec"),
            "source": SOURCE_LABEL,
        })

    return intents
