// Renders video.html frame-by-frame with Playwright and encodes an MP4 with ffmpeg.
// Usage: node linkedin-video/render.js [--stills 1.9,6.9,...]
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const FPS = 30, DURATION = 22.6, W = 1080, H = 1350;
const out = path.join(__dirname, 'fable-5.2-finance-linkedin.mp4');
const stillsArg = process.argv.indexOf('--stills');

(async () => {
  const frames = fs.mkdtempSync(path.join(process.env.FRAMES_DIR || os.tmpdir(), 'frames-'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'video.html') + '?t=0');
  await page.evaluate(() => document.fonts.ready);

  if (stillsArg > -1) {
    for (const t of process.argv[stillsArg + 1].split(',')) {
      await page.evaluate(x => window.seek(x), +t);
      await page.screenshot({ path: path.join(frames, `still-${t}.png`) });
    }
    console.log(frames);
    return browser.close();
  }

  const total = Math.round(FPS * DURATION);
  for (let i = 0; i < total; i++) {
    await page.evaluate(x => window.seek(x), i / FPS);
    await page.screenshot({ path: path.join(frames, String(i).padStart(5, '0') + '.png') });
  }
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS),
    '-i', path.join(frames, '%05d.png'),
    '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100', '-shortest',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', out], { stdio: 'inherit' });
  fs.rmSync(frames, { recursive: true, force: true });
  console.log('wrote', out);
})();
