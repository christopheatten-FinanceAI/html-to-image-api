const express = require("express");
const nodeHtmlToImage = require("node-html-to-image");
const cors = require("cors");
const { v4: uuidv4 } = require("uuid");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const API_KEY = process.env.API_KEY || ""; // Optional: set for basic auth
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

// Store generated images in memory (or disk)
const STORAGE_DIR = path.join(__dirname, "images");
if (!fs.existsSync(STORAGE_DIR)) {
  fs.mkdirSync(STORAGE_DIR, { recursive: true });
}

// Middleware
app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// ─────────────────────────────────────────────
// Auth middleware (optional, skip if no API_KEY)
// ─────────────────────────────────────────────
function authenticate(req, res, next) {
  if (!API_KEY) return next(); // No key set = open access

  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ error: "Missing Authorization header" });
  }

  // Support both Bearer token and Basic auth
  if (authHeader.startsWith("Bearer ")) {
    const token = authHeader.slice(7);
    if (token !== API_KEY) {
      return res.status(403).json({ error: "Invalid API key" });
    }
  } else if (authHeader.startsWith("Basic ")) {
    const decoded = Buffer.from(authHeader.slice(6), "base64").toString();
    // Accept key as either user:pass format or just the key
    if (!decoded.includes(API_KEY)) {
      return res.status(403).json({ error: "Invalid API key" });
    }
  } else {
    return res.status(401).json({ error: "Invalid auth format" });
  }

  next();
}

// ─────────────────────────────────────────────
// POST /v1/image — Generate image (HCTI-compatible)
// ─────────────────────────────────────────────
app.post("/v1/image", authenticate, async (req, res) => {
  try {
    const { html, css, google_fonts, viewport_width, viewport_height, device_scale, transparent } = req.body;

    if (!html) {
      return res.status(400).json({ error: "Missing 'html' parameter" });
    }

    // Combine HTML with CSS and Google Fonts
    let fullHtml = html;

    // Inject Google Fonts if provided
    if (google_fonts) {
      const fontLink = `<link href="https://fonts.googleapis.com/css2?family=${encodeURIComponent(google_fonts)}&display=swap" rel="stylesheet">`;
      if (fullHtml.includes("<head>")) {
        fullHtml = fullHtml.replace("<head>", `<head>${fontLink}`);
      } else if (fullHtml.includes("<html>")) {
        fullHtml = fullHtml.replace("<html>", `<html><head>${fontLink}</head>`);
      } else {
        fullHtml = `<html><head>${fontLink}</head><body>${fullHtml}</body></html>`;
      }
    }

    // Inject CSS if provided separately
    if (css) {
      const styleTag = `<style>${css}</style>`;
      if (fullHtml.includes("</head>")) {
        fullHtml = fullHtml.replace("</head>", `${styleTag}</head>`);
      } else if (fullHtml.includes("<body>")) {
        fullHtml = fullHtml.replace("<body>", `${styleTag}<body>`);
      } else {
        fullHtml = `<style>${css}</style>${fullHtml}`;
      }
    }

    // Wrap bare HTML if needed
    if (!fullHtml.includes("<html")) {
      fullHtml = `<html><head><meta charset="UTF-8"></head><body>${fullHtml}</body></html>`;
    }

    const imageId = uuidv4();
    const filename = `${imageId}.png`;
    const filepath = path.join(STORAGE_DIR, filename);

    // Configure puppeteer args
    const puppeteerArgs = {
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
    };

    // Build options
    const options = {
      output: filepath,
      html: fullHtml,
      puppeteerArgs,
      transparent: transparent === true || transparent === "true",
    };

    // Viewport configuration
    if (viewport_width || viewport_height) {
      options.viewport = {
        width: parseInt(viewport_width) || 1080,
        height: parseInt(viewport_height) || 1080,
      };
    }

    if (device_scale) {
      options.viewport = options.viewport || { width: 1080, height: 1080 };
      options.viewport.deviceScaleFactor = parseFloat(device_scale) || 2;
    }

    await nodeHtmlToImage(options);

    // Return HCTI-compatible response
    const imageUrl = `${BASE_URL}/images/${imageId}.png`;

    res.status(200).json({
      url: imageUrl,
      id: imageId,
    });
  } catch (error) {
    console.error("Image generation error:", error);
    res.status(500).json({
      error: "Failed to generate image",
      message: error.message,
    });
  }
});

// ─────────────────────────────────────────────
// POST /v1/image/base64 — Return image as base64
// (Useful for n8n when you don't want URL storage)
// ─────────────────────────────────────────────
app.post("/v1/image/base64", authenticate, async (req, res) => {
  try {
    const { html, css, google_fonts, viewport_width, viewport_height, device_scale, transparent } = req.body;

    if (!html) {
      return res.status(400).json({ error: "Missing 'html' parameter" });
    }

    let fullHtml = html;

    if (google_fonts) {
      const fontLink = `<link href="https://fonts.googleapis.com/css2?family=${encodeURIComponent(google_fonts)}&display=swap" rel="stylesheet">`;
      if (fullHtml.includes("<head>")) {
        fullHtml = fullHtml.replace("<head>", `<head>${fontLink}`);
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

    const options = {
      html: fullHtml,
      encoding: "base64",
      transparent: transparent === true || transparent === "true",
      puppeteerArgs: {
        args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
      },
    };

    if (viewport_width || viewport_height) {
      options.viewport = {
        width: parseInt(viewport_width) || 1080,
        height: parseInt(viewport_height) || 1080,
      };
    }

    if (device_scale) {
      options.viewport = options.viewport || { width: 1080, height: 1080 };
      options.viewport.deviceScaleFactor = parseFloat(device_scale) || 2;
    }

    const base64 = await nodeHtmlToImage(options);

    res.status(200).json({
      base64: base64,
      content_type: "image/png",
    });
  } catch (error) {
    console.error("Image generation error:", error);
    res.status(500).json({ error: "Failed to generate image", message: error.message });
  }
});

// ─────────────────────────────────────────────
// GET /images/:filename — Serve generated images
// ─────────────────────────────────────────────
app.use("/images", express.static(STORAGE_DIR));

// ─────────────────────────────────────────────
// GET /health — Health check for monitoring
// ─────────────────────────────────────────────
app.get("/health", (req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

// ─────────────────────────────────────────────
// Cleanup old images (every 30 min, delete > 1h old)
// ─────────────────────────────────────────────
setInterval(() => {
  const cutoff = Date.now() - 60 * 60 * 1000; // 1 hour
  fs.readdirSync(STORAGE_DIR).forEach((file) => {
    const fp = path.join(STORAGE_DIR, file);
    const stat = fs.statSync(fp);
    if (stat.mtimeMs < cutoff) {
      fs.unlinkSync(fp);
    }
  });
}, 30 * 60 * 1000);

// ─────────────────────────────────────────────
// Start
// ─────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n🖼️  HTML-to-Image API running on port ${PORT}`);
  console.log(`   POST ${BASE_URL}/v1/image         → returns image URL`);
  console.log(`   POST ${BASE_URL}/v1/image/base64   → returns base64`);
  console.log(`   GET  ${BASE_URL}/health             → health check\n`);
  if (!API_KEY) {
    console.log("   ⚠️  No API_KEY set — running without authentication\n");
  }
});
