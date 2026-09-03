# 📝 The plugin remembers: notes on assets

A cleanup pass over a big album is expensive: thumbnails looked at, metadata read, a judgement made on each photo. Close the session and all of it is gone, so the next pass starts from zero on the same photos. Immich lets an app store key to JSON pairs on an asset, and the plugin uses exactly one key, `immich-photo-manager`, to keep what a model decided and why. This page shows the design, then a real Claude Code session that reviewed an album with it against Immich 3.1.0, and the raw shapes from the 2.0.9 transcripts.

## 1. The design in five lines

Tags are the visible state a user acts on inside Immich. Notes are the why, and they are invisible in the Immich UI and not searchable there. The key holds two lists, `reviews` (a verdict plus its reason) and `actions` (what the plugin did plus the detail worth keeping), each capped at its newest 10 entries, because this is a memory and not a log. Verdicts come from a closed vocabulary, `keep`, `delete_candidate`, `duplicate_of` and `needs_check`, so they stay comparable across sessions and models. Nothing writes a note on its own: a tool call does, after a decision. And `clear_asset_notes` removes only this plugin's key, never another app's.

## 2. Review an album, remember every decision

```
Review the Lab Album for cleanup. Look at its thumbnails, decide for each photo
whether to keep it or mark it as a delete candidate, and remember every decision with
its reason using the plugin's notes so a later session can skip them. Then show me
which assets carry notes now, with their last verdict. Finally clear all the notes you
wrote so the library is back to how it was. Keep the report short.
```

Claude loaded the `photo-cleanup` skill on its own, fetched the album's thumbnails, and before judging any of them called `get_assets_notes` on the five assets, the check for work an earlier session had already done (the skill tells it to). Then one `review_assets` call per asset, a read-back with `get_assets_notes`, and `clear_asset_notes`:

> **Verdicts written, then read back with `get_assets_notes`:**
>
> | Asset | Last verdict | Reason |
> |---|---|---|
> | photo4.jpg | keep | Camera and GPS (Lisbon), rated 3 stars, largest file in the album |
> | photo3.jpg | keep | Favourited, captioned "Tree in Sintra", green frame matches the caption |
> | photo2.jpg | keep | Camera and GPS (Porto), already tagged by you |
> | photo1.jpg | delete_candidate | Solid red frame, caption says "blue boat in Porto" but GPS is Lisbon, same spot as the better photo4 |
> | clip.mp4 | delete_candidate | 3-second 640x360 clip, no camera or GPS data, flat magenta frame |
>
> **Cleanup.** The five notes were removed with `clear_asset_notes` and a follow-up read returned no annotated assets. I skipped tagging the delete candidates in Immich since you asked for the library to end unchanged. If you want the two candidates actually trashed, say so and I'll send them to the recoverable trash.

It also opened its report with a caveat rather than a claim:

> This session blocked writing decoded thumbnails to disk, so I could not view the images directly. I decoded each thumbnail's embedded thumbhash colour summary by hand and combined it with the EXIF metadata. All five are flat single-colour lab renders, so the verdicts rest on metadata and those colour reads rather than a true visual inspection.

Nothing was trashed and nothing was tagged. The two delete candidates stayed candidates, which is the point of a verdict.

## 3. The call that saves the next pass

`get_assets_notes` takes a list of ids and answers which of them already carry notes, with the last verdict on each. It is the "skip what I already reviewed" call, and it costs one request instead of a re-analysis:

```json
{ "success": true, "checked": 5,
  "annotated": [
    { "asset_id": "d39681a2-...", "last_verdict": "delete_candidate",
      "last_reason": "near-identical framing, keep only the sharper one",
      "last_review_at": "2026-09-03T08:26:45Z", "reviews": 1, "actions": 1 },
    { "asset_id": "652d083f-...", "last_verdict": "delete_candidate",
      "last_reason": "near-identical framing, keep only the sharper one",
      "last_review_at": "2026-09-03T08:26:45Z", "reviews": 1, "actions": 0 } ],
  "failed": [] }
```

Three assets were checked and came back with nothing, so they are not in `annotated` at all. `review_assets` and `record_action` answer in the same spirit, counting what worked and naming what did not:

```json
{ "success": true, "reviewed": 2, "verdict": "delete_candidate", "failed": [] }
{ "success": true, "recorded": 1, "action": "trashed", "failed": [] }
```

`get_asset_notes(asset_id)` reads one asset in full, `get_asset_info(asset_id, with_notes=true)` folds the notes into the normal metadata answer, and `clear_asset_notes` returns `{"success": true, "cleared": 2, "failed": []}`.

## 4. Acting on a batch, and the gate before a merge

Once the verdicts exist, the follow-up is usually a bulk write. `update_assets_metadata` applies one change to many assets in a single call:

```json
{ "asset_ids": ["e1b4b195-...", "14a743d4-..."], "rating": 4 }
```

```json
{ "success": true, "updated": 2 }
```

Ratings run 1 to 5, with -1 for rejected, and `rating=0` is refused up front because Immich 3.x rejects it. Some calls do not run at all on the first try. `merge_people` is irreversible, so it previews instead:

```json
{ "confirm_required": true,
  "keep":  { "id": "17490fb4-...", "name": "Abraham Lincoln" },
  "merge": [ { "id": "2c5d3e53-...", "name": "Albert Einstein" } ],
  "failed": [],
  "note": "Irreversible. Call again with confirm=true to merge." }
```

The names come back before anything happens, which is what catches the case where two ids are not the two people the user meant.

## What leaves your network

Notes are stored on your Immich server as metadata on the asset, next to the photo they describe. They never leave it, and a later session reads them back from there. Clearing them removes this plugin's key only, so anything another app wrote stays where it is.

---

*The raw calls come from the published 2.0.9 package driven against Immich 2.7.5 and 3.1.0, the same lab as [`tests/live/`](../../tests/live/).*
