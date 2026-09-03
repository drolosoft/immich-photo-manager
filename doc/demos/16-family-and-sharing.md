# 👨‍👩‍👦 Partners, comments and the album as a zip

Immich has a family side that rarely gets driven from a chat: partner sharing, where two accounts see each other's libraries while each keeps its own; album activities, the comments and likes people leave on a shared album; and the download endpoint that packs an album into a zip. This page runs all three in order from one prompt in a real Claude Code session against Immich 3.1.0, with the raw calls from the 2.0.9 transcripts underneath.

## 1. Everything in one prompt

```
Do these in order and report each in one line: list the users on this server; share my
library with the partner user (Lab Partner); show me who I share with; stop sharing
with them; post the comment 'Great set!' on the Lab Album, list the album's comments,
then delete that comment; tell me how big a zip of the Lab Album would be, download it
to <path>/lab-album.zip, and tell me how many files it holds.
```

Ten steps, ten tools, and Claude re-read the server after each change instead of trusting its own writes:

> All steps done and re-read from the server, except the local zip inspection, which the shell declined twice.
>
> 1. **Users on the server:** two, Lab Partner (partner@example.com) and Lab (lab@example.com).
> 2. **Shared with Lab Partner:** done, partner entry created with the library not in their timeline.
> 3. **Who I share with:** Lab Partner, and they also share their library back with me, shown in my timeline.
> 4. **Stopped sharing:** done, and a re-read shows nobody in my shared-by-me list anymore. Their share to me is untouched.
> 5. **Comment posted:** "Great set!" on the Lab Album by user Lab.
> 6. **Album comments:** one comment, the one just posted.
> 7. **Comment deleted:** done, the album now lists zero activities.
> 8. **Zip size estimate:** 0.11 MB for 5 assets in a single archive.
> 9. **Download:** written to the requested path, 113,987 bytes, 5 assets.
> 10. **Files in the zip:** 5 per the download result. Pending to verify by opening the file locally, since both attempts to run a shell command on it were declined.

Point 10 is worth keeping in view: the sandbox refused the shell command that would have opened the zip, so Claude reported the count from the tool's own answer and said the local check was still pending rather than claiming it had looked inside.

## 2. Sharing is addressed by user id

Everything in this area takes a user id, never a name or an email, so `list_users` comes first:

```json
{ "total": 2, "users": [
  { "id": "435674fe-8154-4fbc-908b-d457ce492d08", "name": "Lab Partner", "email": "partner@example.com" },
  { "id": "387e5d40-e195-499c-ba5c-96c10cc40fed", "name": "Lab", "email": "lab@example.com" } ] }
```

`create_partner(user_id)` shares this account's whole library with that user and answers `{"id": "435674fe-...", "in_timeline": false}`. `list_partners` asks Immich in both directions in one call, which is the view that actually answers "who can see what":

```json
{ "shared_with_me": [ { "id": "435674fe-...", "name": "Lab Partner", "email": "partner@example.com", "in_timeline": true } ],
  "shared_by_me":   [ { "id": "435674fe-...", "name": "Lab Partner", "email": "partner@example.com", "in_timeline": false } ] }
```

`update_partner(user_id, in_timeline)` decides whether a partner's photos are mixed into this timeline or kept separate. It only works on someone in `shared_with_me`, because the flag controls how their photos appear here; calling it on a `shared_by_me` partner is rejected by Immich. `remove_partner(user_id)` revokes the share and returns `{"success": true, "removed": "<user id>"}`, and the other side's share is untouched, which is exactly what the re-read in step 4 above confirmed.

## 3. Talking about an album

`create_activity(album_id, comment)` posts a comment, or `like=true` posts a like, and `asset_id` attaches either to one photo instead of the whole album. In the transcript run the comment text was different from the session's:

```json
{ "total": 1, "activities": [ {
  "id": "b5f2fa48-a235-432a-bbde-a315663b92ec",
  "type": "comment",
  "comment": "Let us print this one for the wall",
  "asset_id": null,
  "user": "Lab",
  "created_at": "2026-09-03T08:26:45.000Z" } ] }
```

`delete_activity(activity_id)` removes it for everyone.

## 4. The album as a zip, size first

Two tools, in this order, because originals and videos add up fast and telling the user "this is 14 GB" before starting is the whole point of the first one:

```json
{ "total_size_mb": 0.11, "asset_count": 5, "archives": 1 }
```

`archives` is how many separate zips Immich would split the download into. Then `download_archive(album_id, output_path)`:

```json
{ "path": ".../lab-album-v3.zip", "bytes": 113987, "assets": 5 }
```

The file is streamed to disk rather than held in memory, which is what makes a large album safe, and it is written to a `.part` file that is renamed on success, so a failed download never leaves a corrupt zip in the way of the retry. An existing file is never overwritten: the call refuses and asks for another path. The saved zip on disk is 111 KB and opens with five files inside: `clip.mp4`, `photo1.jpg`, `photo2.jpg`, `photo3.jpg`, `photo4.jpg`.

## What leaves your network

Partners, comments and downloads are all Immich's own endpoints, called from the machine running the plugin. The zip lands on that machine's disk and never enters the conversation, so what reaches the Claude API is three numbers: the size estimate, the byte count and the asset count.

---

*The raw calls come from the published 2.0.9 package driven against Immich 2.7.5 and 3.1.0, the same lab as [`tests/live/`](../../tests/live/).*
