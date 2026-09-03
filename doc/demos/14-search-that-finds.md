# 🔎 Search that finds: OCR, people, places

Immich indexes more than dates and filenames. It reads the text printed inside a photo, it knows which faces belong to which person, and it ships a gazetteer of place names. `search_metadata` takes all of that as filters, in one call, and the model never has to look at an image to narrow things down. This page runs three real searches from one prompt in a Claude Code session against Immich 3.1.0, and shows the raw calls behind them from the 2.0.9 transcripts on both majors.

## 1. Three searches, one prompt

```
Three searches, tell me each result in one or two lines: (1) everything with Marie
Curie in it; (2) which of my photos contain the text 'boarding pass' and what else
the text says; (3) what place is at latitude 38.7223, longitude -9.1393, and check
the spelling of that place in the gazetteer.
```

Claude used `search_people`, `search_metadata(ocr=...)`, `search_smart`, `search_metadata(person_ids=...)`, `search_places`, `reverse_geocode`, `get_album` and finally `get_asset_image` to read the boarding pass with its own eyes. Its answer:

> All three searches are done against your Immich server (connected, version 3.1.0, OCR and smart search enabled).
>
> 1. **Marie Curie**: one person named Marie Curie exists, and she appears in exactly one asset, `curie.jpg` (taken 2026-03-06), which lives in the album "Famous People". No image in the library contains her name as printed text, and the CLIP search only surfaced other unrelated portraits, so that single photo is everything.
>
> 2. **"boarding pass" text**: one photo, `ocr-test.jpg` (dated 2026-06-01, no GPS or camera data), matches. I checked the image itself and the full text reads "BOARDING PASS / GATE B42".
>
> 3. **38.7223, -9.1393**: Immich's reverse geocoder resolves it to Lisbon, Lisbon district, Portugal. The gazetteer confirms the spelling "Lisbon" (English form, centred at 38.72509, -9.1498), and the coordinates you gave sit in the city centre between the Baixa and Graça entries, so the nearest neighbourhood is Baixa.

The photo in point 2 was uploaded for this demo and removed afterwards. The transcript run uploaded its own copy under the name `boarding-pass.jpg`.

## 2. The text inside the photo

```
Which of my photos contain the text "boarding pass"?
```

`search_metadata(ocr="boarding pass")` filters on the text Immich recognized inside the image, which is a different index from the filename and from the CLIP embedding. One hit on the lab:

```json
{ "total": 1, "page": 1, "assets": [ {
  "id": "2d9071a8-8041-4d9e-ae29-b39b44219578",
  "originalFileName": "boarding-pass.jpg",
  "localDateTime": "2026-06-01T09:00:00.000Z",
  "width": 1400, "height": 800, "..." } ] }
```

The filter needs OCR enabled on the server, which is what `get_capabilities` reports as `"ocr": true`. `search_smart` accepts the same `ocr` parameter, combined with the visual query.

## 3. A person, by id and not by name

Faces are addressed by id. `list_people` gives the ids, then `search_metadata(person_ids=[...])` returns only the assets showing all of them:

```json
{ "total": 4, "page": 1, "people": [
  { "id": "17490fb4-...", "name": "Abraham Lincoln", "isHidden": false, "..." },
  { "id": "2c5d3e53-...", "name": "Albert Einstein", "..." },
  { "id": "93fc1039-...", "name": "Marie Curie", "..." },
  { "id": "b8e138ce-...", "name": "Theodore Roosevelt", "..." } ] }
```

Searching for Abraham Lincoln's id returns three assets, one of them `lincoln1_dup.jpg`, which carries a `duplicateId`. One difference between the majors here: on Immich 3.x `list_people` hides people below a face-count threshold while still counting them in `total`, and `get_capabilities` says so in its quirks list.

## 4. Tags and albums as filters

`tag_ids` and `album_ids` take the same shape, from `list_tags` and `list_albums`. Restricting a search to one album is what "look only inside this album" means in practice:

```json
{ "album_ids": ["49933bd6-2041-48b6-8220-5ed5ad7bd2c2"] }
```

```json
{ "total": 5, "page": 1, "assets": [ { "id": "652d083f-...", "originalFileName": "photo4.jpg", "width": 1200, "height": 800, "..." }, "..." ] }
```

Filters combine, so `album_ids` plus `person_ids` plus `ocr` is one call, not three passes.

## 5. Places, and the spelling of a place

`search_places(name="Lisbon")` looks the name up in Immich's built-in gazetteer, which is how you check a spelling before using it as a filter. The answer holds 20 rows, and they are not all the same Lisbon:

```json
{ "total": 20, "places": [
  { "name": "Lisbon", "latitude": 38.72509, "longitude": -9.1498, "admin1name": "Lisbon", "admin2name": "Lisbon" },
  { "name": "Bairro Alto", "latitude": 38.7119, "longitude": -9.14411, "admin1name": "Lisbon", "..." },
  { "name": "Lisbon", "latitude": 41.92112, "longitude": -91.38545, "admin1name": "Iowa", "admin2name": "Linn County" },
  "..." ] }
```

`reverse_geocode` goes the other way, from a pair of coordinates to the names Immich itself would store on a photo taken there:

```json
{ "total": 1, "places": [ { "country": "Portugal", "state": "Lisbon", "city": "Lisbon" } ] }
```

## 6. A bare date works on both majors

`taken_after`, `created_after`, `file_created_after` and their siblings accept a plain `2019-07-14`. That used to be true on 2.7.5 only: Immich 3.1.0 validates full ISO 8601 and answered 400. Since 2.0.9 the client widens a bare date to midnight UTC, exactly how 2.x read it, so the same call now works on both.

## What leaves your network

The OCR text, the face clusters and the gazetteer all live on your Immich server, and these searches are plain reads against it. Only what the model quotes back reaches the Claude API. In the session above the single image that was actually downloaded is the boarding pass, because the prompt asked what the rest of the text said.

---

*The raw calls come from the published 2.0.9 package driven against Immich 2.7.5 and 3.1.0, the same lab as [`tests/live/`](../../tests/live/).*
