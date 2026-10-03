---
name: create-album
description: Create a geographic album from a location
argument-hint: <location> [--share]
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

Create an Immich album for the location specified in $ARGUMENTS.

Follow the album-manager skill workflow:

1. Parse the location from $ARGUMENTS (e.g., "Rome, Italy" or "Lanzarote")
2. Search for photos at that location using GPS coordinates and CLIP semantic search
3. Report how many photos were found
4. Filter out screenshots and obvious non-travel photos
5. Create the album with the naming convention: [Country emoji] Place, Country
6. Add the curated photos
7. If --share flag is present, create a shared link for Gallery publication

Report the result:
```
✅ Created: 🇮🇹 Roma, Italia
   Photos: 47 selected from 203 found
   Date range: Jun 2023
   Shared: Yes — visible on Gallery
```
