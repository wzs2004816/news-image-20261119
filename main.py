#!/usr/bin/env python3
"""Draw a one-page newspaper front page summing up Thursday 19 November 2026.

Pure Python standard library. No network, no clock, no randomness:
two runs write byte-identical PNGs. Output: $MAKEFUN_OUTPUT_DIR/entry.png
(or /output/entry.png). All text is ASCII; glyphs come from fonts.py,
the land mask from worldmap.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import base64
import struct
import zlib

from fonts import FONTS
from worldmap import WORLD_W, WORLD_H, WORLDMAP

W, H = 1024, 1024

PAPER = (248, 244, 232)
INK = (25, 25, 25)
GREY = (107, 103, 92)
RED = (158, 27, 30)
BLUE = (30, 77, 122)
SKY = (38, 84, 138)
DARKBLUE = (18, 42, 74)
GOLD = (201, 162, 39)
LIGHT = (233, 226, 208)
NEON = (255, 92, 168)
TEAL = (23, 120, 110)


# ---------------------------------------------------------------- PNG writer
def chunk(typ, data):
    c = struct.pack(">I", len(data)) + typ + data
    return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(path, rgb, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.buf = bytearray(bg * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(c)

    def blend(self, x, y, c, a):
        # a: 0..15
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 15:
            self.set(x, y, c)
            return
        i = (y * self.w + x) * 3
        for k in range(3):
            self.buf[i + k] = (self.buf[i + k] * (15 - a) + c[k] * a) // 15

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(row)] = row

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def frame(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def disc(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, c, t=2):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            dx2 = int(max(0, (r - t) * (r - t) - dy * dy) ** 0.5) if abs(dy) < r - t else 0
            if dx > dx2:
                self.rect(cx - dx, cy + dy, dx - dx2, 1, c)
                self.rect(cx + dx2 + 1, cy + dy, dx - dx2, 1, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def polygon(self, pts, c):
        # scanline fill
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, yy1 = pts[i]
                x2, yy2 = pts[(i + 1) % n]
                if (yy1 <= y < yy2) or (yy2 <= y < yy1):
                    xs.append(x1 + (y - yy1) * (x2 - x1) / (yy2 - yy1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(int(xs[k]), y, max(1, int(xs[k + 1]) - int(xs[k])), 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        pts = []
        import math
        for k in range(48):
            a = 2 * math.pi * k / 48
            pts.append((int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a))))
        self.polygon(pts, c)


# -------------------------------------------------------------------- fonts
def decode_font(b64):
    raw = zlib.decompress(base64.b64decode(b64))
    n = raw[0]
    glyphs = {}
    o = 1
    for _ in range(n):
        code, adv, w, h, dx, dy = raw[o:o + 6]
        o += 6
        if dy >= 128:
            dy -= 256
        if dx >= 128:
            dx -= 256
        nb = (w * h + 1) // 2
        glyphs[code] = (adv, w, h, dx, dy, raw[o:o + nb])
        o += nb
    return glyphs


FONTS_D = {name: decode_font(b64) for name, b64 in FONTS.items()}


def text_width(font, s):
    g = FONTS_D[font]
    return sum(g[ord(ch)][0] for ch in s if ord(ch) in g)


def draw_text(cv, x, y, s, font, color):
    """Draw s with its baseline at y, left edge x. Returns width drawn."""
    g = FONTS_D[font]
    cx = x
    for ch in s:
        code = ord(ch)
        if code not in g:
            continue
        adv, w, h, dx, dy, data = g[code]
        for row in range(h):
            for col in range(w):
                idx = row * w + col
                nib = (data[idx // 2] >> (4 if idx % 2 == 0 else 0)) & 0xF
                if nib:
                    cv.blend(cx + dx + col, y + dy + row, color, nib)
        cx += adv
    return cx - x


def draw_text_c(cv, cx, y, s, font, color):
    draw_text(cv, cx - text_width(font, s) // 2, y, s, font, color)


def wrap(s, font, maxw):
    words = s.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_width(font, trial) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(cv, x, y, s, font, color, maxw, leading):
    lines = wrap(s, font, maxw)
    for ln in lines:
        draw_text(cv, x, y, ln, font, color)
        y += leading
    return y


# -------------------------------------------------------------- illustrations
def star(cv, cx, cy, r, c):
    # 5-point star as a small polygon
    import math
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.42
        pts.append((int(cx + rr * math.cos(ang)), int(cy + rr * math.sin(ang))))
    cv.polygon(pts, c)


def flag_us(cv, x, y, w, h):
    stripe = max(1, h // 13)
    for i in range(13):
        cv.rect(x, y + i * stripe, w, stripe, (178, 34, 52) if i % 2 == 0 else (255, 255, 255))
    cw, ch = int(w * 0.4), stripe * 7
    cv.rect(x, y, cw, ch, (30, 50, 110))
    for r in range(4):
        for c in range(5):
            cv.disc(x + 5 + c * (cw - 8) // 4, y + 4 + r * (ch - 8) // 3, 1, (255, 255, 255))


def flag_cn(cv, x, y, w, h):
    cv.rect(x, y, w, h, (222, 41, 16))
    star(cv, x + w // 5, y + h // 4, max(3, h // 5), (255, 222, 0))
    for sx, sy in ((0.55, 0.12), (0.68, 0.28), (0.68, 0.5), (0.55, 0.66)):
        star(cv, x + int(w * sx), y + int(h * sy), max(2, h // 10), (255, 222, 0))


def flag_ru(cv, x, y, w, h):
    third = max(1, h // 3)
    cv.rect(x, y, w, third, (255, 255, 255))
    cv.rect(x, y + third, w, third, (0, 57, 166))
    cv.rect(x, y + 2 * third, w, h - 2 * third, (213, 0, 50))


def hero_shenzhen(cv, x, y, w, h):
    # sky, skyline, round table, three flags
    cv.rect(x, y, w, h, SKY)
    cv.disc(x + w - 30, y + 22, 12, (255, 214, 130))
    cv.rect(x, y + h - 34, w, 34, DARKBLUE)
    for bx, bw, bh in ((8, 26, 26), (42, 18, 40), (66, 30, 20), (104, 16, 34),
                       (128, 34, 46), (170, 20, 30), (198, 28, 42), (234, 18, 24),
                       (258, 30, 36), (292, 16, 26)):
        cv.rect(x + bx, y + h - 34 - bh, bw, bh, (12, 30, 56))
        for wy in range(y + h - 34 - bh + 4, y + h - 38, 8):
            for wx in range(x + bx + 4, x + bx + bw - 3, 8):
                cv.rect(wx, wy, 2, 3, (255, 214, 130))
    cv.ellipse(x + w // 2, y + h - 10, 108, 12, (122, 72, 32))
    cv.ellipse(x + w // 2, y + h - 13, 108, 10, (150, 96, 48))
    for i, flag in enumerate((flag_us, flag_cn, flag_ru)):
        fx = x + 46 + i * 100
        cv.vline(fx + 14, y + h - 52, 34, INK, 2)
        flag(cv, fx, y + h - 52, 30, 20)


def hero_icj(cv, x, y, w, h):
    cv.rect(x, y, w, h, (214, 205, 178))
    # courthouse: pediment + columns + steps
    cx = x + w // 2
    cv.polygon([(cx - 118, y + 36), (cx + 118, y + 36), (cx, y + 8)], (96, 84, 66))
    cv.disc(cx, y + 24, 7, GOLD)
    cv.rect(x + 28, y + 36, w - 56, 5, (96, 84, 66))
    for i in range(5):
        colx = x + 44 + i * 56
        cv.rect(colx, y + 41, 14, 30, (240, 234, 218))
        cv.rect(colx - 3, y + 39, 20, 4, (240, 234, 218))
    cv.rect(x + 20, y + 71, w - 40, 4, (120, 108, 88))
    cv.rect(x + 12, y + 75, w - 24, 3, (140, 128, 106))
    # scales of justice, foreground right
    sx, sy = x + w - 58, y + h - 22
    cv.vline(sx, sy - 22, 22, INK, 2)
    cv.line(sx - 18, sy - 22, sx + 18, sy - 22, INK)
    cv.disc(sx, sy - 24, 2, INK)
    for dx in (-18, 18):
        cv.line(sx + dx, sy - 22, sx + dx, sy - 10, INK)
        cv.polygon([(sx + dx - 9, sy - 10), (sx + dx + 9, sy - 10), (sx + dx, sy - 2)], GOLD)


def hero_gta(cv, x, y, w, h):
    cv.rect(x, y, w, h, (26, 10, 44))
    cv.disc(x + w // 2, y + 40, 30, NEON)
    cv.disc(x + w // 2, y + 40, 23, (255, 150, 200))
    # neon skyline
    cv.rect(x, y + h - 40, w, 40, (10, 6, 24))
    for bx, bw, bh in ((6, 30, 28), (44, 20, 44), (72, 34, 20), (114, 18, 36),
                       (140, 28, 46), (176, 22, 30), (206, 30, 40), (244, 20, 24),
                       (272, 30, 34)):
        cv.rect(x + bx, y + h - 40 - bh, bw, bh, (38, 18, 66))
        for wy in range(y + h - 40 - bh + 6, y + h - 44, 10):
            for wx in range(x + bx + 4, x + bx + bw - 3, 9):
                cv.rect(wx, wy, 2, 3, NEON if (wx + wy) % 3 else (90, 230, 255))
    # palm silhouettes
    for px in (x + 18, x + w - 22):
        cv.vline(px, y + h - 66, 28, (8, 40, 24), 3)
        for dx, dy in ((-14, -8), (-8, -14), (0, -16), (8, -14), (14, -8)):
            cv.line(px, y + h - 66, px + dx, y + h - 66 + dy, (8, 40, 24))
    draw_text(cv, x + w // 2 - text_width("serif_bold_56", "VI") // 2,
              y + 74, "VI", "serif_bold_56", (255, 255, 255))


# ---------------------------------------------------------------- mid icons
def icon_chart(cv, x, y, s):
    cv.frame(x, y, s, s, INK, 2)
    bars = (10, 18, 14, 26)
    for i, bh in enumerate(bars):
        cv.rect(x + 5 + i * 8, y + s - 4 - bh, 5, bh, BLUE if i < 3 else RED)


def icon_flame(cv, x, y, s):
    cv.polygon([(x + s // 2, y + 2), (x + s - 4, y + s // 2),
                (x + s - 6, y + s - 4), (x + 6, y + s - 4), (x + 4, y + s // 2)],
               (230, 90, 20))
    cv.polygon([(x + s // 2, y + 12), (x + s - 10, y + s - 8),
                (x + 10, y + s - 8)], (255, 190, 40))


def icon_flags(cv, x, y, s):
    cv.line(x + 6, y + 4, x + s - 10, y + s - 8, INK)
    cv.line(x + s - 10, y + 4, x + 6, y + s - 8, INK)
    cv.rect(x + 4, y + 2, 12, 8, (0, 120, 60))
    cv.rect(x + s - 16, y + 2, 12, 8, (0, 80, 160))


def icon_bridge(cv, x, y, s):
    cv.rect(x, y + s - 8, s, 8, (90, 140, 200))
    cv.polygon([(x + 2, y + s - 10), (x + s // 2, y + 6), (x + s - 2, y + s - 10)],
               (120, 120, 120))
    cv.line(x + 2, y + s - 12, x + s - 2, y + s - 12, INK)


def icon_cyclone(cv, x, y, s):
    cx, cy = x + s // 2, y + s // 2
    for r in (4, 8, 12, 15):
        cv.ring(cx, cy, r, TEAL if r % 8 else BLUE, 2)
    cv.disc(cx, cy, 3, RED)


def icon_atom(cv, x, y, s):
    cx, cy = x + s // 2, y + s // 2
    cv.ellipse(cx, cy, 15, 6, BLUE)
    cv.ellipse(cx, cy, 6, 15, BLUE)
    cv.disc(cx, cy, 4, RED)


# ----------------------------------------------------------------- world map
def decode_map():
    raw = zlib.decompress(base64.b64decode(WORLDMAP))
    cells = []
    for i in range(WORLD_W * WORLD_H):
        byte = raw[i // 8]
        cells.append((byte >> (7 - i % 8)) & 1)
    return cells


def draw_map(cv, x, y, pitch, dot, land_color, mark_color, marks, max_rows=None):
    cells = decode_map()
    rows = WORLD_H if max_rows is None else min(max_rows, WORLD_H)
    for row in range(rows):
        for col in range(WORLD_W):
            if cells[row * WORLD_W + col]:
                cv.disc(x + col * pitch + pitch // 2, y + row * pitch + pitch // 2,
                        dot, land_color)
    for lon, lat in marks:
        mx = x + int((lon + 180.0) / 360.0 * WORLD_W * pitch)
        my = y + int((90.0 - lat) / 180.0 * WORLD_H * pitch)
        cv.disc(mx, my, dot + 2, mark_color)
        cv.ring(mx, my, dot + 4, mark_color, 1)


# --------------------------------------------------------------------- build
HEROES = [
    ("SHENZHEN  |  DIPLOMACY", "TRUMP MEETS XI AND PUTIN",
     "First three-way summit ends with a pledge: a nuclear war cannot be won and must never be fought.",
     hero_shenzhen),
    ("THE HAGUE  |  JUSTICE", "MYANMAR GUILTY OF GENOCIDE",
     "The UN's top court rules Myanmar committed genocide against the Rohingya, the first state ever found guilty.",
     hero_icj),
    ("VICE CITY  |  GAMES", "GTA VI ARRIVES AT LAST",
     "After a 13-year wait, Grand Theft Auto VI launches worldwide at midnight, back in Vice City on PS5 and Xbox.",
     hero_gta),
]

MIDS = [
    ("ANT debuts on the Nasdaq",
     "Opens $111.50, closes $97.17, up 17%.", icon_chart),
    ("Gulf war widens",
     "Missile hits Riyadh tower; tanker hit off Oman.", icon_flame),
    ("Ethiopia and Eritrea on the brink",
     "Shelling near Badme raises fear of full war.", icon_flags),
    ("Crimea bridge hit again",
     "Third strike in a week; rail traffic halted.", icon_bridge),
    ("Cyclone Akvan nears India",
     "Odisha evacuates 50,000 ahead of the storm.", icon_cyclone),
    ("North Korea expands Yongbyon",
     "Uranium plant grows, says UN watchdog.", icon_atom),
]

ALSO = [
    ("KUMAMOTO", "M5.7 quake jolts Japan; two hurt"),
    ("ROOPPUR", "Bangladesh starts nuclear power"),
    ("E1 DELAYED", "Israel pauses West Bank plan"),
    ("SPAIN", "Snap election set for 29 November"),
    ("LONDON", "UK inflation hits 3.6%, a 1-year high"),
    ("GENEVA", "WHO warns drug resistance rising"),
    ("SHENZHOU-24", "First Pakistani astronaut to fly"),
    ("SEOUL", "Ex-PM Han faces retrial over martial law"),
    ("RAKUTEN", "Broker scrambles after data breach"),
    ("TOKYO", "Japan Tobacco takes $8.9bn Russia hit"),
    ("MANILA", "Trump and Marcos hail alliance"),
    ("IGNITE", "Microsoft unveils new AI models"),
    ("TOKYO", "Bank of Japan rate rise expected"),
    ("SPACE", "NASA confirms Voyager 1 a light-day out"),
    ("WALL ST", "Walmart slips; Palo Alto climbs"),
    ("SUDAN", "School strike kills 16 in Kordofan"),
    ("BRASILIA", "Brazil approves fiscal package"),
    ("BERLIN", "Germany bans Hells Angels chapter"),
    ("CYBER", "Governments warn of Java flaw"),
    ("FAITH", "Islam set to be largest religion by 2035"),
]

TIMELINE = [
    ("05:00", "GTA VI unlocks across the US at midnight"),
    ("10:31", "ICJ: Myanmar guilty of Rohingya genocide"),
    ("14:30", "Anthropic starts trading on the Nasdaq"),
    ("16:58", "New attack reported on the Crimea bridge"),
    ("19:05", "M5.7 quake jolts Kumamoto, Japan"),
]

# lon/lat of the marked places on the map
MARKS = [(114.1, 22.5), (4.3, 52.1), (-74.0, 40.7), (56.5, 26.5),
         (38.9, 9.0), (36.5, 45.3), (85.8, 20.3), (126.3, 39.8)]


def build():
    cv = Canvas(W, H, PAPER)
    MX = 24
    CW = W - 2 * MX  # 976

    # ---- masthead
    y = 10
    draw_text_c(cv, W // 2, y + 52, "THE WORLD IN ONE DAY", "serif_bold_56", INK)
    y = 74
    cv.hline(MX, y, CW, INK, 2)
    cv.hline(MX, y + 4, CW, INK, 1)
    y = 100
    draw_text(cv, MX, y, "THURSDAY 19 NOVEMBER 2026", "sans_bold_13", RED)
    draw_text(cv, W - MX - text_width("sans_bold_13", "29 STORIES  |  6 REGIONS  |  1 DAY"),
              y, "29 STORIES  |  6 REGIONS  |  1 DAY", "sans_bold_13", INK)

    # ---- heroes: 3 columns
    y = 108
    colw = (CW - 40) // 3  # 312
    for i, (tag, head, body, draw) in enumerate(HEROES):
        x = MX + i * (colw + 20)
        draw(cv, x, y, colw, 88)
        ty = y + 106
        draw_text(cv, x, ty, tag, "sans_bold_13", RED)
        hy = ty + 30
        for ln in wrap(head, "serif_bold_26", colw):
            draw_text(cv, x, hy, ln, "serif_bold_26", INK)
            hy += 30
        by = hy + 6
        draw_wrapped(cv, x, by, body, "serif_19", INK, colw, 23)

    # ---- mids: 2 rows x 3 columns
    y = 392
    for r in range(2):
        for c in range(3):
            idx = r * 3 + c
            head, body, icon = MIDS[idx]
            x = MX + c * (colw + 20)
            my = y + r * 104
            icon(cv, x, my + 4, 34)
            tx = x + 44
            tw = colw - 44
            hy = my + 20
            for ln in wrap(head, "serif_bold_19", tw):
                draw_text(cv, tx, hy, ln, "serif_bold_19", INK)
                hy += 23
            draw_wrapped(cv, tx, hy + 2, body, "serif_19", GREY, tw, 22)
    cv.hline(MX, y + 100, CW, LIGHT, 1)

    # ---- also list
    y = 612
    cv.rect(MX, y, CW, 2, INK)
    y += 24
    draw_text(cv, MX, y, "ALSO ON THURSDAY 19 NOVEMBER", "sans_bold_13", INK)
    dc = "DATE CHECK: EVERY STORY HAPPENED OR WAS FIRST REPORTED ON 19 NOVEMBER 2026"
    draw_text(cv, W - MX - text_width("sans_bold_13", dc), y, dc, "sans_bold_13", RED)
    y += 10
    half = CW // 2  # 488
    for i, (lead, text) in enumerate(ALSO):
        col = 0 if i < 10 else 1
        row = i if i < 10 else i - 10
        x = MX + col * half
        ly = y + 20 + row * 19
        draw_text(cv, x, ly, lead + ":", "sans_bold_13", RED)
        lx = x + text_width("sans_bold_13", lead + ": ") + 2
        draw_text(cv, lx, ly, text, "serif_19", INK)

    # ---- bottom band: timeline + map
    y = 854
    cv.rect(MX, y, CW, 2, INK)
    y += 22
    draw_text(cv, MX, y, "THE DAY IN FIVE MOMENTS  (UTC)", "sans_bold_13", INK)
    ty = y + 22
    for t, text in TIMELINE:
        draw_text(cv, MX, ty, t, "sans_bold_13", RED)
        draw_text(cv, MX + 52, ty, text, "serif_19", INK)
        ty += 19
    draw_text(cv, MX, ty + 6,
              "SOURCES: AP, REUTERS, WSJ, CNN, AL JAZEERA, LE MONDE, JAPAN TIMES",
              "sans_bold_13", GREY)
    # map, right side (rows 0..49: drops Antarctica only)
    mapx = MX + 600
    draw_text(cv, mapx, y, "WHERE THE NEWS FELL", "sans_bold_13", INK)
    draw_map(cv, mapx + 40, y + 12, 2, 1, (90, 110, 140), RED, MARKS, max_rows=50)
    my = y + 12 + 50 * 2 + 8
    draw_text(cv, mapx, my, "N AM 6  |  S AM 1  |  EUR 6", "sans_bold_13", INK)
    draw_text(cv, mapx, my + 16, "MID EAST 2  |  AFR 2  |  ASIA 12", "sans_bold_13", INK)
    return cv


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    cv = build()
    write_png(os.path.join(outdir, "entry.png"), cv.buf, W, H)


if __name__ == "__main__":
    main()
