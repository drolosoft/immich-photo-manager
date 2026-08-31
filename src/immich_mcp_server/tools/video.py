"""Video frames: cut frames from a video locally, with a confirmation gate above 12 frames.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import asyncio
import json

from mcp.server.fastmcp import Context, Image

from .. import video_frames
from ..app import mcp, _client
from ._common import _entry_to_image

async def _video_plan(ctx: Context, asset_id: str, count: int, size: str,
                      start: float, end: float, interval: float, confirm: bool):
    """Download the video, plan the frames, and either extract or return the gate JSON."""
    data = await _client(ctx).get_video_playback(asset_id)
    duration = await asyncio.to_thread(video_frames.probe_duration, data)
    try:
        planned = video_frames.plan_timestamps(duration, count, interval, start, end)
    except video_frames.TooManyFrames as exc:
        return None, {"error": str(exc), "duration": duration}
    if not planned:
        return None, {
            "error": "could not determine the video duration; try count instead of interval",
            "duration": duration,
        }
    if len(planned) > video_frames.CONFIRM_ABOVE and not confirm:
        seg_start, seg_end = video_frames.segment_bounds(duration, start, end)
        return None, {
            "confirm_required": True, "asset_id": asset_id, "duration": duration,
            "segment": [round(seg_start, 3), round(seg_end, 3)], "frames_planned": len(planned),
            "estimated_tokens": video_frames.estimate_tokens(len(planned), size),
            "hint": "Tell the user the number of frames and tokens; call again with confirm=true to proceed.",
        }
    result = await asyncio.to_thread(
        video_frames.extract_frames, data, count, size, None, start, end, interval
    )
    return result, None


@mcp.tool(structured_output=False)
async def get_video_frames(
    ctx: Context, asset_id: str, count: int = 6, size: str = "thumbnail",
    start: float = 0.0, end: float = 0.0, interval: float = 0.0, confirm: bool = False,
    sheet: bool = False,
) -> list[Image] | str:
    """Get frames of a video as image blocks, to "watch" a clip. Immich keeps one
    poster per video; this downloads the video and cuts frames locally (PyAV, a
    dependency since 1.7.1, or ffmpeg on PATH). Every frame is one
    image for the model. Workflow: 6 frames first; to look closer, narrow with
    start/end or use interval (down to 1 s). Above 12 frames the tool returns a JSON
    plan with frames_planned and estimated_tokens instead of images: show it to the
    user and call again with confirm=true only if they agree. Hard cap 120 per call.
    For base64 JSON with timestamps use get_video_frames_json. Read-only.

    Args:
        asset_id: The video asset's UUID.
        count: Frames evenly spaced over the segment (default 6). Ignored when interval > 0.
        size: 'thumbnail' (250px, ~1.6k tokens per frame) or 'preview' (1440px, ~6.4k). Default 'thumbnail'.
        start: Segment start in seconds (default 0).
        end: Segment end in seconds (0 = to the end).
        interval: One frame every N seconds instead of count (1 = one per second, the maximum granularity).
        confirm: Required (true) when more than 12 frames would be produced; ask the user first.
        sheet: Pack the frames into contact sheets (30 per image, timestamps burned in):
            a long video becomes one or two images instead of dozens, so no
            confirmation is needed. Use it to skim, then cut the moments that matter.

    Returns: JPEG image blocks in time order, or JSON (confirmation plan / error).
    """
    try:
        result, gate = await _video_plan(ctx, asset_id, count, size, start, end, interval,
                                         confirm or sheet)
    except video_frames.NoVideoBackend as exc:
        return json.dumps({"error": str(exc)})
    if gate is not None:
        return json.dumps(gate)
    if sheet:
        return [_entry_to_image(entry) for entry in video_frames.contact_sheets(result["frames"])]
    return [_entry_to_image(frame) for frame in result["frames"]]


@mcp.tool()
async def get_video_frames_json(
    ctx: Context, asset_id: str, count: int = 6, size: str = "thumbnail",
    start: float = 0.0, end: float = 0.0, interval: float = 0.0, confirm: bool = False,
) -> str:
    """Frames of a video as base64 JPEG with timestamps, for HTML galleries and
    skills. Same parameters, gate (confirm above 12) and cap (120) as get_video_frames. Read-only.

    Args:
        asset_id: The video asset's UUID.
        count: Frames evenly spaced over the segment (default 6). Ignored when interval > 0.
        size: 'thumbnail' (250px, ~1.6k tokens per frame) or 'preview' (1440px, ~6.4k). Default 'thumbnail'.
        start: Segment start in seconds (default 0).
        end: Segment end in seconds (0 = to the end).
        interval: One frame every N seconds instead of count (1 = one per second, the maximum granularity).
        confirm: Required (true) when more than 12 frames would be produced; ask the user first.

    Returns: JSON {asset_id, duration, backend, count, frames:[{timestamp, data, type}]},
    a confirmation plan {confirm_required, frames_planned, estimated_tokens, ...}, or {"error": ...}.
    """
    try:
        result, gate = await _video_plan(ctx, asset_id, count, size, start, end, interval, confirm)
    except video_frames.NoVideoBackend as exc:
        return json.dumps({"error": str(exc)})
    if gate is not None:
        return json.dumps(gate)
    return json.dumps(
        {"asset_id": asset_id, "duration": result["duration"], "backend": result["backend"],
         "count": len(result["frames"]), "frames": result["frames"]}
    )


