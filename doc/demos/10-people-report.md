# 👤 People Report

> **Who appears in your library? How many untagged faces? Which photos are group shots?** A complete face detection summary.

Immich runs face detection automatically. The plugin gives you a structured report of who appears, how often, and what needs attention.

---

## Step 1: Gather face data

```
search_metadata(size=200, page=1)
search_metadata(size=200, page=2)
...
```

For each photo, Claude reads the `people` and `unassignedFaces` fields:

```
get_asset_info(asset_id="...")
→ people: [{ name: "Sam", id: "..." }]
   unassignedFaces: [{ id: "face-uuid-1" }, { id: "face-uuid-2" }]
```

## Step 2: Build the report

```
PEOPLE REPORT
═════════════

👤 NAMED PEOPLE (faces you've tagged in Immich)
   Sam:          4,521 photos  (most frequent)
   María:         2,103 photos
   Carlos:          891 photos
   Ana:             634 photos
   ... 12 more people

📊 STATISTICS
   Photos with faces:    18,234 (42.9%)
   Photos without faces: 24,277 (57.1%)
   Named faces:          14,892
   Untagged faces:        8,341  ⚠️ needs attention
   Group photos (3+):     2,456

🔍 UNTAGGED FACE CLUSTERS
   Cluster A: 342 photos — same unknown person, appears frequently
   Cluster B: 128 photos — same unknown person
   Cluster C:  89 photos — same unknown person
   → Open Immich → People → assign names to these clusters

📅 PEOPLE OVER TIME
   2024: Sam (892), María (445), Carlos (201)
   2025: Sam (1,834), María (923), Ana (412)
   2026: Sam (1,795), María (735), Carlos (690)
```

## Step 3: Actionable next steps

```
RECOMMENDATIONS
═══════════════

1. Tag 8,341 untagged faces — 3 large clusters detected
   → Open Immich People section to assign names

2. Review 2,456 group photos — potential album candidates
   → "Create a 'Group Photos' album?" [Yes / No]

3. Sam appears in 4,521 photos — consider a dedicated album
   → "Create albums per person?" [Yes / No]
```

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `search_metadata` | Paginate through library | paginated |
| `get_asset_info` | Read face data per asset | sampled |
| `create_album` | Create per-person or group albums | optional |
| `get_thumbnails_batch` | Visual preview of face clusters | optional |

## What Immich provides vs. what the plugin adds

| | Immich | + Plugin |
|---|---|---|
| Face detection | ✅ Automatic | — |
| Face clustering | ✅ Groups similar faces | — |
| Face naming | ✅ Manual in UI | — |
| **People report** | ❌ | ✅ Statistics, trends, recommendations |
| **Untagged face alerts** | ❌ | ✅ Highlights clusters that need naming |
| **Per-person albums** | ❌ Manual | ✅ Automatic creation |
| **Group photo detection** | ❌ | ✅ Photos with 3+ faces |
