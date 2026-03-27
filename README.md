# 🖼️ HTML-to-Image API

Free, self-hosted HTML/CSS to Image API — drop-in replacement for [htmlcsstoimage.com](https://htmlcsstoimage.com) (HCTI).

Built with `node-html-to-image` + Express. Deploy on Render, Railway, or any Docker host.

---

## Features

- **HCTI-compatible** `/v1/image` endpoint — minimal n8n workflow changes
- **Base64 endpoint** `/v1/image/base64` — get images directly without URL storage
- Google Fonts support
- Separate CSS injection
- Viewport & device scale configuration
- Optional API key authentication
- Auto-cleanup of generated images (1 hour TTL)
- Docker-ready with all Chromium dependencies

---

## API Reference

### `POST /v1/image` — Generate image, get URL

**Request body (JSON):**

| Field | Required | Description |
|---|---|---|
| `html` | ✅ | HTML content to render |
| `css` | ❌ | CSS to inject (added as `<style>` tag) |
| `google_fonts` | ❌ | Google Font family name (e.g. `"Inter:wght@400;700"`) |
| `viewport_width` | ❌ | Viewport width in px (default: 1080) |
| `viewport_height` | ❌ | Viewport height in px (default: 1080) |
| `device_scale` | ❌ | Device scale factor (default: 2 for retina) |
| `transparent` | ❌ | Transparent background (default: false) |

**Response:**

```json
{
  "url": "https://your-api.onrender.com/images/abc-123.png",
  "id": "abc-123"
}
```

### `POST /v1/image/base64` — Generate image, get base64

Same request body. Response:

```json
{
  "base64": "iVBORw0KGgo...",
  "content_type": "image/png"
}
```

### `GET /health` — Health check

```json
{ "status": "ok", "uptime": 12345 }
```

---

## Deployment

### Option A: Render.com (recommended — free tier)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your GitHub repo
4. Render detects the `Dockerfile` automatically
5. Set environment variables:
   - `API_KEY` — your secret key (or leave empty for open access)
   - `BASE_URL` — your Render URL, e.g. `https://html-to-image-api.onrender.com`
6. Choose **Free** plan → Deploy

> ⚠️ Free tier spins down after 15 min of inactivity (first request takes ~30s to cold-start). Upgrade to Starter ($7/mo) if you need always-on.

### Option B: Railway.app

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Add env vars: `API_KEY`, `BASE_URL` (Railway gives you a URL like `https://your-app.up.railway.app`)
4. Deploy

### Option C: Any VPS with Docker

```bash
# Clone and build
git clone https://github.com/YOUR_USER/html-to-image-api.git
cd html-to-image-api

# Run with Docker
docker build -t html-to-image-api .
docker run -d \
  -p 3000:3000 \
  -e API_KEY=your-secret-key \
  -e BASE_URL=https://your-domain.com \
  --name html-to-image \
  html-to-image-api
```

---

## n8n Integration

### Replacing HCTI in your carousel workflow

In your n8n HTTP Request node, change:

| Setting | HCTI (old) | This API (new) |
|---|---|---|
| **URL** | `https://hcti.io/v1/image` | `https://your-api.onrender.com/v1/image` |
| **Auth** | Basic Auth (UserID:APIKey) | Bearer Token or Basic Auth |
| **Body** | Same | Same — `html`, `css`, `google_fonts` all work |

**Example n8n HTTP Request node config:**

```
Method: POST
URL: https://your-api.onrender.com/v1/image
Authentication: Header Auth
  Name: Authorization
  Value: Bearer YOUR_API_KEY
Body (JSON):
{
  "html": "{{ $json.slideHtml }}",
  "css": "{{ $json.slideCss }}",
  "google_fonts": "Inter:wght@400;600;700",
  "viewport_width": 1080,
  "viewport_height": 1080,
  "device_scale": 2
}
```

The response gives you `{{ $json.url }}` — same as HCTI.

### Using base64 instead (no image hosting needed)

If you want to skip the URL and get the image directly:

```
URL: https://your-api.onrender.com/v1/image/base64
```

Response: `{{ $json.base64 }}` — use this in a "Convert to File" node in n8n.

---

## Local Development

```bash
npm install
npm run dev
# Server starts at http://localhost:3000
```

Test it:

```bash
curl -X POST http://localhost:3000/v1/image \
  -H "Content-Type: application/json" \
  -d '{"html": "<div style=\"padding:40px;background:#4f46e5;color:white;font-size:32px;font-family:sans-serif;\">Hello World!</div>"}'
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | Server port |
| `API_KEY` | _(none)_ | Set to require authentication. Leave empty for open access |
| `BASE_URL` | `http://localhost:3000` | Public URL for image links in responses |

---

## License

MIT — use it however you want.
