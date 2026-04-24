"""
integration/recommendation_api.py — MLB model recommendation engine

This is the main loop / service layer of the new calibrated model system.
It orchestrates:
  1. Live game discovery (from ESPN)
  2. Game state fetching
  3. Pregame prior lookup (Elo or sharp odds)
  4. Win probability inference
  5. Market state fetch (order books)
  6. Edge computation
  7. Execution gate check
  8. Recommendation output
  9. Shadow mode logging

Can run in two modes:
  - Standalone loop: `python -m integration.recommendation_api`
  - As a callable module: `from integration.recommendation_api import get_recommendations`

Phase control (via PHASE env var):
  shadow   — generate and log recommendations, no execution
  advisory — recommendations sent to dashboard; manual approval required
  merged   — recommendations consumed by sports_bot_v2 execution layer

The existing sports_bot_v2 should call get_recommendations() and apply its
own execution gates (cooldown, risk budget, position limits) before trading.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

PHASE = os.getenv("PHASE", "shadow")
LOOP_SECONDS = int(os.getenv("RECOMMENDATION_LOOP_SECONDS", "15"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _age_to_ts(age_seconds: float) -> str:
    """Convert an age-in-seconds to the ISO8601 timestamp when that fetch occurred."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat() + "Z"


def _get_pregame_prob_for_game(home_team: str, away_team: str, date: str) -> float:
    """
    Return P(home wins) pregame prior.
    Priority: 1) Elo table  2) Sharp Pinnacle odds  3) default 0.54
    """
    # Try Elo table first (always available after training)
    try:
        from data.pregame_prior_builder import load_elo_table, get_pregame_prob
        from sports.mlb.team_normalizer import normalize
        elo = load_elo_table()
        prob = get_pregame_prob(normalize(home_team), normalize(away_team), date, elo)
        if prob != 0.54:   # 0.54 = default → elo not found, try sharp
            return prob
    except Exception:
        pass

    # Try sharp Pinnacle odds (if API key configured)
    try:
        odds_key = os.getenv("ODDS_API_KEY", "")
        if odds_key:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                            "sports_bot_v2"))
            from sports.mlb.sharp_odds import get_sharp_prob
            prob = get_sharp_prob(home_team, away_team)
            if prob is not None:
                return prob
    except Exception:
        pass

    return 0.54


def _suppress_confidence_for_extreme_prices(confidence: float, ask_yes: float, ask_no: float) -> float:
    """
    Suppress confidence when market prices are near 0 or 1.
    Extreme prices indicate high market certainty; our model edge becomes less meaningful.
    """
    EXTREME_THRESHOLD = 0.05  # prices < 5% or > 95%
    SUPPRESSION_FACTOR = 0.7  # reduce confidence by 30% when either side is extreme

    if ask_yes is not None and (ask_yes < EXTREME_THRESHOLD or ask_yes > 1.0 - EXTREME_THRESHOLD):
        confidence *= SUPPRESSION_FACTOR
    if ask_no is not None and (ask_no < EXTREME_THRESHOLD or ask_no > 1.0 - EXTREME_THRESHOLD):
        confidence *= SUPPRESSION_FACTOR

    return max(0.0, min(1.0, confidence))


