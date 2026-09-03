# 🗂️ Memories and stacks: keep everything, show less

Two Immich features that a chat is unusually good at driving. A memory is an "on this day" collection: a date, a year to look back to, and a handful of assets. A stack groups near-identical shots into one item fronted by a cover, with every frame still in the library. Both are reversible, which is why they are the right answer when a cleanup pass finds forty versions of the same thing and nobody wants to press delete. This page runs both from one prompt in a real Claude Code session against Immich 3.1.0, then shows the raw calls from the 2.0.9 transcripts.

## 1. The round trip in one prompt

```
Take the photos in the Lab Album. First group the two that look most alike into a
stack and show me the stacks. Then create an 'on this day' memory for today looking
back to 2020 with those same two photos, list my memories, and finally dissolve the
stack and delete the memory so the library is as it was. Tell me each step in one line.
```

Claude read the album, looked at the thumbnails to decide which two were alike, and then ran `create_stack`, `create_memory`, `list_stacks`, `list_memories`, `delete_stack`, `delete_memory`, with a final `list_stacks` and `list_memories` to check the library was back where it started. Its answer:

> All six steps ran and the library is verified back to its starting state, with zero stacks and zero memories, exactly as before.
>
> - **Picked the pair.** The Lab Album holds five solid-colour test cards, and photo2 "BOAT" and photo3 "TREE" match best: same layout, same font, and both a single four-letter word.
> - **Created the stack.** Grouped photo2 and photo3 into one stack with photo2 as the cover.
> - **Listed the stacks.** One stack in the library, containing exactly photo2 and photo3.
> - **Created the memory.** An "on this day" memory for 3 September 2026 looking back to 2020 with those same two photos.
> - **Listed the memories.** One memory in the library, the one just created, with both photos attached.
> - **Dissolved and deleted.** Removed the stack and the memory, and a final check shows no stacks and no memories left.

## 2. What a stack costs and what it saves

`create_stack` takes at least two asset ids, in order, and the first one becomes the cover:

```json
{ "asset_ids": ["e1b4b195-b190-4018-be9b-abd953804968", "14a743d4-dd73-4ad4-9f24-19da5b58db5a"] }
```

```json
{ "id": "605294bf-2d01-41e8-b5cb-11b205a650f9",
  "primary_asset_id": "e1b4b195-b190-4018-be9b-abd953804968",
  "asset_count": 2,
  "assets": [ { "asset_id": "e1b4b195-...", "filename": "photo1.jpg" },
              { "asset_id": "14a743d4-...", "filename": "photo2.jpg" } ] }
```

`list_stacks` returns the same shape wrapped in `{total, stacks}`. `update_stack(stack_id, primary_asset_id)` changes which frame fronts the group, and the new cover must already be in the stack. `delete_stack` dissolves the grouping and says so plainly:

```json
{ "success": true, "deleted": "605294bf-...", "note": "The assets stay in the library, only the grouping is gone." }
```

Nothing was deleted, nothing was moved, and the library shows one item where there were two.

## 3. The 34 clips of one car

Stacks came up in [issue #15](https://github.com/drolosoft/immich-photo-manager/issues/15), a thread about cleaning up a 530-asset car-spotting album: 34 clips of the same blue Aventador, sitting next to each other on the timeline. Deleting 33 of them is a decision nobody wants to make in a chat window, and a "delete candidate" tag only leaves the same decision for later. A stack ends the clutter without ending the clips: one item on the timeline, all 34 still there, and `delete_stack` undoes it in a call. The gentler cleanup is usually the one that actually gets done.

## 4. A memory for a date

`create_memory` needs the date it is shown on and the year it looks back to, both required by Immich:

```json
{ "memory_at": "2026-09-03T00:00:00Z", "year": 2020, "asset_ids": ["e1b4b195-...", "14a743d4-..."] }
```

```json
{ "id": "9541723a-8989-4145-a0fe-dc99cdcb07d2", "type": "on_this_day",
  "memory_at": "2026-09-03T00:00:00.000Z", "year": 2020, "is_saved": false, "asset_count": 2,
  "assets": [ { "asset_id": "e1b4b195-...", "filename": "photo1.jpg", "date": "2026-03-01T12:01:00+00:00" },
              { "asset_id": "14a743d4-...", "filename": "photo2.jpg", "date": "2026-03-02T12:02:00+00:00" } ] }
```

`list_memories` returns the same rows under `{total, memories}`. `update_memory(memory_id, is_saved=true)` keeps one so Immich stops rotating it away, and `delete_memory` returns `{"success": true, "deleted": "<id>"}` with the photos untouched.

## 5. One thing that did not go smoothly

In the session above, the first `create_memory` was called with a bare `2026-09-03` and failed on Immich 3.1.0. Claude retried with `2026-09-03T00:00:00.000Z` and it worked, and it said so in its own report:

> One detail worth knowing: the first memory creation failed when given a bare date, and succeeded on retry with a full ISO timestamp. That looks like a plugin quirk rather than a problem with your library.

It read the situation correctly. 2.0.9 fixed exactly this for the search date filters, where Immich 3.x started validating full ISO 8601 and 2.7.5 had always accepted a bare date; the memory tools were not covered by that pass. 2.0.10 widens bare dates for memories too, the same fix in the same place.

## What leaves your network

Stacks and memories are rows in Immich, created and removed through its own API. The only images involved in the session above are the album thumbnails Claude looked at to decide which two photos were alike.

---

*The raw calls come from the published 2.0.9 package driven against Immich 2.7.5 and 3.1.0, the same lab as [`tests/live/`](../../tests/live/).*
