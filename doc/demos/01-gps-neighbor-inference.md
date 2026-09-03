# GPS Neighbor Inference: Step by Step

How the plugin detects missing GPS and infers coordinates from neighboring photos. This is a real session using the MCP tools on a live Immich library.

---

## Step 1: Scan the day

Two MCP calls in parallel. One gets all GPS markers, the other gets all photos:

```
get_map_markers(file_created_after="2026-01-02", file_created_before="2026-01-03")
→ 14 photos with GPS

search_metadata(taken_after="2026-01-02", taken_before="2026-01-03", size=200)
→ 20 photos total
```

**Result:** 6 photos have no GPS on a day where 14 others do.

## Step 2: Identify the target

```
get_asset_info(asset_id="64d2a726-...")
```

```
File:      Screenshot_20260102_224330_Edge.jpg
Date:      2026-01-02 22:43
GPS:       null
Camera:    null (screenshot)
```

No coordinates. Taken at 22:43.

## Step 3: Find the nearest neighbor with GPS

From the map markers on the same day, the closest photo by timestamp:

```
get_asset_info(asset_id="b77bb7a8-...")
```

```
File:      20260102_212804.jpg
Date:      2026-01-02 21:28
GPS:       28.958244, -13.55575
City:      Arrecife, Canary Islands
Camera:    Samsung Galaxy S24
```

**Time gap: 1 hour 15 minutes, within the 2-hour window.**

## Step 4: Propose the fix (nothing written yet)

Claude presents the finding before writing anything:

```
METADATA FIX PROPOSAL
══════════════════════

Target:   Screenshot_20260102_224330_Edge.jpg
          2026-01-02 22:43 - NO GPS

Neighbor: 20260102_212804.jpg
          2026-01-02 21:28 - Arrecife (28.9582, -13.5558)
          Gap: 1h 15m - SAFE TO INFER

Proposed: Copy GPS → latitude 28.958244, longitude -13.55575

Apply? [Yes / No]
```

## Step 5: Write the fix

User approves. One MCP call:

```
update_asset_metadata(
    asset_id="64d2a726-...",
    latitude=28.958244,
    longitude=-13.55575
)
```

## Step 6: Verify

```
get_asset_info(asset_id="64d2a726-...")
```

```
File:      Screenshot_20260102_224330_Edge.jpg
GPS:       28.958244, -13.55575
City:      Arrecife
State:     Canary Islands
Country:   Spain
Timezone:  Atlantic/Canary
```

Immich resolved the city and timezone automatically from the coordinates.

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `get_map_markers` | Find all photos with GPS on the day | 1 |
| `search_metadata` | Find all photos on the day | 1 |
| `get_asset_info` | Read metadata for target + neighbor | 2 |
| `update_asset_metadata` | Write GPS to the target | 1 |
| `get_asset_info` | Verify the fix | 1 |
| **Total** | | **6** |

## Safety rules

- Gap must be **under 2 hours**: if the gap is larger, the user may have traveled
- Claude **shows the proposal before writing**: nothing is modified without approval
- The original values are logged so fixes can be reverted
- Photos in bursts (< 5 seconds apart) always share GPS
