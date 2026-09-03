# Live tests: every tool against real Immich servers

The unit suite (`pytest`, runs in CI) mocks HTTP. This kit does the opposite: it starts real Immich servers in Docker, fills them with a small library, and drives **every MCP tool over the real MCP protocol**, re-reading state after each write to confirm the effect. It is how v1.5.1 to v1.5.3 were verified against Immich **2.7.5** and **3.1.0** (2026-08-25).

Requirements: Docker, `magick` (ImageMagick), `ffmpeg`, `exiftool`, `uv` or a venv with the package installed.

```sh
cd tests/live
./make-media.sh                                     # synthetic photos + video + 3 public-domain portraits

docker compose -p immich275 -f docker-compose.immich-2.7.5.yml up -d
docker compose -p immich310 -f docker-compose.immich-3.1.0.yml up -d
# wait until http://127.0.0.1:12283/api/server/ping and :13283 answer

python bootstrap.py http://127.0.0.1:12283 ./media > creds-2.7.5.json
python bootstrap.py http://127.0.0.1:13283 ./media > creds-3.1.0.json
# give the ML jobs a minute (smart search, faces, duplicates)

python mcp_harness.py creds-2.7.5.json v2 "$(which immich-photo-manager)" ./media
python mcp_harness.py creds-3.1.0.json v3 "$(which immich-photo-manager)" ./media
```

Each run prints one line per check and a summary such as `SUMMARY v3: 123/123 checks passed; tools not covered: []` (last full run 2026-09-03). Anything the harness could not exercise is listed, never silently skipped. Faces need at least two recognized people; if a run reports `SKIPPED` for `merge_people`/`reassign_face`, trigger facial recognition in Immich (Administration → Jobs) and rerun.

Tear down with `docker compose -p immich275 -f docker-compose.immich-2.7.5.yml down -v` (same for 3.1.0).