def generate_recommendation_for_game(
    home_team: str,
    away_team: str,
    market_id: str,
    yes_token_id: str,
    no_token_id: str,
    market_slug: str,
    tracked_team: str,       # which team the YES contract pays on
) -> "Recommendation":
    """
    Generate a single recommendation for a specific game/market.
    Returns a Recommendation (action may be NO_TRADE).
    """
    from integration.recommendation_schema import Recommendation
    from sports.mlb.game_state_service import get_game_snapshot
    from sports.mlb.live_game_registry import get_game_by_teams
    from sports.mlb.winprob_inference import infer_for_team, is_loaded
    from sports.mlb.market_state_stream import get_market_state, compute_edge
    from sports.mlb.team_normalizer import normalize

    ts = _now_iso()

    def _no_trade(reason: str) -> Recommendation:
        return Recommendation.no_trade(
            market_id=market_id,
            reason=reason,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            market_slug=market_slug,
            home_team=normalize(home_team),
            away_team=normalize(away_team),
            tracked_team=normalize(tracked_team),
            feature_timestamp=ts,
        )

    # Check model loaded
    if not is_loaded():
        return _no_trade("model_not_loaded")

    # Fetch live game state
    snap = get_game_snapshot(home_team, away_team)
    if snap is None:
        return _no_trade("game_state_unavailable")

    if not snap.is_live:
        return _no_trade(f"game_not_live:{snap.status}")

    # Verify game is live from the registry (independent confirmation)
    reg_game = get_game_by_teams(home_team, away_team)
    game_is_live_confirmed = reg_game is not None and reg_game.is_live
    if not game_is_live_confirmed:
        return _no_trade("registry_not_live")

    # Pregame prior
    pregame_prob = _get_pregame_prob_for_game(home_team, away_team, snap.date)

    # Model inference
    try:
        p_tracked, infer_result = infer_for_team(snap, tracked_team, pregame_prob)
    except Exception as e:
        logger.warning("Inference failed for %s vs %s: %s", home_team, away_team, e)
        return _no_trade(f"inference_error:{e}")

    p_home = infer_result.p_home

    # Market state
    market = get_market_state(yes_token_id, no_token_id)
    if market is None:
        return _no_trade("market_state_unavailable")

    # Edge calculation
    edges = compute_edge(p_tracked, market)
    edge_yes = edges["edge_yes"]
    edge_no = edges["edge_no"]

    # Determine action candidate
    if edge_yes > edge_no and edge_yes >= float(os.getenv("MIN_EDGE_THRESHOLD", "0.05")):
        action_candidate = "BUY_YES"
        edge_candidate = edge_yes
    elif edge_no > edge_yes and edge_no >= float(os.getenv("MIN_EDGE_THRESHOLD", "0.05")):
        action_candidate = "BUY_NO"
        edge_candidate = edge_no
    else:
        action_candidate = "NO_TRADE"
        edge_candidate = max(edge_yes, edge_no)

    # Near-resolution suppressor: cap confidence at 0.0 and suppress trades
    # when entry-side market price is near-zero (< 0.10)
    near_resolution_suppressed = False
    near_res_threshold = float(os.getenv("NEAR_RESOLUTION_PRICE_THRESHOLD", "0.10"))
    if action_candidate == "BUY_YES":
        if edges["p_cost_yes"] < near_res_threshold:
            action_candidate = "NO_TRADE"
            near_resolution_suppressed = True
    elif action_candidate == "BUY_NO":
        if edges["p_cost_no"] < near_res_threshold:
            action_candidate = "NO_TRADE"
            near_resolution_suppressed = True

    if action_candidate == "NO_TRADE":
        # Still build a full recommendation for shadow logging
        size_tier = "none"
        size_mult = 0.0
        if near_resolution_suppressed:
            # Include which side and price triggered the suppression
            if edges["p_cost_yes"] < near_res_threshold:
                gate_reasons = [f"near_resolution_suppressor:yes_price={edges['p_cost_yes']:.4f}<{near_res_threshold}"]
            elif edges["p_cost_no"] < near_res_threshold:
                gate_reasons = [f"near_resolution_suppressor:no_price={edges['p_cost_no']:.4f}<{near_res_threshold}"]
            else:
                gate_reasons = ["near_resolution_suppressor"]
        else:
            gate_reasons = [f"edge_too_small:yes={edge_yes:.4f},no={edge_no:.4f}"]
    else:
        gate_reasons = []
        strong_edge = float(os.getenv("STRONG_EDGE_THRESHOLD", "0.08"))
        min_edge = float(os.getenv("MIN_EDGE_THRESHOLD", "0.05"))
        if edge_candidate >= strong_edge:
            size_tier = "strong"
            size_mult = 1.5
        elif edge_candidate >= min_edge:
            size_tier = "normal"
            size_mult = 1.0
        else:
            size_tier = "none"
            size_mult = 0.0

    # Build reasons list
    reasons = []
    if snap.score_diff != 0:
        leader = snap.home_team if snap.score_diff > 0 else snap.away_team
        reasons.append(f"{leader} leads by {abs(snap.score_diff)}")
    reasons.append(f"inning {snap.inning} {'bot' if snap.inning_half else 'top'}, {snap.outs} outs")
    if snap.home_is_bullpen or snap.away_is_bullpen:
        reasons.append("bullpen in game")
    reasons.append(f"pregame_prior={pregame_prob:.3f}")
    if gate_reasons:
        reasons.extend(gate_reasons[:3])

    if action_candidate == "NO_TRADE" and near_resolution_suppressed:
        confidence = 0.0
    else:
        max_spread = float(os.getenv("MAX_SPREAD", "0.035"))
        spread_quality = 1.0 - (market.spread or 0.0) / max_spread if market.spread is not None else 0.8
        spread_quality = max(0.0, min(1.0, spread_quality))
        min_edge = float(os.getenv("MIN_EDGE_THRESHOLD", "0.05"))
        edge_score = min(1.0, max(0.0, (edge_candidate - min_edge) / 0.10 + 0.5))
        confidence = edge_score * infer_result.data_quality * spread_quality
        confidence = _suppress_confidence_for_extreme_prices(confidence, market.ask_yes, market.ask_no)
        confidence = round(confidence, 4)

    is_home = normalize(tracked_team) == normalize(home_team)

    return Recommendation(
        market_id=market_id,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        market_slug=market_slug,
        home_team=normalize(home_team),
        away_team=normalize(away_team),
        tracked_team=normalize(tracked_team),
        is_home_team=is_home,
        fair_win_prob=p_tracked,
        p_home=p_home,
        pregame_win_prob=pregame_prob,
        market_yes_cost=edges["p_cost_yes"],
        market_no_cost=edges["p_cost_no"],
        ask_yes=market.ask_yes,
        ask_no=market.ask_no,
        spread=market.spread,
        thin_side_depth_usd=market.thin_side_depth,
        edge_yes=edge_yes,
        edge_no=edge_no,
        action=action_candidate,
        size_tier=size_tier,
        size_mult=size_mult,
        model_version=infer_result.model_version,
        data_quality=infer_result.data_quality,
        confidence=confidence,
        reasons=reasons,
        inning=snap.inning,
        inning_half=snap.inning_half,
        outs=snap.outs,
        score_diff=snap.score_diff,
        game_progress=snap.game_progress,
        game_status=snap.status,
        feature_timestamp=ts,
        game_state_timestamp=_age_to_ts(snap.age_seconds),
        book_timestamp=_age_to_ts(market.age_seconds),
        game_state_age_sec=round(snap.age_seconds, 2),
        book_age_sec=round(market.age_seconds, 2),
    )


