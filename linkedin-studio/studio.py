#!/usr/bin/env python3
"""LinkedIn media studio for Christophe Atten (AI in Finance).

Render on-brand media from a JSON spec (formats in README.md):

  python3 studio.py image    spec.json --out DIR --name BASE  -> BASE.jpg (2160x2700)
  python3 studio.py carousel spec.json --out DIR --name BASE  -> BASE.pdf, BASE_cover.jpg
  python3 studio.py video    spec.json --out DIR --name BASE  -> BASE.mp4 (1080x1350, 30 fps),
                                                               BASE_poster.jpg, BASE_contact.jpg

Every run also writes BASE_check.jpg (images and carousels: all pages side by side;
videos: the last frame of every scene) so the result can be looked at before it is used.

Prints one JSON report on stdout. Exit code 0 = fine, 2 = rendered but some text
overflows (shorten it and render again), 1 = error.
"""
import argparse, base64, html, json, math, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'fonts')
esc = lambda s: html.escape(str(s)).replace('\n', '<br>')


def font_css():
    out = []
    for w in (400, 500, 600, 700, 800, 900):
        p = os.path.join(FONTS, f'Inter-{w}.woff2')
        b64 = base64.b64encode(open(p, 'rb').read()).decode()
        out.append(f"@font-face{{font-family:'Inter';font-weight:{w};font-style:normal;src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return '\n'.join(out)


# =====================================================================  static design (images, carousels)
STATIC_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px}
body{font-family:'Inter',sans-serif;color:#E9EEF4;background:#0E1621;position:relative;overflow:hidden;font-feature-settings:'cv11' 1}
.glow{position:absolute;inset:0;background:
 radial-gradient(700px 600px at 92% 4%, rgba(70,130,255,.30), transparent 70%),
 radial-gradient(640px 560px at 4% 100%, rgba(244,183,64,.20), transparent 70%)}
.frame{position:absolute;inset:0;padding:84px 88px 136px;display:flex;flex-direction:column}
.eyebrow{font-size:26px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#F4B740}
h1{font-size:76px;line-height:1.04;letter-spacing:-.03em;font-weight:800;color:#FFFFFF;margin-top:22px;text-wrap:balance}
h1.xl{font-size:92px}
h1.dense{font-size:62px}
.sub{font-size:34px;line-height:1.35;color:#A9B8C7;margin-top:30px;max-width:860px}
.items{margin-top:52px;display:flex;flex-direction:column;gap:22px}
.item{display:grid;grid-template-columns:64px 1fr;gap:22px;align-items:start;padding:22px 26px;border-radius:18px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.08)}
.items.compact{gap:12px;margin-top:34px}
.items.compact .item{padding:12px 22px;grid-template-columns:56px 1fr;align-items:center}
.items.compact .n{width:48px;height:48px;font-size:22px}
.items.tight{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:34px}
.items.tight .item{padding:12px 16px;grid-template-columns:44px 1fr;align-items:center;gap:12px}
.items.tight .n{width:40px;height:40px;font-size:19px}
.items.tight .it{font-size:24px;line-height:1.22}
.items.tight .id{display:none}
.n{width:56px;height:56px;border-radius:50%;background:rgba(70,130,255,.18);color:#8DB5FF;font-weight:800;font-size:26px;display:grid;place-items:center}
.it{font-size:34px;font-weight:700;color:#FFFFFF;line-height:1.2}
.items.compact .it{font-size:30px}
.id{font-size:26px;color:#A9B8C7;margin-top:6px;line-height:1.35}
.items.compact .id{font-size:24px;margin-top:3px}
.grid{margin-top:60px;display:grid;grid-template-columns:1fr 1fr;gap:24px}
.cell{border-radius:20px;padding:34px 32px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);min-height:250px}
.cell b{display:block;font-size:52px;font-weight:800;color:#F4B740;letter-spacing:-.02em}
.cell span{display:block;font-size:30px;line-height:1.35;color:#D3DCE6;margin-top:14px}
.two{margin-top:52px;display:grid;grid-template-columns:1fr 1fr;gap:24px}
.col{border-radius:20px;padding:30px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.08)}
.col h3{font-size:24px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:20px}
.col.ok h3{color:#7FD7A8} .col.no h3{color:#FF9B8A}
.col li{list-style:none;font-size:29px;line-height:1.3;font-weight:600;color:#FFFFFF;padding:13px 0;border-top:1px solid rgba(255,255,255,.08);display:flex;gap:14px}
.col li:first-child{border-top:none}
.col.ok li::before{content:'✓';color:#7FD7A8;font-weight:800}
.col.no li::before{content:'×';color:#FF9B8A;font-weight:800}
.items,.grid,.two{margin-bottom:28px}
.kicker{margin-top:auto;margin-bottom:24px;font-size:34px;line-height:1.3;font-weight:700;color:#FFFFFF;border-left:6px solid #F4B740;padding-left:24px}
.badge{align-self:flex-start;margin-bottom:0;font-size:24px;font-weight:700;color:#0E1621;background:#F4B740;border-radius:999px;padding:12px 24px}
.foot{position:absolute;left:88px;right:88px;bottom:44px;display:flex;justify-content:space-between;align-items:center;font-size:24px;color:#8796A6;border-top:1px solid rgba(255,255,255,.1);padding-top:24px}
.foot b{color:#E9EEF4;font-weight:700}
.page{font-variant-numeric:tabular-nums}
.bignum{font-size:200px;font-weight:800;line-height:.9;letter-spacing:-.05em;color:transparent;-webkit-text-stroke:3px rgba(244,183,64,.85);margin-top:10px}
.frame.mid{justify-content:center;padding-bottom:180px}
.frame.mid h1{font-size:84px}
.body{font-size:46px;line-height:1.3;color:#E9EEF4;margin-top:36px;font-weight:500}
.tip{margin-top:44px;font-size:36px;line-height:1.35;font-weight:700;color:#F4B740}
.list{margin-top:48px;display:flex;flex-direction:column;gap:18px}
.list li{list-style:none;font-size:40px;line-height:1.3;font-weight:600;color:#FFFFFF;display:grid;grid-template-columns:70px 1fr;gap:10px;padding:18px 0;border-top:1px solid rgba(255,255,255,.09)}
.list.dense li{font-size:34px;padding:12px 0}
.list li:first-child{border-top:none}
.list li i{font-style:normal;color:#8DB5FF;font-weight:800}
.rulebox{margin-top:56px;border-radius:24px;padding:48px;background:rgba(244,183,64,.10);border:2px solid rgba(244,183,64,.55);font-size:46px;line-height:1.32;font-weight:600;color:#FFFFFF}
.swipe{margin-top:auto;margin-bottom:0;font-size:30px;font-weight:700;color:#8DB5FF}
.ctabox{margin-top:70px;font-size:48px;line-height:1.3;color:#FFFFFF;font-weight:600}
.arrow{font-size:120px;color:#F4B740;margin-top:40px;line-height:1}
"""


def shell(inner, page=None, mid=False):
    pg = f'<span class="page">{page}</span>' if page else '<span>christopheatten.com</span>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_css()}{STATIC_CSS}</style></head>
<body><div class="glow"></div><div class="frame{' mid' if mid else ''}">{inner}</div>
<div class="foot"><span><b>Christophe Atten</b> · AI in Finance</span>{pg}</div></body></html>"""


def image_html(im):
    dense = ' class="dense"' if len(im.get('items', [])) > 5 or len(im['title']) > 40 else ''
    parts = [f'<div class="eyebrow">{esc(im["eyebrow"])}</div><h1{dense}>{esc(im["title"])}</h1>']
    if 'items' in im:
        compact = ' tight' if len(im['items']) > 8 else (' compact' if len(im['items']) > 5 else '')
        parts.append(f'<div class="items{compact}">' + ''.join(
            f'<div class="item"><span class="n">{i+1}</span><div><div class="it">{esc(t)}</div><div class="id">{esc(d)}</div></div></div>'
            for i, (t, d) in enumerate(im['items'])) + '</div>')
    if 'grid' in im:
        parts.append('<div class="grid">' + ''.join(f'<div class="cell"><b>{esc(t)}</b><span>{esc(d)}</span></div>' for t, d in im['grid']) + '</div>')
    if 'twocol' in im:
        ok, no = im['twocol']
        la, lb = im.get('labels', ['Handles well', 'Never owns'])
        parts.append(f'<div class="two"><div class="col ok"><h3>{esc(la)}</h3><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in ok) +
                     f'</ul></div><div class="col no"><h3>{esc(lb)}</h3><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in no) + '</ul></div></div>')
    if im.get('kicker'):
        parts.append(f'<div class="kicker">{esc(im["kicker"])}</div>')
    if im.get('badge'):
        parts.append(f'<div class="badge">{esc(im["badge"])}</div>')
    return shell(''.join(parts))


def slide_html(s, i, total):
    k = s['kind']
    page = f'{i}/{total}'
    if k == 'cover':
        inner = f'<div class="eyebrow">{esc(s["eyebrow"])}</div><h1 class="xl">{esc(s["title"])}</h1><div class="sub">{esc(s.get("sub", ""))}</div><div class="swipe">Swipe →</div>'
    elif k == 'step':
        inner = f'<div class="eyebrow">Step {s["n"]}</div><div class="bignum">{s["n"]}</div><h1>{esc(s["title"])}</h1><div class="body">{esc(s["body"])}</div>' + (f'<div class="tip">{esc(s["tip"])}</div>' if s.get('tip') else '')
    elif k == 'plain':
        inner = f'<div class="eyebrow">{esc(s["eyebrow"])}</div><h1>{esc(s["title"])}</h1><div class="body">{esc(s["body"])}</div>' + (f'<div class="tip">{esc(s["tip"])}</div>' if s.get('tip') else '')
    elif k == 'list':
        st = s.get('start', 1)
        dense = ' dense' if len(s['items']) > 5 else ''
        lis = ''.join(f'<li><i>{(st+j):02d}</i><span>{esc(x)}</span></li>' for j, x in enumerate(s['items']))
        inner = f'<div class="eyebrow">{esc(s["eyebrow"])}</div><h1>{esc(s["title"])}</h1><ul class="list{dense}">{lis}</ul>'
    elif k == 'rule':
        inner = f'<div class="eyebrow">{esc(s.get("eyebrow", "Before you start"))}</div><h1>{esc(s["title"])}</h1><div class="rulebox">{esc(s["body"])}</div>'
    elif k == 'cta':
        inner = f'<div class="eyebrow">{esc(s.get("eyebrow", "Free resource"))}</div><h1 class="xl">{esc(s["title"])}</h1><div class="ctabox">{esc(s["body"])}</div><div class="sub">{esc(s.get("sub", ""))}</div><div class="arrow">↑</div>'
    else:
        raise ValueError(f'unknown slide kind: {k}')
    return shell(inner, page, mid=(k != 'cover'))


MEASURE_STATIC = """()=>{const f=document.querySelector('.frame');const foot=document.querySelector('.foot');
 let bottom=0,right=0; f.querySelectorAll('*').forEach(e=>{const r=e.getBoundingClientRect(); if(r.width&&r.height){bottom=Math.max(bottom,r.bottom);right=Math.max(right,r.right)}});
 return {bottom:Math.round(bottom), footTop:Math.round(foot.getBoundingClientRect().top), right:Math.round(right), fonts:document.fonts.check('800 40px Inter')}}"""


def _page(b, w=1080, h=1350, dsf=2):
    return b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=dsf)


def _load(pg, htm, tmpdir, name='page.html'):
    p = os.path.join(tmpdir, name)
    open(p, 'w', encoding='utf-8').write(htm)
    pg.goto('file://' + p)
    pg.evaluate('document.fonts.ready.then(()=>true)')
    pg.wait_for_timeout(80)


def contact_sheet(paths, out, cols=None, thumb_w=360):
    from PIL import Image
    ims = [Image.open(p).convert('RGB') for p in paths]
    ims = [im.resize((thumb_w, int(im.height * thumb_w / im.width))) for im in ims]
    cols = cols or min(len(ims), 6)
    rows = math.ceil(len(ims) / cols)
    h = max(im.height for im in ims)
    sheet = Image.new('RGB', (cols * thumb_w + (cols + 1) * 12, rows * h + (rows + 1) * 12), (240, 242, 245))
    for k, im in enumerate(ims):
        r, c = divmod(k, cols)
        sheet.paste(im, (12 + c * (thumb_w + 12), 12 + r * (h + 12)))
    sheet.save(out, quality=85)
    return out


def render_image(spec, out, name):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    warnings = []
    tmp = tempfile.mkdtemp()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = _page(b)
        _load(pg, image_html(spec), tmp)
        m = pg.evaluate(MEASURE_STATIC)
        if m['bottom'] > m['footTop'] - 6:
            warnings.append(f"content runs into the footer by {m['bottom'] - m['footTop'] + 6}px: shorten the text or use fewer items")
        if m['right'] > 1080 - 60:
            warnings.append('content is wider than the frame')
        png = os.path.join(tmp, 'img.png')
        pg.screenshot(path=png)
        b.close()
    jpg = os.path.join(out, name + '.jpg')
    Image.open(png).convert('RGB').save(jpg, quality=90)
    check = contact_sheet([jpg], os.path.join(out, name + '_check.jpg'), thumb_w=540)
    shutil.rmtree(tmp, ignore_errors=True)
    return {'files': {'image': jpg, 'check': check}, 'warnings': warnings, 'fonts_ok': m['fonts']}


def render_carousel(spec, out, name):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import img2pdf
    slides = spec['slides']
    warnings = []
    tmp = tempfile.mkdtemp()
    jpgs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = _page(b)
        for i, s in enumerate(slides, 1):
            _load(pg, slide_html(s, i, len(slides)), tmp, f's{i}.html')
            m = pg.evaluate(MEASURE_STATIC)
            if m['bottom'] > m['footTop'] - 6:
                warnings.append(f"slide {i}: content runs into the footer by {m['bottom'] - m['footTop'] + 6}px")
            if m['right'] > 1080 - 60:
                warnings.append(f'slide {i}: content is wider than the frame')
            png = os.path.join(tmp, f's{i}.png')
            pg.screenshot(path=png)
            jp = os.path.join(tmp, f's{i}.jpg')
            Image.open(png).convert('RGB').save(jp, quality=88)
            jpgs.append(jp)
        b.close()
    pdf = os.path.join(out, name + '.pdf')
    with open(pdf, 'wb') as f:
        f.write(img2pdf.convert(jpgs, layout_fun=img2pdf.get_layout_fun((img2pdf.mm_to_pt(1080 / 4), img2pdf.mm_to_pt(1350 / 4)))))
    cover = os.path.join(out, name + '_cover.jpg')
    Image.open(jpgs[0]).convert('RGB').resize((1080, 1350)).save(cover, quality=88)
    check = contact_sheet(jpgs, os.path.join(out, name + '_check.jpg'), cols=min(len(jpgs), 5), thumb_w=320)
    shutil.rmtree(tmp, ignore_errors=True)
    return {'files': {'pdf': pdf, 'cover': cover, 'check': check}, 'slides': len(slides), 'warnings': warnings, 'fonts_ok': m['fonts']}


# =====================================================================  kinetic video
VIDEO_CSS = """
:root{--navy:#0D1726;--navy2:#13223A;--card:#1A2D4B;--teal:#2EC4B0;--red:#E63946;--yellow:#FFD23F;--paper:#F5F7FA;--ink:#0D1726;--muted:#8CA0BA}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden;background:var(--navy);font-family:'Inter',sans-serif;font-feature-settings:'cv11' 1}
#progress{position:absolute;left:0;top:0;height:10px;width:100%;background:var(--yellow);transform-origin:left;transform:scaleX(0);z-index:9}
.scene{position:absolute;inset:0;display:none;overflow:hidden}
.stage{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:130px 90px 170px;gap:30px;transform-origin:50% 45%}
.scene.left .stage{align-items:flex-start;text-align:left}
.bg-navy{background:var(--navy);color:#fff}.bg-navy2{background:var(--navy2);color:#fff}.bg-teal{background:var(--teal);color:var(--ink)}
.bg-red{background:var(--red);color:#fff}.bg-paper{background:var(--paper);color:var(--ink)}.bg-yellow{background:var(--yellow);color:var(--ink)}
.kick{font-size:36px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}
.bg-navy .kick,.bg-navy2 .kick,.bg-red .kick{color:var(--yellow)}.bg-paper .kick{color:var(--red)}.bg-teal .kick,.bg-yellow .kick{color:var(--navy)}
.lead{font-size:46px;font-weight:600;line-height:1.25;opacity:.8}
.mega{font-size:280px;font-weight:900;letter-spacing:-.045em;line-height:.9;font-variant-numeric:tabular-nums;white-space:nowrap}
.huge{font-size:128px;font-weight:900;line-height:.98;letter-spacing:-.03em;text-transform:uppercase}
.big{font-size:96px;font-weight:900;line-height:1.02;letter-spacing:-.025em;text-transform:uppercase}
.mid{font-size:66px;font-weight:800;line-height:1.1;letter-spacing:-.02em}
.text{font-size:46px;font-weight:600;line-height:1.3}
.note{font-size:36px;font-weight:600;line-height:1.35;opacity:.85}
.c-yellow{color:var(--yellow)}.c-teal{color:var(--teal)}.c-red{color:var(--red)}.c-white{color:#fff}.c-navy{color:var(--navy)}
.lines{display:flex;flex-direction:column;align-items:center;gap:6px}
.band{align-self:stretch;margin:10px -90px;background:var(--navy);color:var(--yellow);padding:28px 40px;font-size:86px;font-weight:900;letter-spacing:-.02em;text-transform:uppercase}
.bg-navy .band,.bg-navy2 .band{background:var(--yellow);color:var(--navy)}
.pills{display:flex;flex-direction:column;gap:22px;align-items:center}
.pill{display:inline-block;background:var(--yellow);color:var(--ink);border-radius:999px;padding:16px 44px;font-size:50px;font-weight:800}
.bg-yellow .pill{background:var(--navy);color:var(--yellow)}
.cards{display:flex;flex-direction:column;gap:26px;align-self:stretch}
.card{background:var(--card);border-radius:24px;padding:28px 38px;text-align:left;color:#fff}
.bg-paper .card,.bg-teal .card,.bg-yellow .card{background:var(--navy)}
.card .lab{font-size:28px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.card .val{font-size:74px;font-weight:900;text-transform:uppercase;line-height:1.05;margin-top:4px}
.card.red .val{color:var(--red)}.card.teal .val{color:var(--teal)}.card.yellow .val{color:var(--yellow)}
.neq{position:relative;width:210px;height:150px;margin:8px 0}
.neq i{position:absolute;left:0;right:0;height:28px;background:var(--red);border-radius:6px}
.neq i:first-child{top:30px}.neq i:last-child{bottom:30px}
.neq b{position:absolute;left:50%;top:-14px;width:28px;height:178px;background:var(--red);border-radius:6px;transform:translateX(-50%) rotate(28deg)}
.strike{position:relative;display:inline-block}
.strike::after{content:'';position:absolute;left:-3%;right:-3%;top:47%;height:16px;background:var(--red);border-radius:8px;transform-origin:left;transform:scaleX(var(--s,0))}
.bars{align-self:stretch;display:flex;flex-direction:column;gap:34px;text-align:left;margin-top:30px}
.barlab{font-size:28px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.track{height:60px;border-radius:14px;background:rgba(255,255,255,.07);overflow:hidden}
.bg-paper .track,.bg-teal .track{background:rgba(13,23,38,.08)}
.fill{height:100%;border-radius:14px;background:var(--muted);transform-origin:left}
.fill.teal{background:var(--teal)}.fill.yellow{background:var(--yellow)}.fill.red{background:var(--red)}
.dots{display:flex;gap:12px}.dots i{width:22px;height:22px;border-radius:50%;background:rgba(255,255,255,.2)}.dots i.on{background:var(--yellow)}
.top{align-self:stretch;display:flex;justify-content:space-between;align-items:center}
.sq{align-self:stretch;display:grid;grid-template-columns:repeat(10,1fr);gap:14px}
.sq i{aspect-ratio:1;border-radius:10px;background:var(--teal)}.sq i.m{background:var(--red)}
.legend{display:flex;gap:34px;font-size:28px;font-weight:700}.legend span::before{content:'';display:inline-block;width:22px;height:22px;border-radius:5px;margin-right:10px;vertical-align:-3px;background:var(--teal)}
.legend span.m::before{background:var(--red)}
.list{align-self:stretch;display:flex;flex-direction:column;gap:20px;text-align:left}
.li{display:grid;grid-template-columns:96px 1fr;gap:18px;align-items:center;background:var(--card);border-radius:22px;padding:22px 30px;color:#fff}
.bg-paper .li,.bg-teal .li,.bg-yellow .li{background:var(--navy)}
.li b{font-size:52px;font-weight:900;color:var(--yellow);font-variant-numeric:tabular-nums}
.li span{font-size:42px;font-weight:700;line-height:1.2}
.deco{position:absolute;height:24px;border-radius:4px;background:rgba(0,0,0,.16)}
.brand{position:absolute;left:90px;right:90px;bottom:62px;display:flex;justify-content:space-between;font-size:26px;font-weight:700;opacity:.55}
.book{position:relative;width:430px;height:560px;border-radius:10px 22px 22px 10px;background:linear-gradient(160deg,#1E3354,#0F1C30);box-shadow:0 40px 80px rgba(0,0,0,.45),inset 10px 0 0 rgba(255,255,255,.06);transform:rotate(-6deg);padding:60px 46px;text-align:left;color:#fff;display:flex;flex-direction:column}
.book .bt{font-size:52px;font-weight:900;line-height:1.08;letter-spacing:-.02em}
.book .bl{width:70px;height:7px;background:var(--yellow);margin:26px 0}
.book .ba{margin-top:auto;font-size:22px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.book .stripe{position:absolute;left:46px;right:46px;top:26px;height:6px;background:var(--teal);border-radius:3px}
.burst{position:absolute;right:-48px;bottom:84px;width:150px;height:150px;border-radius:50%;background:var(--yellow);color:var(--navy);display:grid;place-items:center;text-align:center;font-size:28px;font-weight:900;line-height:1;transform:rotate(8deg)}
.url{font-size:52px;font-weight:900;color:var(--yellow)}
"""

ENGINE_JS = r"""
(function(){
const scenes=[...document.querySelectorAll('.scene')];
let acc=0; scenes.forEach(s=>{s._start=acc;s._dur=parseFloat(s.dataset.dur||'5');acc+=s._dur;});
const TOTAL=acc; window.__duration=TOTAL;
const E={out:x=>1-Math.pow(1-x,3),inout:x=>x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2,back:x=>{const c1=1.70158,c3=c1+1;return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2)}};
const items=scenes.map(s=>[...s.querySelectorAll('[data-anim]')].map(e=>({e,a:e.dataset.anim,at:parseFloat(e.dataset.at||'0'),len:parseFloat(e.dataset.len||'0.55')})));
const bar=document.getElementById('progress');
function fmt(v,f){ if(f==='comma') return Math.round(v).toLocaleString('en-GB'); if(f==='dec1') return v.toFixed(1); if(f==='pct') return Math.round(v)+'%'; return String(Math.round(v)); }
function apply(o,r){
  const e=o.e;
  switch(o.a){
    case 'up':{const p=E.out(r);e.style.opacity=p;e.style.transform=`translateY(${(1-p)*60}px)`;break}
    case 'down':{const p=E.out(r);e.style.opacity=p;e.style.transform=`translateY(${-(1-p)*60}px)`;break}
    case 'left':{const p=E.out(r);e.style.opacity=p;e.style.transform=`translateX(${-(1-p)*90}px)`;break}
    case 'right':{const p=E.out(r);e.style.opacity=p;e.style.transform=`translateX(${(1-p)*90}px)`;break}
    case 'fade':{e.style.opacity=E.out(r);break}
    case 'pop':{const p=r<=0?0:E.back(r);e.style.opacity=Math.min(1,r*3);e.style.transform=`scale(${0.55+0.45*p})`;break}
    case 'zoom':{const p=E.out(r);e.style.opacity=p;e.style.transform=`scale(${1.35-0.35*p})`;break}
    case 'wipe':{const p=E.inout(r);e.style.clipPath=`inset(0 ${(1-p)*100}% 0 0)`;break}
    case 'count':{const p=E.out(r);const a=parseFloat(e.dataset.from||'0'),b=parseFloat(e.dataset.to||'0');e.textContent=(e.dataset.pre||'')+fmt(a+(b-a)*p,e.dataset.fmt)+(e.dataset.suf||'');e.style.opacity=r>0?1:0;break}
    case 'strike':{e.style.setProperty('--s',E.inout(r));break}
    case 'grow':{e.style.transform=`scaleX(${E.out(r)*parseFloat(e.dataset.to||'1')})`;break}
    case 'type':{const full=e.dataset.text||'';e.textContent=full.slice(0,Math.round(full.length*r));break}
    case 'slide':{const p=E.inout(r);const from=parseFloat(e.dataset.from||'-400'),to=parseFloat(e.dataset.to||'0');e.style.transform=`translateX(${from+(to-from)*p}px)`;break}
  }
}
window.setT=function(t){
  scenes.forEach((s,i)=>{
    const lt=t-s._start, last=i===scenes.length-1;
    const on=lt>=0&&(lt<s._dur||(last&&lt<=s._dur+1));
    s.style.display=on?'block':'none';
    if(!on) return;
    const st=s.querySelector('.stage'); if(st) st.style.transform=`scale(${1+0.035*Math.min(1,lt/s._dur)})`;
    for(const o of items[i]) apply(o,Math.min(1,Math.max(0,(lt-o.at)/o.len)));
  });
  if(bar) bar.style.transform=`scaleX(${Math.min(1,t/TOTAL)})`;
};
window.sceneTimes=()=>scenes.map(s=>[s._start,s._dur]);
window.setT(0);
})();
"""


class Cue:
    """Hands out reveal times inside one scene."""
    def __init__(self, t=0.25):
        self.t = t
        self.end = t

    def at(self, gap, length=0.55):
        a = self.t
        self.t += gap
        self.end = max(self.end, a + length)
        return a, length


def A(anim, at_len, extra=''):
    at, ln = at_len
    return f'data-anim="{anim}" data-at="{at:.2f}" data-len="{ln:.2f}" {extra}'


def words(*xs):
    n = 0
    for x in xs:
        if isinstance(x, (list, tuple)):
            n += words(*x)
        elif x:
            n += len(str(x).split())
    return n


def scene_html(sc, idx, total):
    k = sc['kind']
    bg = sc.get('bg', 'navy')
    q = Cue()
    deco = ''
    cls = ''
    if k == 'number':
        val = sc['value']
        body = (f'<div class="lead" {A("up", q.at(0.5))}>{esc(sc.get("kicker", ""))}</div>' if sc.get('kicker') else '')
        color = sc.get('color') or ('white' if bg in ('navy', 'navy2', 'red') else 'navy')
        extra = 'data-from="{}" data-to="{}" data-fmt="{}" data-pre="{}" data-suf="{}"'.format(
            sc.get('from', 0), val, sc.get('format', 'comma'), esc(sc.get('prefix', '')), esc(sc.get('suffix', '')))
        body += f'<div class="mega c-{color}" {A("count", q.at(1.9, 1.6), extra)}>0</div>'
        if sc.get('caption'):
            body += f'<div class="mid" {A("up", q.at(0.6))}>{esc(sc["caption"])}</div>'
        w = words(sc.get('kicker'), sc.get('caption')) + 2
    elif k == 'statement':
        lines = sc['lines']
        body = '<div class="lines">' + ''.join(f'<div class="huge" {A("up", q.at(0.32))}>{esc(l)}</div>' for l in lines)
        if sc.get('highlight'):
            body += f'<div class="huge c-{sc.get("hcolor", "yellow")}" style="font-size:{sc.get("hsize", 190)}px" {A("pop", q.at(0.5, 0.6))}>{esc(sc["highlight"])}</div>'
        body += '</div>'
        if sc.get('sub'):
            body += f'<div class="text" {A("up", q.at(0.5))}>{esc(sc["sub"])}</div>'
        if sc.get('deco', True):
            for j, (y, w0, frm) in enumerate([(170, 300, -500), (260, 180, -400), (1040, 420, 1300), (1150, 220, 1200)]):
                ex = 'data-from="{}" data-to="0"'.format(frm)
                deco += f'<div class="deco bleed" style="top:{y}px;left:{90 + (j % 2) * 120}px;width:{w0}px" {A("slide", (0.05 * j, 0.9), ex)}></div>'
        w = words(lines, sc.get('highlight'), sc.get('sub'))
    elif k == 'maths':
        body = f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc.get("kicker", "Do the maths"))}</div><div class="lines">'
        for j, l in enumerate(sc['lines']):
            body += f'<div class="{"big" if j == 0 else "mid"}" style="text-transform:none" {A("up", q.at(0.85))}>{esc(l)}</div>'
        body += '</div>'
        if sc.get('result'):
            body += f'<div class="band bleed" {A("wipe", q.at(0.9, 0.6))}>{esc(sc["result"])}</div>'
        if sc.get('note'):
            body += f'<div class="note" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>'
        w = words(sc['lines'], sc.get('result'), sc.get('note')) + 3
    elif k == 'cards':
        body = (f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc["kicker"])}</div>' if sc.get('kicker') else '') + '<div class="cards">'
        for c in sc['items']:
            body += f'<div class="card {c.get("tone", "")}" {A("left", q.at(0.7))}><div class="lab">{esc(c["label"])}</div><div class="val">{esc(c["value"])}</div></div>'
        body += '</div>'
        if sc.get('note'):
            body += f'<div class="note" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>'
        w = words([c['label'] for c in sc['items']], [c['value'] for c in sc['items']], sc.get('note'), sc.get('kicker'))
    elif k == 'versus':
        body = (f'<div class="big" {A("up", q.at(0.55))}>{esc(sc["top"])}</div>'
                f'<div class="neq" {A("pop", q.at(0.55))}><i></i><b></b><i></i></div>'
                f'<div class="big c-{sc.get("bcolor", "teal")}" {A("up", q.at(0.8))}>{esc(sc["bottom"])}</div>')
        if sc.get('sub'):
            body += f'<div class="text" style="opacity:.75" {A("fade", q.at(0.5))}>{esc(sc["sub"])}</div>'
        if sc.get('pills'):
            body += '<div class="pills">' + ''.join(f'<span class="pill" {A("pop", q.at(0.45))}>{esc(p_)}</span>' for p_ in sc['pills']) + '</div>'
        if sc.get('note'):
            body += f'<div class="note" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>'
        w = words(sc['top'], sc['bottom'], sc.get('sub'), sc.get('pills'), sc.get('note'))
    elif k == 'pills':
        body = (f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc["kicker"])}</div>' if sc.get('kicker') else '')
        body += f'<div class="big" {A("up", q.at(0.6))}>{esc(sc["title"])}</div>' if sc.get('title') else ''
        body += f'<div class="text" style="opacity:.8" {A("fade", q.at(0.5))}>{esc(sc["sub"])}</div>' if sc.get('sub') else ''
        body += '<div class="pills">' + ''.join(f'<span class="pill" {A("pop", q.at(0.45))}>{esc(p_)}</span>' for p_ in sc['pills']) + '</div>'
        body += f'<div class="note" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>' if sc.get('note') else ''
        w = words(sc.get('kicker'), sc.get('title'), sc.get('sub'), sc['pills'], sc.get('note'))
    elif k == 'strike':
        body = f'<div class="mid" {A("up", q.at(0.5))}>{esc(sc["pre"])}</div>'
        shown = q.at(0.9)                       # the words that get crossed out appear
        line = (shown[0] + 0.6, 0.45)           # then the red line draws through them
        q.t = max(q.t, line[0] + 0.75)
        q.end = max(q.end, line[0] + line[1])
        body += (f'<div class="big"><span class="strike" {A("strike", line)}>'
                 f'<span style="display:inline-block" {A("up", shown)}>{esc(sc["struck"])}</span></span></div>')
        if sc.get('post'):
            body += f'<div class="mid" {A("up", q.at(0.6))}>{esc(sc["post"])}</div>'
        if sc.get('big'):
            body += f'<div class="huge c-{sc.get("bigcolor", "navy" if bg in ("teal", "yellow", "paper") else "yellow")}" {A("pop", q.at(0.7, 0.6))}>{esc(sc["big"])}</div>'
        if sc.get('note'):
            body += f'<div class="note" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>'
        w = words(sc['pre'], sc['struck'], sc.get('post'), sc.get('big'), sc.get('note'))
    elif k == 'metric':
        on, of = sc.get('dots', [1, 1])
        dots = ''.join(f'<i class="{"on" if j < on else ""}"></i>' for j in range(of))
        body = (f'<div class="top"><div class="kick" {A("fade", q.at(0.3))}>{esc(sc.get("counter", ""))}</div><div class="dots">{dots}</div></div>'
                f'<div class="big c-{sc.get("color", "teal")}" {A("left", q.at(0.6))}>{esc(sc["title"])}</div>')
        if sc.get('text'):
            body += f'<div class="text" {A("up", q.at(0.6))}>{esc(sc["text"])}</div>'
        if sc.get('bars'):
            body += '<div class="bars">'
            for bb in sc['bars']:
                to = 'data-to="{}"'.format(bb['value'])
                body += (f'<div {A("fade", q.at(0.15))}><div class="barlab">{esc(bb["label"])}</div>'
                         f'<div class="track"><div class="fill {bb.get("tone", "")}" {A("grow", q.at(0.7, 0.9), to)}></div></div></div>')
            body += '</div>'
        if sc.get('note'):
            body += f'<div class="note" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>'
        cls = ' left'
        w = words(sc.get('counter'), sc['title'], sc.get('text'), sc.get('note')) + 2
    elif k == 'grid':
        marked = set(sc.get('marked', [3, 15, 22, 34, 47]))
        n = sc.get('cells', 50)
        body = (f'<div class="big c-{sc.get("color", "teal")}" {A("up", q.at(0.5))}>{esc(sc["title"])}</div>' +
                (f'<div class="text" {A("up", q.at(0.5))}>{esc(sc["text"])}</div>' if sc.get('text') else ''))
        body += '<div class="sq">' + ''.join(f'<i class="{"m" if j in marked else ""}" {A("pop", (q.t + 0.03 * j, 0.35))}></i>' for j in range(n)) + '</div>'
        q.at(0.03 * n + 0.2)
        if sc.get('legend'):
            la, lb = sc['legend']
            body += f'<div class="legend" {A("fade", q.at(0.4))}><span>{esc(la)}</span><span class="m">{esc(lb)}</span></div>'
        if sc.get('note'):
            body += f'<div class="note c-yellow" {A("fade", q.at(0.5))}>{esc(sc["note"])}</div>'
        cls = ' left'
        w = words(sc['title'], sc.get('text'), sc.get('legend'), sc.get('note'))
    elif k == 'list':
        body = (f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc["kicker"])}</div>' if sc.get('kicker') else '')
        body += f'<div class="mid" {A("up", q.at(0.6))}>{esc(sc["title"])}</div>' if sc.get('title') else ''
        body += '<div class="list">' + ''.join(f'<div class="li" {A("left", q.at(0.6))}><b>{j + sc.get("start", 1):02d}</b><span>{esc(x)}</span></div>' for j, x in enumerate(sc['items'])) + '</div>'
        cls = ' left'
        w = words(sc.get('kicker'), sc.get('title'), sc['items'])
    elif k == 'big':
        body = (f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc["kicker"])}</div>' if sc.get('kicker') else '')
        body += f'<div class="{sc.get("size", "big")}" {A("up", q.at(0.7))}>{esc(sc["text"])}</div>'
        body += f'<div class="text" {A("fade", q.at(0.5))}>{esc(sc["sub"])}</div>' if sc.get('sub') else ''
        w = words(sc.get('kicker'), sc['text'], sc.get('sub'))
    elif k == 'end':
        if sc.get('variant', 'follow') == 'book':
            body = (f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc.get("kicker", "Want the full playbook?"))}</div>'
                    f'<div class="book" {A("pop", q.at(0.7, 0.7))}><div class="stripe"></div><div class="bt">Generative AI for Finance Leaders</div><div class="bl"></div>'
                    f'<div class="ba">Christophe Atten</div><div class="burst">NEW<br>BOOK</div></div>'
                    f'<div class="url" {A("up", q.at(0.5))}>{esc(sc.get("url", "christopheatten.com/book"))}</div>')
            if sc.get('sub'):
                body += f'<div class="note" {A("fade", q.at(0.4))}>{esc(sc["sub"])}</div>'
        else:
            body = (f'<div class="kick" {A("fade", q.at(0.4))}>{esc(sc.get("kicker", "Practical AI for finance teams"))}</div>'
                    f'<div class="big" {A("up", q.at(0.6))}>{esc(sc.get("title", "Follow Christophe Atten"))}</div>'
                    f'<div class="text" {A("fade", q.at(0.5))}>{esc(sc.get("sub", "One practical AI idea for finance, every day."))}</div>'
                    f'<div class="url" {A("up", q.at(0.5))}>{esc(sc.get("url", "christopheatten.com"))}</div>')
        w = words(sc.get('kicker'), sc.get('title'), sc.get('sub')) + 4
    elif k == 'html':
        body = sc['html']
        w = sc.get('words', 12)
        q.end = sc.get('reveal', 2.0)
    else:
        raise ValueError(f'unknown scene kind: {k}')
    hold = min(4.2, max(1.6, 0.26 * w))
    dur = sc.get('dur') or round(q.end + hold, 2)
    brand = '' if k == 'end' else '<div class="brand"><span>Christophe Atten</span><span>AI in Finance</span></div>'
    return f'<section class="scene bg-{bg}{cls}" data-dur="{dur}">{deco}<div class="stage">{body}</div>{brand}</section>', dur


def video_html(spec):
    parts, total = [], 0.0
    for i, sc in enumerate(spec['scenes']):
        h, d = scene_html(sc, i, len(spec['scenes']))
        parts.append(h)
        total += d
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_css()}{VIDEO_CSS}{spec.get('css', '')}</style></head>
<body><div id="progress"></div>{''.join(parts)}<script>{ENGINE_JS}</script></body></html>"""
    return doc, total


MEASURE_SCENE = """(i)=>{const s=document.querySelectorAll('.scene')[i];const st=s.querySelector('.stage');
 let bottom=0,right=0,left=1080,top=1350; st.querySelectorAll('*').forEach(e=>{if(e.closest('.bleed'))return;const r=e.getBoundingClientRect(); if(r.width&&r.height&&getComputedStyle(e).opacity!=='0'){bottom=Math.max(bottom,r.bottom);right=Math.max(right,r.right);left=Math.min(left,r.left);top=Math.min(top,r.top)}});
 return {bottom:Math.round(bottom),right:Math.round(right),left:Math.round(left),top:Math.round(top)}}"""


def ffmpeg_bin():
    f = shutil.which('ffmpeg')
    if f:
        return f
    try:
        import imageio_ffmpeg
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-q', 'imageio-ffmpeg'], check=False)
        import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_video(spec, out, name, fps=30):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    doc, total = video_html(spec)
    tmp = tempfile.mkdtemp()
    frames = os.path.join(tmp, 'frames')
    os.makedirs(frames)
    warnings, ends = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = _page(b, dsf=1)
        _load(pg, doc, tmp, 'video.html')
        times = pg.evaluate('window.sceneTimes()')
        total = pg.evaluate('window.__duration')
        # overflow check at the end of each scene, when everything is revealed
        for i, (st, du) in enumerate(times):
            pg.evaluate(f'setT({st + du - 0.05})')
            m = pg.evaluate(MEASURE_SCENE, i)
            if m['bottom'] > 1350 - 105:
                warnings.append(f"scene {i + 1} ({spec['scenes'][i]['kind']}): text runs {m['bottom'] - 1245}px into the bottom margin")
            if m['right'] > 1080 - 40 or m['left'] < 40:
                warnings.append(f"scene {i + 1} ({spec['scenes'][i]['kind']}): text is wider than the frame")
            if m['top'] < 30:
                warnings.append(f"scene {i + 1} ({spec['scenes'][i]['kind']}): text runs off the top")
            shot = os.path.join(tmp, f'end_{i + 1}.jpg')
            pg.screenshot(path=shot, type='jpeg', quality=85)
            ends.append(shot)
        n = int(math.ceil(total * fps))
        for f in range(n):
            pg.evaluate(f'setT({f / fps:.4f})')
            pg.screenshot(path=os.path.join(frames, f'{f:05d}.jpg'), type='jpeg', quality=92)
        pg.evaluate(f'setT({min(1.6, times[0][1] - 0.1):.2f})')
        poster = os.path.join(out, name + '_poster.jpg')
        pg.screenshot(path=poster, type='jpeg', quality=90)
        b.close()
    ff = ffmpeg_bin()
    mp4 = os.path.join(out, name + '.mp4')
    cmd = [ff, '-y', '-v', 'error', '-framerate', str(fps), '-i', os.path.join(frames, '%05d.jpg')]
    if spec.get('music', True):
        sys.path.insert(0, HERE)
        from music import make_track
        wav = os.path.join(tmp, 'music.wav')
        make_track(total, wav, bpm=spec.get('bpm', 112), seed=spec.get('seed', 0))
        cmd += ['-i', wav]
    else:
        cmd += ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000']
    cmd += ['-c:v', 'libx264', '-profile:v', 'high', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', str(fps),
            '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-shortest', '-movflags', '+faststart', mp4]
    subprocess.run(cmd, check=True)
    check = contact_sheet(ends, os.path.join(out, name + '_check.jpg'), cols=min(len(ends), 4), thumb_w=300)
    shutil.rmtree(tmp, ignore_errors=True)
    size = os.path.getsize(mp4)
    if size > 19 * 1024 * 1024:
        warnings.append('video is over 19 MB: shorten it so the preview upload works')
    return {'files': {'video': mp4, 'poster': poster, 'check': check}, 'seconds': round(total, 2), 'scenes': len(times),
            'frames': n, 'megabytes': round(size / 1048576, 2), 'warnings': warnings}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kind', choices=['image', 'carousel', 'video'])
    ap.add_argument('spec')
    ap.add_argument('--out', default='.')
    ap.add_argument('--name', required=True)
    ap.add_argument('--fps', type=int, default=30)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    spec = json.load(open(a.spec, encoding='utf-8'))
    try:
        if a.kind == 'image':
            rep = render_image(spec, a.out, a.name)
        elif a.kind == 'carousel':
            rep = render_carousel(spec, a.out, a.name)
        else:
            rep = render_video(spec, a.out, a.name, a.fps)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'{type(e).__name__}: {e}'}))
        sys.exit(1)
    rep['ok'] = True
    print(json.dumps(rep, indent=1))
    sys.exit(2 if rep['warnings'] else 0)


if __name__ == '__main__':
    main()
