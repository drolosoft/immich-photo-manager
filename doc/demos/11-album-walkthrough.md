# 📷 Album Walkthrough: analyze an album item by item

> **"I have an album with a bunch of assets (image / video) and want to analyze them on a per-image basis."** Someone asked this in the Immich discussions, so I did it end to end, in plain English. Every prompt below was run as is, no edits, against Immich 2.7.5 and 3.1.0 with plugin 1.5.3. The answers matched on both, apart from the version string in step 0.

## The test album

I did not want to run this on my family library, so I made a small one. In my two Immich servers (2.7.5 and 3.1.0, both in Docker, the same setup that is in [`tests/live/`](../../tests/live/)) I created an album called *Famous People* with six items: public-domain portraits of Marie Curie, Theodore Roosevelt and Albert Einstein, two different copies of Abraham Lincoln's 1863 portrait, and one short video.

Immich's own face recognition ran on it before I started, so it already knew that the two Lincoln photos are the same person.

Use any album of yours instead. The prompts don't change, only the album name.

---

## 0. Know where you are

```
What Immich version am I connected to?
```
> Immich 3.1.0 at http://immich.local:2283

If that's the wrong server:
```
Update my Immich credentials to http://immich.local:2283 with API key <key>
```
The key is checked against that server before anything is switched. If it is wrong, you keep the previous connection.

## 1. Read the album, item by item

```
Go through my 'Famous People' album and tell me who is in each item
```
Claude reads the album (`get_album`) and looks at every picture (`get_album_images`):

| # | File | Who | Immich person |
|---|---|---|---|
| 1 | curie.jpg | Marie Curie, b/w portrait c. 1920 | detected, unnamed |
| 2 | roosevelt.jpg | Theodore Roosevelt, Pach Brothers studio portrait, 1904 | detected, unnamed |
| 3 | einstein.jpg | Albert Einstein, portrait from his last years | detected, unnamed |
| 4 | lincoln1.jpg | Abraham Lincoln, 1863 Gardner portrait, close crop | person A |
| 5 | lincoln2.jpg | Abraham Lincoln, same session, M.P. Rice copy | same person A |
| 6 | clip.mp4 | Video, read from its poster frame only | no faces |

A video gives you one frame: the plugin sends thumbnails, and for a video that is the poster frame, not the clip. Big albums are listed in full, but the pictures themselves go to the model 20 at a time (50 max per call), so on a few hundred assets ask for a quick pass first and a closer look only at the ones that matter.

Detail has a price too: the default is a 250px thumbnail, enough for "who and what is this" but not for reading text or small details. Ask for preview size (1440px) when that matters; it costs roughly twenty times the tokens per image.

Whatever you ask it to look at is sent to the model you use, so with a hosted model those thumbnails leave your network. The same MCP server works with a local model if you would rather nothing did, see the [LM Studio + Gemma demo](cc/lm-studio-gemma4-demo.txt).

## 2. Who repeats?

```
Which photos in Famous People show the same person?
```
> lincoln1.jpg and lincoln2.jpg, both faces belong to the same person.

This comes straight from the album listing: since 1.5.3 `get_album` returns the recognized people per asset, so no extra calls are needed.

## 3. Duplicates (same picture, not same person)

```
Which photos in Famous People are duplicates?
```
> lincoln1.jpg has a duplicate (a resized, recompressed copy) stored in the library but not in this album. No two photos inside the album are duplicates of each other.

`get_duplicates(album_id)` filters Immich's ML duplicate groups to the album and says which assets of each group are inside or outside it.

"Duplicate" means the same picture. The two Lincoln photos are the same person, not duplicates; that is step 2.

## 4. Make a new album from it

```
Create an album called 'Presidents' with only the US presidents from Famous People
```
> Album "Presidents" created with 3 assets: roosevelt.jpg, lincoln1.jpg, lincoln2.jpg.

Claude picks the assets from what it saw in step 1 and checks by re-reading the new album.

## 5. Write it back: tags + descriptions

```
Tag every photo in Presidents with "president" and set a one-line description on each
```
> Tag "president" created; applied to 3 photos; descriptions set:
> - roosevelt.jpg: Theodore Roosevelt, 26th US president, Pach Brothers studio portrait (1904).
> - lincoln1.jpg: Abraham Lincoln, 16th US president, Alexander Gardner portrait, November 1863.
> - lincoln2.jpg: Abraham Lincoln, 16th US president, November 1863 session, M.P. Rice copy (1900).

Check it in the Immich web app: open a photo, then the ⓘ info panel shows the description and the tag. If you don't see a Tags section, enable it once in Account Settings, Features, Tags. It is off by default on new accounts.

## 6. Optional: name the people

```
Name the person who appears in lincoln1.jpg "Abraham Lincoln"
```
From then on, step 1 answers with names instead of "unnamed".

---

### Tools involved

`get_server_version`, `get_connection_info`, `update_credentials`, `list_albums`, `get_album`, `get_album_images`, `get_duplicates`, `create_album`, `list_tags`, `create_tag`, `tag_assets`, `update_asset_metadata`, `get_asset_info`, `update_person`.

### Version note

Immich 3.0 changed how album contents are read, and plugin versions before 1.5.1 see an empty album on 3.x. Use 1.5.3 or later; it is tested against both 2.7 and 3.1.
