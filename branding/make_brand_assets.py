"""Generates the WebPulse logo, mark and favicon set (run once; outputs are committed).

    python branding/make_brand_assets.py

Design: a rounded teal square ("the monitor") with a white pulse/heartbeat line ("a change detected").
Everything is drawn from the same geometry so the SVGs and the PNG/ICO favicons match exactly.
Original artwork made for WebPulse - not derived from any upstream asset.
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, '..', 'changedetectionio', 'static')
TEAL = '#0d9488'
TEAL_DARK = '#0f766e'
INK = '#0f172a'
# Pulse line in a 64x64 box: flat - small dip - tall spike - deep dip - recovery - flat
PULSE = [(12, 34), (22, 34), (26, 28), (31, 46), (37, 16), (42, 38), (45, 34), (52, 34)]


def svg_mark(size=64, mono=False):
    pts = ' '.join(f'{x},{y}' for x, y in PULSE)
    fill = '#000' if mono else 'url(#wp-g)'
    stroke = '#fff'
    defs = '' if mono else (f'<defs><linearGradient id="wp-g" x1="0" y1="0" x2="1" y2="1">'
                            f'<stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{TEAL_DARK}"/>'
                            f'</linearGradient></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}" role="img" '
            f'aria-label="WebPulse">{defs}<rect x="2" y="2" width="60" height="60" rx="15" fill="{fill}"/>'
            f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="5" stroke-linecap="round" '
            f'stroke-linejoin="round"/></svg>')


def svg_logo():
    pts = ' '.join(f'{x},{y}' for x, y in PULSE)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 236 64" width="236" height="64" role="img" aria-label="WebPulse">'
            f'<defs><linearGradient id="wp-lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{TEAL}"/>'
            f'<stop offset="1" stop-color="{TEAL_DARK}"/></linearGradient></defs>'
            f'<rect x="2" y="2" width="60" height="60" rx="15" fill="url(#wp-lg)"/>'
            f'<polyline points="{pts}" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
            '<text x="76" y="43" font-family="Segoe UI, system-ui, -apple-system, Roboto, Arial, sans-serif" font-size="30" '
            f'font-weight="600" fill="{INK}">Web<tspan font-weight="800" fill="{TEAL}">Pulse</tspan></text></svg>')


def png_mark(px, pad_ratio=0.0, background=None):
    """Raster version of svg_mark at px x px (4x supersampled)."""
    ss = 4
    big = px * ss
    img = Image.new('RGBA', (big, big), background or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(big * pad_ratio)
    s = (big - 2 * pad) / 64.0
    # vertical gradient approximation of the teal square
    top, bot = (13, 148, 136), (15, 118, 110)
    box = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    for y in range(big):
        t = y / max(1, big - 1)
        bd.line([(0, y), (big, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    mask = Image.new('L', (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([pad + 2 * s, pad + 2 * s, pad + 62 * s, pad + 62 * s], radius=15 * s, fill=255)
    img.paste(box, (0, 0), mask)
    pts = [(pad + x * s, pad + y * s) for x, y in PULSE]
    w = max(1, int(5 * s))
    d.line(pts, fill=(255, 255, 255, 255), width=w, joint='curve')
    r = w / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))
    return img.resize((px, px), Image.LANCZOS)


def main():
    img_dir = os.path.join(STATIC, 'images')
    fav = os.path.join(STATIC, 'favicons')
    open(os.path.join(img_dir, 'webpulse-mark.svg'), 'w').write(svg_mark())
    open(os.path.join(img_dir, 'webpulse-logo.svg'), 'w').write(svg_logo())
    open(os.path.join(fav, 'safari-pinned-tab.svg'), 'w').write(svg_mark(mono=True))
    png_mark(16).save(os.path.join(fav, 'favicon-16x16.png'))
    png_mark(32).save(os.path.join(fav, 'favicon-32x32.png'))
    png_mark(180, background=(255, 255, 255, 255), pad_ratio=0.06).save(os.path.join(fav, 'apple-touch-icon.png'))
    png_mark(192).save(os.path.join(fav, 'android-chrome-192x192.png'))
    png_mark(256).save(os.path.join(fav, 'android-chrome-256x256.png'))
    png_mark(256, background=(13, 148, 136, 255), pad_ratio=0.12).save(os.path.join(fav, 'android-chrome-256x256-maskable.png'))
    png_mark(150, pad_ratio=0.15).save(os.path.join(fav, 'mstile-150x150.png'))
    png_mark(256).save(os.path.join(img_dir, 'avatar-256x256.png'))
    png_mark(64).save(os.path.join(fav, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print('WebPulse brand assets written')


if __name__ == '__main__':
    main()
