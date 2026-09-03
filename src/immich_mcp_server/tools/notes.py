"""Asset notes: the plugin's own memory on each asset.

Immich lets an app store key -> JSON object pairs on an asset (invisible in the
Immich UI, not searchable). This module keeps ONE key, `immich-photo-manager`,
with two capped lists: the reviews a model made (verdict + reason) and the
actions the plugin took (what + detail). Tags remain the visible state a user
acts on in Immich; these notes carry the why, and let the next session skip
what was already reviewed.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json
from datetime import datetime, timezone

from mcp.server.mcpserver import Context

from ..app import mcp, _client

# The single metadata key this plugin owns on an asset. Other apps' keys are
# never read as ours nor deleted.
NOTES_KEY = "immich-photo-manager"

# Closed vocabulary so that verdicts stay comparable across sessions and
# models; the reason next to them is free text.
VERDICTS = ("keep", "delete_candidate", "duplicate_of", "needs_check")

# Each list keeps the newest entries only; the notes are a memory, not a log.
HISTORY_LIMIT = 10


def _now() -> str:
    """UTC timestamp for a note. Isolated so tests can pin it."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty_notes() -> dict:
    return {"reviews": [], "actions": []}


async def _load_notes(client, asset_id: str) -> dict:
    """The plugin's notes on an asset, or an empty structure when there are none.
    Reads every key the asset has and picks ours; lists always exist."""
    entries = await client.get_asset_metadata(asset_id)
    for entry in entries:
        if entry.get("key") == NOTES_KEY:
            value = entry.get("value") or {}
            return {
                "reviews": list(value.get("reviews") or []),
                "actions": list(value.get("actions") or []),
            }
    return _empty_notes()


async def _append_note(client, asset_id: str, section: str, entry: dict) -> None:
    """Read-modify-write one asset's notes: append to a section, keep the newest
    HISTORY_LIMIT entries, store back under the plugin's key only."""
    current = await _load_notes(client, asset_id)
    current[section].append(entry)
    current[section] = current[section][-HISTORY_LIMIT:]
    await client.upsert_asset_metadata(asset_id, NOTES_KEY, current)


@mcp.tool()
async def review_assets(
    ctx: Context, asset_ids: list[str], verdict: str, reason: str = ""
) -> str:
    """Remember a review verdict on assets, with the reason, so a later session
    does not redo the analysis and the why survives. Use this after deciding what
    to do with a photo in a cleanup or duplicate pass — together with a tag when
    the user must see the state in Immich (tags are visible there, notes are not).
    Side effect: writes the plugin's metadata key on each asset; other apps' keys
    are untouched.

    Args:
        asset_ids: The assets the verdict applies to.
        verdict: One of 'keep', 'delete_candidate', 'duplicate_of', 'needs_check'.
        reason: Free text explaining the verdict (e.g. 'near-identical to IMG_6367,
            keep that one'). Short and concrete beats long.

    Returns: JSON with success, the number of assets reviewed, the verdict, and a
    failed array of {asset_id, error} for any asset that could not be written.
    Success is true only when nothing failed.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})

    if verdict not in VERDICTS:
        return json.dumps({
            "error": f"Unknown verdict '{verdict}'. Use one of: {', '.join(VERDICTS)}.",
        })

    entry = {"at": _now(), "verdict": verdict, "reason": reason}
    reviewed = 0
    failed = []
    for asset_id in asset_ids:
        # One bad id must not throw away the assets already annotated: note the
        # failure and carry on, the way rotate_assets does.
        try:
            await _append_note(_client(ctx), asset_id, "reviews", entry)
            reviewed += 1
        except Exception as exc:
            failed.append({"asset_id": asset_id, "error": str(exc)})

    return json.dumps({"success": not failed, "reviewed": reviewed,
                       "verdict": verdict, "failed": failed}, default=str)


@mcp.tool()
async def record_action(
    ctx: Context, asset_ids: list[str], action: str, detail: str = ""
) -> str:
    """Remember something the plugin did to assets and why, for audit or undo:
    which album they went into and from what prompt, what date they had before a
    fix, why they were rotated. Side effect: writes the plugin's metadata key on
    each asset; other apps' keys are untouched.

    Args:
        asset_ids: The assets the action touched.
        action: Short verb-like label (e.g. 'added_to_album', 'date_fixed', 'rotated').
        detail: Free text with the context worth keeping (album name, previous
            value, the user's request).

    Returns: JSON with success, the number of assets recorded, the action, and a
    failed array of {asset_id, error} for any asset that could not be written.
    Success is true only when nothing failed.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})

    entry = {"at": _now(), "action": action, "detail": detail}
    recorded = 0
    failed = []
    for asset_id in asset_ids:
        # A half-written batch is worse than a reported one: keep going and say
        # exactly which assets missed out.
        try:
            await _append_note(_client(ctx), asset_id, "actions", entry)
            recorded += 1
        except Exception as exc:
            failed.append({"asset_id": asset_id, "error": str(exc)})

    return json.dumps({"success": not failed, "recorded": recorded,
                       "action": action, "failed": failed}, default=str)


