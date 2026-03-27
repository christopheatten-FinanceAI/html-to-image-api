const express = require("express");
const puppeteer = require("puppeteer");
const cors = require("cors");
const { v4: uuidv4 } = require("uuid");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 8080;
const API_KEY = process.env.API_KEY || "";
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

const STORAGE_DIR = path.join(__dirname, "images");
if (!fs.existsSync(STORAGE_DIR)) fs.mkdirSync(STORAGE_DIR, { recursive: true });

app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// ─────────────────────────────────────────────
// Reusable browser instance
// ─────────────────────────────────────────────
let browser = null;

async function getBrowser() {
  if (browser && browser.connected) return browser;

  browser = await puppeteer.launch({
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
      "--disable-extensions",
      "--disable-background-networking",
      "--disable-default-apps",
      "--disable-translate",
      "--no-first-run",
    ],
    protocolTimeout: 120000,
    timeout: 120000,
  });

  console.log("✅ Browser launched successfully");
  return browser;
}

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
// Helper: build full HTML
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

// ─────────────────────────────────────────────
// Core: render HTML to image
// ─────────────────────────────────────────────
async function renderImage({ html, css, google_fonts, viewport_width, viewport_height, device_scale, transparent }) {
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    const vw = parseInt(viewport_width) || 1080;
    const vh = parseInt(viewport_height) || 1080;
    const ds = parseFloat(device_scale) || 2;

    await page.setViewport({ width: vw, height: vh, deviceScaleFactor: ds });

    const fullHtml = buildFullHtml({ html, css, google_fonts });
    await page.setContent(fullHtml, { waitUntil: "networkidle0", timeout: 30000 });

    // Wait a moment for fonts to load
    await page.evaluate(() => document.fonts.ready);

    const screenshot = await page.screenshot({
      type: "png",
      fullPage: true,
      omitBackground: transparent === true || transparent === "true",
    });

    return screenshot;
  } finally {
    await page.close();
  }
}

// ─────────────────────────────────────────────
// POST /v1/image — Generate image, get URL
// ─────────────────────────────────────────────
app.post("/v1/image", authenticate, async (req, res) => {
  try {
    const { html } = req.body;
    if (!html) return res.status(400).json({ error: "Missing 'html' parameter" });

    const imageBuffer = await renderImage(req.body);

    const imageId = uuidv4();
    const filename = `${imageId}.png`;
    const filepath = path.join(STORAGE_DIR, filename);

    fs.writeFileSync(filepath, imageBuffer);

    res.status(200).json({
      url: `${BASE_URL}/images/${filename}`,
      id: imageId,
    });
  } catch (error) {
    console.error("Image generation error:", error);
    // If browser crashed, reset it
    if (browser) {
      try { await browser.close(); } catch (e) {}
      browser = null;
    }
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

    const imageBuffer = await renderImage(req.body);

    res.status(200).json({
      base64: imageBuffer.toString("base64"),
      content_type: "image/png",
    });
  } catch (error) {
    console.error("Image generation error:", error);
    if (browser) {
      try { await browser.close(); } catch (e) {}
      browser = null;
    }
    res.status(500).json({ error: "Failed to generate image", message: error.message });
  }
});

// Serve images
app.use("/images", express.static(STORAGE_DIR));

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "ok", browser_connected: browser?.connected || false, uptime: process.uptime() });
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

// Pre-launch browser on startup
getBrowser()
  .then(() => console.log("🖼️  Browser ready"))
  .catch((err) => console.error("⚠️  Browser pre-launch failed (will retry on first request):", err.message));

// Start
app.listen(PORT, () => {
  console.log(`\n🖼️  HTML-to-Image API running on port ${PORT}`);
  console.log(`   POST ${BASE_URL}/v1/image`);
  console.log(`   POST ${BASE_URL}/v1/image/base64`);
  console.log(`   GET  ${BASE_URL}/health\n`);
  if (!API_KEY) console.log("   ⚠️  No API_KEY set — running without authentication\n");
});
