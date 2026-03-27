const express = require("express");
const nodeHtmlToImage = require("node-html-to-image");
const cors = require("cors");
const { v4: uuidv4 } = require("uuid");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const API_KEY = process.env.API_KEY || "";
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

const STORAGE_DIR = path.join(__dirname, "images");
if (!fs.existsSync(STORAGE_DIR)) {
  fs.mkdirSync(STORAGE_DIR, { recursive: true });
}

app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// ─────────────────────────────────────────────
// Shared Puppeteer config for Render / Docker
// ─────────────────────────────────────────────
const PUPPETEER_CONFIG = {
  headless: "new",
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
  args: [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--single-process",
    "--no-zygote",
  ],
  protocolTimeout: 60000,
  timeout: 60000,
};

// ─────────────────────────────────────────────
// Auth middleware (optional)
// ─────────────────────────────────────────────
function authenticate(req, res, next) {
  if (!API_KEY) return next();
  const authHeader = req.headers.authorization;
  if (!authHeader) return res.status(401).json({ error: "Missing Authorization header" });

  if (authHeader.startsWith("Bearer ")) {
    if (authHeader.slice(7) !== API_KEY) return res.status(403).json({ error: "Invalid API key" });
  } else if (authHeader.startsWith("Basic ")) {
    const decoded = Buffer.from(authHeader.slice(6), "base64").toString();
    if (!decoded.includes(API_KEY)) return res.status(403).json({ error: "Invalid API key" });
  } else {
    return res.status(401).json({ error: "Invalid auth format" });
  }
  next();
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────
function buildFullHtml({ html, css, google_fonts }) {
  let fullHtml = html;
  if (google_fonts) {
    const fontLink = `<link href="https://fonts.googleapis.com/css2?family=${encodeURIComponent(google_fonts)}&display=swap" rel="stylesheet">`;
    if (fullHtml.includes("<head>")) {
      fullHtml = fullHtml.replace("<head>", `<head>${fontLink}`);
    } else if (fullHtml.includes("<html")) {
      fullHtml = fullHtml.replace(/<html[^>]*>/, `$&<head>${fontLink}</head>`);
    } else {
      fullHtml = `<html><head>${fontLink}</head><body>${fullHtml}</body></html>`;
    }
  }
  if (css) {
    const styleTag = `<style>${css}</style>`;
    if (fullHtml.includes("</head>")) {
      fullHtml = fullHtml.replace("</head>", `${styleTag}</head>`);
    } else {
      fullHtml = `<style>${css}</style>${fullHtml}`;
    }
  }
  if (!fullHtml.includes("<html")) {
    fullHtml = `<html><head><meta charset="UTF-8"></head><body>${fullHtml}</body></html>`;
  }
  return fullHtml;
}

function buildOptions(body, extraOpts = {}) {
  const { viewport_width, viewport_height, device_scale, transparent } = body;
  const options = {
    html: buildFullHtml(body),
    puppeteerArgs: PUPPETEER_CONFIG,
    transparent: transparent === true || transparent === "true",
    ...extraOpts,
  };
  const vw = parseInt(viewport_width) || null;
  const vh = parseInt(viewport_height) || null;
  const ds = parseFloat(device_scale) || null;
  if (vw || vh || ds) {
    options.viewport = { width: vw || 1080, height: vh || 1080 };
    if (ds) options.viewport.deviceScaleFactor = ds;
  }
  return options;
}

// ─────────────────────────────────────────────
// POST /v1/image — Generate image, get URL
// ─────────────────────────────────────────────
app.post("/v1/image", authenticate, async (req, res) => {
  try {
    const { html } = req.body;
    if (!html) return res.status(400).json({ error: "Missing 'html' parameter" });

    const imageId = uuidv4();
    const filename = `${imageId}.png`;
    const filepath = path.join(STORAGE_DIR, filename);
    const options = buildOptions(req.body, { output: filepath });

    await nodeHtmlToImage(options);

    res.status(200).json({
      url: `${BASE_URL}/images/${filename}`,
      id: imageId,
    });
  } catch (error) {
    console.error("Image generation error:", error);
    res.status(500).json({ error: "Failed to generate image", message: error.message });
  }
});

// ─────────────────────────────────────────────
// POST /v1/image/base64 — Return image as base64
// ─────────────────────────────────────────────
app.post("/v1/image/base64", authenticate, async (req, res) => {
  try {
    const { html } = req.body;
    if (!html) return res.status(400).json({ error: "Missing 'html' parameter" });

    const options = buildOptions(req.body, { encoding: "base64" });
    const base64 = await nodeHtmlToImage(options);

    res.status(200).json({ base64, content_type: "image/png" });
  } catch (error) {
    console.error("Image generation error:", error);
    res.status(500).json({ error: "Failed to generate image", message: error.message });
  }
});

// Serve images
app.use("/images", express.static(STORAGE_DIR));

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

// Cleanup old images every 30 min
setInterval(() => {
  const cutoff = Date.now() - 60 * 60 * 1000;
  fs.readdirSync(STORAGE_DIR).forEach((file) => {
    const fp = path.join(STORAGE_DIR, file);
    const stat = fs.statSync(fp);
    if (stat.mtimeMs < cutoff) fs.unlinkSync(fp);
  });
}, 30 * 60 * 1000);

// Start
app.listen(PORT, () => {
  console.log(`\n🖼️  HTML-to-Image API running on port ${PORT}`);
  console.log(`   Chromium: ${PUPPETEER_CONFIG.executablePath}`);
  console.log(`   POST ${BASE_URL}/v1/image`);
  console.log(`   POST ${BASE_URL}/v1/image/base64`);
  console.log(`   GET  ${BASE_URL}/health\n`);
  if (!API_KEY) console.log("   ⚠️  No API_KEY set — running without authentication\n");
});