@mcp.tool()
async def get_asset_notes(ctx: Context, asset_id: str) -> str:
    """The plugin's notes on one asset: past review verdicts with reasons and
    recorded actions, newest last. Empty lists when it was never annotated.
    Read-only.

    Args:
        asset_id: The asset to read.

    Returns: JSON with asset_id, reviews [{at, verdict, reason}] and
    actions [{at, action, detail}].
    """
    notes = await _load_notes(_client(ctx), asset_id)
    return json.dumps({"asset_id": asset_id, **notes}, default=str)


@mcp.tool()
async def get_assets_notes(ctx: Context, asset_ids: list[str]) -> str:
    """Which of these assets already carry notes, and their last verdict — the
    call that lets a cleanup pass skip what an earlier session reviewed. Immich
    cannot search this metadata, so the server is asked once per asset (no
    tokens spent on the ones without notes). Read-only.

    Args:
        asset_ids: The candidates to check (an album's assets, a search result).

    Returns: JSON with checked (how many were asked), annotated (one compact row
    per asset that has notes — asset_id, last_verdict, last_reason, last_review_at,
    and the reviews/actions counts) and a failed array of {asset_id, error} for the
    assets that could not be read. Success is true only when nothing failed.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})

    annotated = []
    checked = 0
    failed = []
    for asset_id in asset_ids:
        # An id that no longer exists must not hide the notes of the rest of the
        # batch, which is the whole point of this call.
        try:
            notes = await _load_notes(_client(ctx), asset_id)
            checked += 1
        except Exception as exc:
            failed.append({"asset_id": asset_id, "error": str(exc)})
            continue

        if not notes["reviews"] and not notes["actions"]:
            continue

        last = notes["reviews"][-1] if notes["reviews"] else {}
        annotated.append({
            "asset_id": asset_id,
            "last_verdict": last.get("verdict"),
            "last_reason": last.get("reason"),
            "last_review_at": last.get("at"),
            "reviews": len(notes["reviews"]),
            "actions": len(notes["actions"]),
        })

    return json.dumps({"success": not failed, "checked": checked,
                       "annotated": annotated, "failed": failed}, default=str)


@mcp.tool()
async def clear_asset_notes(ctx: Context, asset_ids: list[str]) -> str:
    """Forget the plugin's notes on assets (reviews and actions). Only the
    plugin's own key is removed; metadata other apps stored stays. Side effect:
    deletes the notes on the server.

    Args:
        asset_ids: The assets to clear.

    Returns: JSON with success, how many assets were cleared, and a failed array
    of {asset_id, error}. Success is true only when nothing failed.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})

    cleared = 0
    failed = []
    for asset_id in asset_ids:
        # Clearing is a best-effort cleanup: one unreachable asset should not
        # leave the rest of the batch annotated.
        try:
            await _client(ctx).delete_asset_metadata(asset_id, NOTES_KEY)
            cleared += 1
        except Exception as exc:
            failed.append({"asset_id": asset_id, "error": str(exc)})

    return json.dumps({"success": not failed, "cleared": cleared, "failed": failed},
                      default=str)