def get_recommendations(
    candidate_markets: list[dict],
) -> list["Recommendation"]:
    """
    Generate recommendations for a list of candidate markets.

    Each item in candidate_markets must have:
      market_id, yes_token_id, no_token_id, market_slug,
      home_team, away_team, tracked_team (team the YES pays on)

    This is the main API called by sports_bot_v2 in Phase 3.
    In Phase 1/2 (shadow/advisory), it's called by the standalone loop below.
    """
    recs = []
    for market in candidate_markets:
        try:
            rec = generate_recommendation_for_game(
                home_team=market["home_team"],
                away_team=market["away_team"],
                market_id=market["market_id"],
                yes_token_id=market["yes_token_id"],
                no_token_id=market["no_token_id"],
                market_slug=market["market_slug"],
                tracked_team=market["tracked_team"],
            )
            recs.append(rec)
        except Exception as e:
            logger.warning("Failed to generate rec for market %s: %s",
                           market.get("market_id", "?"), e)
    return recs


# ── Standalone shadow mode loop ────────────────────────────────────────────────

def _discover_mlb_markets() -> list[dict]:
    """
    Discover active MLB moneyline markets on Polymarket via the /events endpoint.

    Uses the same endpoint and filtering logic as sports_bot_v2/core/discovery.py:
      - GET /events?tag_slug=mlb&closed=false&limit=500
      - Filter events by slug pattern: mlb-[away]-[home]-YYYY-MM-DD
      - Date window: today ± a few days (rejects 2020 World Series, etc.)
      - Skip closed/resolved markets
      - Moneyline keyword filter
      - Team parse + live registry check

    The /markets endpoint with ?tag_slug= does not reliably filter to MLB
    and returns historical markets from other sports.
    """
    import json as _json
    import re as _re
    import urllib.request
    from datetime import date, timedelta

    from sports.mlb.team_normalizer import parse_question_teams
    from sports.mlb.live_game_registry import get_game_by_teams, get_all_games

    _TEAM_ALIAS_TO_REGISTRY = {
        "CWS": "CHW",
        "OAK": "ATH",
    }

    def _registry_alias(team: str) -> str:
        return _TEAM_ALIAS_TO_REGISTRY.get(str(team).upper(), str(team).upper())

    GAMMA_BASE = os.getenv("GAMMA_API_URL", "https://gamma-api.polymarket.com")

    # Matches Polymarket per-game event slugs: mlb-hou-bos-2026-04-03
    GAME_SLUG_RE = _re.compile(r'^mlb-[a-z0-9]+-[a-z0-9]+-(\d{4}-\d{2}-\d{2})$')
    DATE_WINDOW_PAST = int(os.getenv("DISCOVERY_DATE_WINDOW_PAST", "1"))
    DATE_WINDOW_FUTURE = int(os.getenv("DISCOVERY_DATE_WINDOW_FUTURE", "2"))

    try:
        url = f"{GAMMA_BASE}/events?tag_slug=mlb&closed=false&limit=500"
        req = urllib.request.Request(url, headers={"User-Agent": "mlb_model/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())

        events = data if isinstance(data, list) else data.get("events", [])

        # Log a preview of raw events for discovery debugging
        logger.info("Gamma /events returned %d total events", len(events))
        for i, ev in enumerate(events[:10]):
            logger.info(
                "  raw[%02d] slug=%-48s title=%.45s",
                i, ev.get("slug", "")[:48], (ev.get("title") or ev.get("name") or "")[:45],
            )

        today = date.today()
        markets = []
        skipped_non_mlb = 0
        skipped_closed = 0
        skipped_keyword = 0
        skipped_parse = 0
        skipped_not_live = 0
        skipped_dup_event = 0
        unparseable_examples: list[str] = []

        for event in events:
            event_slug = str(event.get("slug") or "")

            # Must match per-game slug: mlb-away-home-date
            m = GAME_SLUG_RE.match(event_slug)
            if not m:
                skipped_non_mlb += 1
                logger.debug("Skip non-game event: slug=%r", event_slug)
                continue

            # Date window: reject old/future events
            try:
                game_date = date.fromisoformat(m.group(1))
                if game_date < today - timedelta(days=DATE_WINDOW_PAST):
                    skipped_non_mlb += 1
                    logger.debug("Skip old event: slug=%r date=%s", event_slug, game_date)
                    continue
                if game_date > today + timedelta(days=DATE_WINDOW_FUTURE):
                    skipped_non_mlb += 1
                    logger.debug("Skip future event: slug=%r date=%s", event_slug, game_date)
                    continue
            except ValueError:
                pass

            # ── Diagnostics: log every same-day event that passes slug+date ────────
            _is_today = (game_date == today)
            _target_slugs = {"mlb-stl-det-2026-04-04", "mlb-mil-kcr-2026-04-04",
                             "mlb-tor-chw-2026-04-04"}
            _diag = _is_today or event_slug in _target_slugs
            _raw_mkts = event.get("markets") or []
            logger.info(
                "DIAG event=%r  date=%s  today=%s  markets_in_event=%d",
                event_slug, game_date, today, len(_raw_mkts),
            )

            # Collect moneyline candidates for this event, then pick exactly one.
            # Polymarket nests many market types inside one event (spread, total,
            # alt lines, series, props). We must restrict to the canonical moneyline
            # before running inference. The two-phase approach below:
            #   Phase A — per-market filtering with non-moneyline exclusion (P2)
            #   Phase B — pick one canonical market per event (P3)
            event_candidates: list[dict] = []

            # Keywords that unambiguously mark non-moneyline variants.
            # Checked against (question + slug + groupItemTitle) combined.
            _NON_ML_KW = (
                "spread", "run line", "runline", "run-line",
                "total", "over/under", " o/u", "alt line", "alt-line",
                "alternate", "first 5", "first five", " f5",
                "series", "prop", "nrfi", "yrfi", "exact score", "margin",
            )

            for mkt_raw in _raw_mkts:
                if mkt_raw.get("closed") or mkt_raw.get("resolved"):
                    skipped_closed += 1
                    if _diag:
                        logger.info(
                            "  DIAG [closed/resolved] event=%r  mkt_slug=%r",
                            event_slug, mkt_raw.get("slug", ""),
                        )
                    continue

                question = str(mkt_raw.get("question") or mkt_raw.get("title") or "")
                mkt_slug = str(mkt_raw.get("slug") or "")
                # groupItemTitle / marketType / outcomeType are optional fields
                # Polymarket uses to label market sub-types within an event.
                mkt_type = str(
                    mkt_raw.get("groupItemTitle") or
                    mkt_raw.get("marketType") or
                    mkt_raw.get("outcomeType") or ""
                )

                # P1: log every nested market for diag events
                if _diag:
                    logger.info(
                        "  DIAG [P1_market] event=%r  mkt_slug=%r  q=%r  type=%r",
                        event_slug, mkt_slug, question, mkt_type,
                    )

                # Canonical moneyline fast-path: Polymarket's per-game moneyline
                # market always has the same slug as the event itself (no suffix).
                # If the slug matches, skip all P2 keyword filters — the event slug
                # already passed GAME_SLUG_RE which guarantees it's a game market.
                _is_canonical_ml = (mkt_slug == event_slug)

                # P2a: blocklist — explicit non-moneyline keywords
                _mkt_text = (question + " " + mkt_slug + " " + mkt_type).lower()
                _hit_kw = None if _is_canonical_ml else next((kw for kw in _NON_ML_KW if kw in _mkt_text), None)
                if _hit_kw:
                    skipped_keyword += 1
                    if _diag:
                        logger.info(
                            "  DIAG [P2a_non_moneyline] event=%r  mkt_slug=%r"
                            "  hit_kw=%r  q=%r",
                            event_slug, mkt_slug, _hit_kw, question,
                        )
                    else:
                        logger.debug(
                            "Skip non_moneyline: slug=%r q=%r", mkt_slug, question,
                        )
                    continue

                # P2b: run-line/spread indicator — ±N.5 in question text
                if not _is_canonical_ml and _re.search(r'[+\-]\d+\.5', question):
                    skipped_keyword += 1
                    if _diag:
                        logger.info(
                            "  DIAG [P2b_alt_line] event=%r  mkt_slug=%r  q=%r",
                            event_slug, mkt_slug, question,
                        )
                    else:
                        logger.debug("Skip alt_line (±N.5): q=%r", question)
                    continue

                # P2c: require at least one positive moneyline keyword
                # Accepts: "moneyline", "win", "beat", "defeat", "top", "edge",
                #          "cover", "score more" — or a bare "TEAM vs TEAM" slug
                #          pattern (no verb needed when the event slug itself is
                #          a per-game moneyline slug that passed GAME_SLUG_RE).
                q_lower = question.lower()
                _pos_kw_hit = _is_canonical_ml or (
                    "moneyline" in q_lower or "win" in q_lower or
                    "beat" in q_lower or "defeat" in q_lower or
                    "top" in q_lower or "edge" in q_lower or
                    " vs" in q_lower or " vs." in q_lower
                )
                if not _pos_kw_hit:
                    skipped_keyword += 1
                    if _diag:
                        logger.info(
                            "  DIAG [P2c_no_keyword] event=%r  mkt_slug=%r  q=%r",
                            event_slug, mkt_slug, question,
                        )
                    else:
                        logger.debug("Skip no_keyword: slug=%r q=%r", mkt_slug, question)
                    continue

                # Token IDs — events endpoint stores them as clobTokenIds (JSON string or list)
                clob_raw = mkt_raw.get("clobTokenIds") or mkt_raw.get("clob_token_ids") or "[]"
                if isinstance(clob_raw, str):
                    try:
                        clob_ids = _json.loads(clob_raw)
                    except Exception:
                        clob_ids = []
                else:
                    clob_ids = list(clob_raw)
                yes_token_id = str(clob_ids[0]) if len(clob_ids) > 0 else ""
                no_token_id = str(clob_ids[1]) if len(clob_ids) > 1 else ""

                market_id = str(mkt_raw.get("id") or mkt_raw.get("conditionId") or "")

                parsed = parse_question_teams(question)
                if not parsed:
                    skipped_parse += 1
                    if len(unparseable_examples) < 10:
                        unparseable_examples.append(
                            f"  event={event_slug!r}  slug={mkt_slug!r}  q={question!r}"
                        )
                    continue

                tracked_team, opponent = parsed
                tracked_team_registry = _registry_alias(tracked_team)
                opponent_registry = _registry_alias(opponent)

                game_reg = get_game_by_teams(tracked_team_registry, opponent_registry)
                if game_reg is None:
                    game_reg = get_game_by_teams(opponent_registry, tracked_team_registry)
                if game_reg is None:
                    skipped_not_live += 1
                    _reg_snapshot = [(g.away_team, g.home_team, g.status, g.is_live)
                                     for g in get_all_games()]
                    logger.info(
                        "NOT-LIVE [no_registry_match] event=%r  date=%s"
                        "  parsed=(%s vs %s)"
                        "  registry_games=%s",
                        event_slug, game_date,
                        tracked_team, opponent,
                        _reg_snapshot,
                    )
                    continue

                if not game_reg.is_live:
                    skipped_not_live += 1
                    logger.info(
                        "NOT-LIVE [not_live_status] event=%r  date=%s"
                        "  parsed=(%s vs %s)"
                        "  registry_match=%s@%s  status=%s  is_live=%s",
                        event_slug, game_date,
                        tracked_team, opponent,
                        game_reg.away_team, game_reg.home_team,
                        game_reg.status, game_reg.is_live,
                    )
                    continue

                # Slug date guard: tomorrow's pre-created betting event must not
                # attach to today's live game.  Both pass the date window and the
                # team-name match, but game_date > today means this event is for a
                # future game, not the one currently in progress.
                if game_date > today:
                    skipped_not_live += 1
                    logger.info(
                        "NOT-LIVE [future_dated_slug] event=%r  date=%s"
                        "  parsed=(%s vs %s)"
                        "  registry_match=%s@%s  status=%s  is_live=%s",
                        event_slug, game_date,
                        tracked_team, opponent,
                        game_reg.away_team, game_reg.home_team,
                        game_reg.status, game_reg.is_live,
                    )
                    continue

                event_candidates.append({
                    "market_id": market_id,
                    "yes_token_id": yes_token_id,
                    "no_token_id": no_token_id,
                    "market_slug": mkt_slug,
                    "question": question,
                    "home_team": game_reg.home_team,
                    "away_team": game_reg.away_team,
                    "tracked_team": tracked_team,
                    "event_slug": event_slug,
                    "event_date": str(game_date),
                })

            # P3: pick exactly one canonical moneyline per event.
            # Multiple "win" variants (e.g. "Will X win?" and "X vs Y Moneyline")
            # can survive the filters above. Rank by how explicitly moneyline the
            # slug/question is; take the lowest-ranked (most explicit) candidate.
            if not event_candidates:
                continue

            def _ml_rank(c: dict) -> int:
                s = c["market_slug"].lower()
                q = c["question"].lower()
                if "moneyline" in s or "-ml-" in s or s.endswith("-ml"):
                    return 0   # slug explicitly says moneyline
                if "moneyline" in q:
                    return 1   # question says moneyline
                if "winner" in s:
                    return 2   # slug says winner
                return 3       # generic "will X win" phrasing

            canonical = min(event_candidates, key=_ml_rank)
            if len(event_candidates) > 1:
                n_extra = len(event_candidates) - 1
                skipped_dup_event += n_extra
                suppressed = [
                    c["market_slug"] for c in event_candidates
                    if c["market_id"] != canonical["market_id"]
                ]
                logger.info(
                    "Event %s: %d candidates → kept %r, suppressed %d "
                    "(duplicate_event_market): %s",
                    event_slug, len(event_candidates), canonical["market_slug"],
                    n_extra, suppressed,
                )
            markets.append(canonical)

        logger.info(
            "Discovery: %d live | skipped: %d non-mlb/date, %d closed, "
            "%d non-moneyline/no-keyword, %d unparseable, %d not-live, "
            "%d duplicate_event_market",
            len(markets), skipped_non_mlb, skipped_closed,
            skipped_keyword, skipped_parse, skipped_not_live, skipped_dup_event,
        )
        if unparseable_examples:
            logger.info("Unparseable market samples:\n%s", "\n".join(unparseable_examples))
        return markets

    except Exception as e:
        logger.warning("Market discovery failed: %s", e, exc_info=True)
        return []


def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="MLB model recommendation loop (shadow mode)")
    parser.add_argument("--loop-seconds", type=int, default=LOOP_SECONDS)
    parser.add_argument("--phase", default=PHASE)
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  MLB Model Recommendation Engine — phase=%s", args.phase)
    logger.info("=" * 60)

    # Startup checks
    from core.selfcheck import startup_check
    from sports.mlb.winprob_inference import load_artifacts
    from integration.shadow_mode_logger import get_logger

    result = startup_check()
    logger.info("Startup check: mode=%s", result.mode)
    if result.mode == "HALT":
        logger.error("Startup HALT. Exiting.")
        return

    shadow_log = get_logger()
    loop = 0

    while True:
        loop += 1
        loop_start = time.monotonic()

        try:
            from sports.mlb.live_game_registry import (
                refresh_registry, registry_age_seconds, is_registry_stale,
            )

            # Explicitly refresh every loop — do not rely on lazy refresh
            # inside get_game_by_teams(), which is only called when markets parse.
            # If all markets fail to parse, the registry would never refresh
            # and would go stale within 60s.
            try:
                refresh_registry()
            except Exception as _re:
                logger.error("Registry refresh failed: %s", _re)

            if is_registry_stale():
                logger.error(
                    "Loop %d: registry stale (%.0fs) — suppressing actionable recommendations",
                    loop, registry_age_seconds(),
                )
                time.sleep(max(0.0, args.loop_seconds - (time.monotonic() - loop_start)))
                continue

            markets = _discover_mlb_markets()
            if not markets:
                logger.info("Loop %d: no markets discovered", loop)
            else:
                # P3: log every candidate so event slug/date is visible in traces
                for _m in markets:
                    logger.info(
                        "  candidate: event=%s date=%s  %s vs %s",
                        _m.get("event_slug", "?"), _m.get("event_date", "?"),
                        _m.get("tracked_team", "?"), _m.get("home_team", "?"),
                    )

                recs = get_recommendations(markets)

                # P2: dedupe — at most one actionable rec per live game.
                # Multiple Polymarket markets (different slug dates, multiple market
                # types) can still map to the same live ESPN game after P1 fix if
                # Polymarket lists two moneyline variants for the same matchup.
                # Keep the actionable rec with the best absolute edge.
                _seen: dict[tuple, int] = {}   # (home_team, away_team) -> idx in deduped
                deduped: list = []
                dup_suppressed = 0
                for _rec in recs:
                    if _rec.action == "NO_TRADE":
                        deduped.append(_rec)
                        continue
                    _gk = (_rec.home_team, _rec.away_team)
                    _ae = max(abs(_rec.edge_yes), abs(_rec.edge_no))
                    if _gk not in _seen:
                        _seen[_gk] = len(deduped)
                        deduped.append(_rec)
                    else:
                        _xi = _seen[_gk]
                        _xe = max(abs(deduped[_xi].edge_yes), abs(deduped[_xi].edge_no))
                        if _ae > _xe:
                            logger.info(
                                "Dup suppressed (replaced by higher edge=%.3f): "
                                "%s @ %s  dropped_mid=%s",
                                _ae, _rec.away_team, _rec.home_team,
                                deduped[_xi].market_id,
                            )
                            deduped[_xi] = _rec
                        else:
                            logger.info(
                                "Dup suppressed (existing edge=%.3f kept): "
                                "%s @ %s  dropped_mid=%s",
                                _xe, _rec.away_team, _rec.home_team,
                                _rec.market_id,
                            )
                        dup_suppressed += 1
                recs = deduped
                actionable = [r for r in recs if r.action != "NO_TRADE"]
                logger.info(
                    "Loop %d: %d markets -> %d recs (%d actionable, %d dups suppressed)",
                    loop, len(markets), len(recs), len(actionable), dup_suppressed,
                )

                for rec in recs:
                    shadow_log.log(rec)

        except Exception as e:
            logger.error("Loop error: %s", e, exc_info=True)

        elapsed = time.monotonic() - loop_start
        sleep_for = max(0.0, args.loop_seconds - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
