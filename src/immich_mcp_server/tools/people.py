"""People and faces: list, search, update, merge, thumbnails, faces per asset, reassign a face.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client

@mcp.tool()
async def list_people(
    ctx: Context, page: int = 1, size: int = 50, with_hidden: bool = False
) -> str:
    """List all recognized people (face clusters) in the library. Use this to browse
    who appears in the photo library or find a person's ID. For searching by name,
    use search_people instead. Read-only.

    Args:
        page: Page number, starting from 1 (default 1).
        size: Results per page (default 50).
        with_hidden: Include people marked as hidden (default false).

    Returns: JSON with total count, page, and people array (each with id, name, thumbnailPath, photoCount).
    """
    result = await _client(ctx).list_people(page=page, size=size, with_hidden=with_hidden)
    people = result.get("people", [])
    total = result.get("total", len(people))
    return json.dumps({"total": total, "page": page, "people": people}, default=str)


@mcp.tool()
async def get_person(ctx: Context, person_id: str) -> str:
    """Get full details for a specific person including name, birth date, and photo count.
    Use this after finding a person via list_people or search_people. Read-only.

    Args:
        person_id: The person's UUID (from list_people or search_people).

    Returns: JSON with person details (id, name, birthDate, isHidden, photoCount, thumbnailPath).
    """
    result = await _client(ctx).get_person(person_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_person(
    ctx: Context,
    person_id: str,
    name: str = "",
    birth_date: str = "",
    is_hidden: bool | None = None,
    is_favorite: bool | None = None,
    feature_face_asset_id: str = "",
    color: str = "",
) -> str:
    """Update a person's profile details. Use this to name unnamed faces, set birth dates,
    hide clutter faces, or change the representative thumbnail. Only provided fields are
    modified. Side effect: changes person metadata in Immich.

    Args:
        person_id: The person's UUID.
        name: Display name (e.g. 'John Smith'). Set to name unnamed face clusters.
        birth_date: ISO date (e.g. '1990-05-15').
        is_hidden: Hide from the People view (useful for strangers/clutter).
        is_favorite: Mark as a favorite person.
        feature_face_asset_id: Asset UUID whose face crop becomes the person's thumbnail.
        color: Hex color label for UI grouping.

    Returns: JSON with the updated person object.
    """
    fields: dict = {}
    if name:
        fields["name"] = name
    if birth_date:
        fields["birthDate"] = birth_date
    if is_hidden is not None:
        fields["isHidden"] = is_hidden
    if is_favorite is not None:
        fields["isFavorite"] = is_favorite
    if feature_face_asset_id:
        fields["featureFaceAssetId"] = feature_face_asset_id
    if color:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide at least one field."})
    result = await _client(ctx).update_person(person_id, **fields)
    return json.dumps(result, default=str)


@mcp.tool()
async def merge_people(
    ctx: Context, person_id: str, merge_ids: list[str], confirm: bool = False
) -> str:
    """Merge multiple person clusters into one. Use this when the same real person has
    been split into multiple face clusters. DESTRUCTIVE and IRREVERSIBLE: merged persons
    are permanently deleted and all their faces transfer to the target. Without
    confirm=true nothing happens: the call returns who would be kept and who would
    disappear, so the user can check the names before the merge.

    Args:
        person_id: The target person UUID to keep (receives all merged faces).
        merge_ids: List of person UUIDs to absorb into the target. These persons are permanently deleted.
        confirm: Pass true only after the user has seen the preview and agreed.

    Returns: JSON with the preview (confirm_required, keep, merge) or the merge result.
    """
    if not confirm:
        # An irreversible merge deserves the same gate as emptying the trash:
        # show names, not ids, and let the person decide.
        keep = await _client(ctx).get_person(person_id)
        merge = [await _client(ctx).get_person(merge_id) for merge_id in merge_ids]
        return json.dumps({
            "confirm_required": True,
            "keep": {"id": keep.get("id"), "name": keep.get("name")},
            "merge": [{"id": person.get("id"), "name": person.get("name")} for person in merge],
            "note": "Irreversible. Call again with confirm=true to merge.",
        }, default=str)

    result = await _client(ctx).merge_people(person_id, merge_ids)
    return json.dumps(result, default=str)


@mcp.tool()
async def search_people(ctx: Context, name: str, with_hidden: bool = False) -> str:
    """Search for people by name (partial match). Use this when you know the person's
    name. For browsing all people, use list_people instead. Read-only.

    Args:
        name: Full or partial name to match (case-insensitive).
        with_hidden: Include hidden people in results (default false).

    Returns: JSON array of matching people with id, name, and photo count.
    """
    result = await _client(ctx).search_people(name, with_hidden=with_hidden)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_person_thumbnail(ctx: Context, person_id: str) -> str:
    """Get a base64-encoded face crop thumbnail for a person. Use this to visually
    identify a person before merging or renaming. Read-only.

    Args:
        person_id: The person's UUID.

    Returns: JSON with 'data' (base64 string of face crop) and 'type' (MIME type).
    """
    result = await _client(ctx).get_person_thumbnail(person_id)
    return json.dumps(result)


@mcp.tool()
async def get_asset_faces(ctx: Context, asset_id: str) -> str:
    """Get all detected faces in a photo with their person assignments. Use this to see
    who is in a specific photo or to find face IDs for reassign_face. Read-only.

    Args:
        asset_id: The asset's UUID.

    Returns: JSON array of face detections (each with face_id, person_id, person_name, bounding box).
    """
    result = await _client(ctx).get_asset_faces(asset_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def reassign_face(ctx: Context, face_id: str, person_id: str) -> str:
    """Reassign a detected face to a different person. Use this to correct face recognition
    mistakes (e.g. a face wrongly attributed to Person A should be Person B). Get face_id
    from get_asset_faces first. Side effect: permanently changes face-to-person mapping.

    Args:
        face_id: The face detection UUID (from get_asset_faces results).
        person_id: The correct person UUID to assign this face to.

    Returns: JSON with the updated face assignment.
    """
    result = await _client(ctx).reassign_face(face_id, person_id)
    return json.dumps(result, default=str)
