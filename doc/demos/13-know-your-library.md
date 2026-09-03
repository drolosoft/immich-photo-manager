# 🧭 Know a library before searching it

A library nobody has described yet is a bad place to start guessing. Before any search there is a set of calls that answer "what is in here": what the server can do, which places show up, which months hold photos, which cameras took them. This page runs that tour twice. Once as a real Claude Code session against Immich 3.1.0, where Claude picked the tools on its own from one prompt, and once as the raw call transcripts of the published 2.0.9 package against Immich 2.7.5 and 3.1.0, the same lab that lives in [`tests/live/`](../../tests/live/).

## 1. The whole tour in one prompt

```
I just connected you to my Immich and I know nothing about this library. Give me a
quick tour: what this server can do, which places appear in the photos, how many
photos per camera make, what months hold photos, and a random sample of three
filenames. Keep it under 15 lines.
```

Nothing named a tool. Claude chose these, in this order: `ping`, `get_capabilities`, `search_cities`, `search_suggestions(suggestion_type="camera-make")`, `get_timeline_buckets(order="asc")`, `search_random(size=3)`, and then `search_statistics` once per camera make it had just learned about. Eight calls, no photo downloaded. Its answer:

> Immich is connected and healthy. Here is the tour of a small library of 16 photos.
>
> **Server:** Immich 3.1.0 with smart (CLIP) search, face recognition, OCR, duplicate detection, map and reverse geocoding all enabled. Trash is on, OAuth is off.
>
> **Places:** Lisbon, Sintra and Senhora do Porto in Portugal, plus New York City. The other photos have no GPS.
>
> **Photos per camera make:**
>
> | Make | Photos |
> |------|--------|
> | DemoCam | 5 |
> | LabCam | 4 |
> | No make recorded | 7 |
>
> **Months with photos:** March 2026 holds 11 and May 2026 holds 5. Nothing else.
>
> **Random sample:** `roosevelt.jpg`, `einstein.jpg`, `photo4.jpg`.

## 2. What this server can do

`get_capabilities` is the first call because everything after it depends on the answer. It returns Immich's own feature flags plus a list of quirks in plain sentences:

```json
{
  "server_version": "3.1.0",
  "immich_major": 3,
  "features": { "smartSearch": true, "facialRecognition": true, "ocr": true, "map": true, "trash": true, "oauth": false, "..." },
  "quirks": [
    "The edits API (rotate_assets, revert_asset_edits) applies to images only.",
    "Videos expose a single thumbnail; use get_video_frames for more moments.",
    "list_people hides people below a face-count threshold; the total still counts them."
  ]
}
```

On 2.7.5 the same call reports `"immich_major": 2` and a different quirk list, including that searching by asset ids is ignored there, so the plugin fetches each asset one by one.

## 3. Which places appear

Two tools answer this. `search_explore` is Immich's own Explore page, one representative asset per city and per detected concept, and it has Immich's five-assets-per-city threshold, so a city with four photos simply does not appear. On the lab it returns a single city:

```json
{ "total": 2, "fields": [ { "field": "exifInfo.city", "items": [ { "value": "Sintra", "asset_id": "d39681a2-..." } ] }, { "field": "createdAt", "items": [ "..." ] } ] }
```

Here `total` counts the fields that came back, not the cities. That `createdAt` field is 3.x only; on 2.7.5 the same call returns `"total": 1` with the city field alone. `search_cities` has no threshold, which makes it the reliable one on a small library:

```json
{ "total": 4, "cities": [
  { "city": "Lisbon", "country": "Portugal", "asset_id": "e1b4b195-...", "date": "2026-03-01T12:01:00.000Z" },
  { "city": "New York City", "country": "United States of America", "..." },
  { "city": "Senhora do Porto", "country": "Portugal", "..." },
  { "city": "Sintra", "country": "Portugal", "..." } ] }
```

`search_suggestions` gives the exact strings the library holds for one field, so a later filter is never guessed. Asked for cities it answers `["Lisbon", "New York City", "Senhora do Porto", "Sintra"]`; asked for `camera-make` it is what fed the table above.

## 4. Counting without listing

`search_statistics(make="LabCam")` returns `{"total": 4}` and nothing else. No asset rows, no thumbnails, no tokens spent on data the user did not ask for. It is the right call for "how many" questions, and it takes the same filters as a search.

## 5. A random handful

`search_random(size=3)` returns three assets picked at random, full metadata each. Claude used it for the "three filenames" part of the prompt and read only `originalFileName` out of each. On a big album it is the cheapest way to see whether the metadata looks sane.

## 6. What months, what days

`get_timeline_buckets` is the month index of the library:

```json
{ "total_buckets": 2, "buckets": [ { "timeBucket": "2026-05-01", "count": 5 }, { "timeBucket": "2026-03-01", "count": 11 } ] }
```

`get_timeline_bucket("2026-05-01")` opens one month into trimmed rows (`asset_id`, `date`, `is_image`, `is_favorite`, `duration`, `city`, `country`), which is enough to decide what to look at without fetching a single image.

`get_calendar_heatmap` goes down to the day, and only days with activity appear in the series. A day missing from the list had nothing:

```json
{ "source": "immich", "total": 16, "series": [
  { "date": "2026-03-01", "count": 2 }, { "date": "2026-03-05", "count": 4 }, "...",
  { "date": "2026-05-11", "count": 2 }, { "date": "2026-05-13", "count": 1 } ] }
```

The `source` key says where the numbers came from: `"immich"` on 3.x, which answers natively, and `"timeline"` on 2.7.5, where the plugin builds the same shape from the timeline buckets. The two lab servers do not hold exactly the same assets, so the 2.7.5 run reports `"total": 17` for the same range.

## What leaves your network

Every call on this page is a read against your own Immich, and none of them fetches an image. What reaches the Claude API is the small JSON each tool returns, and the tour above cost eight of those.

---

*The raw transcripts behind sections 2 to 6 come from the published 2.0.9 package driven against Immich 2.7.5 and 3.1.0, the same lab as [`tests/live/`](../../tests/live/).*
