---
name: my-travels
description: Discover all travel destinations in your photo library
allowed-tools: ["mcp__plugin_immich-photo-manager_immich__*"]
---

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server configured (see **/setup-immich-photo-manager**)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Analyze the Immich library to discover all geographic locations where photos were taken.

1. Search for all assets that have GPS data
2. Cluster by location (group photos within 30km of each other)
3. Identify the city/region/country for each cluster
4. Count photos per cluster
5. Sort by photo count (most photos first)

Present as a travel map:

```
🗺️ Your Travel Destinations
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Found photos from {count} distinct locations across {countries} countries.

🇮🇹 Italy
   📍 Roma — {count} photos ({date_range})
   📍 Cinque Terre — {count} photos ({date_range})
   📍 Venezia — {count} photos ({date_range})

🇪🇬 Egypt
   📍 Cairo & Luxor — {count} photos ({date_range})

🇲🇽 Mexico
   📍 Oaxaca — {count} photos ({date_range})

[... more destinations ...]

📊 {no_gps_count} photos have no GPS data ({percentage}%)

Want me to create albums for these destinations?
```

After presenting, offer to create geographic albums using the album-manager skill.
