# CORS Setup Guide (Optional)

Enable Cross-Origin Resource Sharing on your Immich reverse proxy for faster, lighter gallery files when viewed outside Cowork.

---

## Why Enable CORS?

By default, the plugin embeds photo thumbnails as base64 data directly inside gallery HTML files. This works everywhere, including inside the Cowork sandbox, but limits galleries to ~50 photos (~1.2 MB per file).

With CORS enabled, galleries opened in a **regular browser** (outside Cowork) can load thumbnails directly from your Immich server on demand. This means:

- Gallery files drop from ~1.2 MB to ~15 KB regardless of photo count
- All photos in an album load (not just the first 50)
- Thumbnails load on demand with lazy loading and pagination

**Important:** CORS does **not** help inside the Cowork viewer, which runs in an `about:` protocol sandbox that blocks all external requests. Base64 embedding remains the only option there.

---

## What Changes

| | Without CORS | With CORS (browser only) |
|---|---|---|
| Gallery file size (273 photos) | ~1.2 MB (50 photos max) | ~15 KB (all photos) |
| Works in Cowork | Yes | No |
| Works in browser | Yes | Yes |
| Requires server config | No | Yes |
| Photo limit per gallery | ~50 | Unlimited |

---

## Setup by Reverse Proxy

### Nginx

Add these lines **inside the `location /` block** that proxies to Immich:

```nginx
# CORS for immich-photo-manager gallery viewer
add_header 'Access-Control-Allow-Origin' '*' always;
add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
add_header 'Access-Control-Allow-Headers' 'x-api-key, Content-Type' always;

if ($request_method = 'OPTIONS') {
    add_header 'Access-Control-Allow-Origin' '*';
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS';
    add_header 'Access-Control-Allow-Headers' 'x-api-key, Content-Type';
    add_header 'Access-Control-Max-Age' 86400;
    return 204;
}
```

Then test and reload:

```bash
sudo nginx -t && sudo nginx -s reload
```

### Caddy

Add a `header` block to the Immich site:

```caddy
photos.example.com {
    header {
        Access-Control-Allow-Origin *
        Access-Control-Allow-Methods "GET, OPTIONS"
        Access-Control-Allow-Headers "x-api-key, Content-Type"
    }
    reverse_proxy localhost:2283
}
```

Then reload: `caddy reload`

### Traefik

Add CORS middleware via labels (Docker) or file provider:

```yaml
# Docker labels
- "traefik.http.middlewares.immich-cors.headers.accessControlAllowOriginList=*"
- "traefik.http.middlewares.immich-cors.headers.accessControlAllowMethods=GET,OPTIONS"
- "traefik.http.middlewares.immich-cors.headers.accessControlAllowHeaders=x-api-key,Content-Type"
```

### No Reverse Proxy

If you access Immich directly on its port (e.g., `http://192.168.1.100:2283`), Immich does not have built-in CORS configuration. You would need to set up a lightweight reverse proxy (Nginx, Caddy) in front of it.

---

## Verifying CORS

Test with curl:

```bash
# Preflight (OPTIONS)
curl -sI -X OPTIONS \
  -H "Origin: http://localhost" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: x-api-key" \
  https://your-immich-server.com/api/server/ping

# Regular GET
curl -sI -H "Origin: http://localhost" \
  https://your-immich-server.com/api/server/ping
```

Both should return:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: x-api-key, Content-Type
```

---

## Security Note

Using `Access-Control-Allow-Origin: *` allows any website to make requests to your Immich API **if they have your API key**. For a self-hosted instance on a private network, this is generally acceptable. For a publicly exposed instance, you may prefer to restrict the origin to `null` (which allows `file://` and `about:` origins used by local HTML viewers).

---

## After Enabling CORS

No plugin changes needed. The gallery viewer is designed to work with base64 by default. CORS gives a better experience when viewing galleries in a regular browser.
