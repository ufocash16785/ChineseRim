"""小型像素畫布：以「部位」為單位作畫，最後自動加邊緣光影與外框。"""
from PIL import Image

OUTLINE = (38, 26, 42)


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(c, t=.28):
    return mix(c, (255, 255, 255), t)


def darken(c, t=.32):
    return mix(c, (20, 10, 40), t)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = {}          # (x,y) -> (rgb, part)

    def put(self, x, y, c, part="x"):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[(x, y)] = (c, part)

    def rect(self, x0, y0, x1, y1, c, part="x"):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.put(x, y, c, part)

    def ellipse(self, cx, cy, rx, ry, c, part="x"):
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if ((x - cx) / (rx + .3)) ** 2 + ((y - cy) / (ry + .3)) ** 2 <= 1:
                    self.put(x, y, c, part)

    def line(self, x0, y0, x1, y1, c, part="x", th=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            for t in range(th):
                self.put(x0, y0 + t, c, part)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, c, part="x"):
        """實心多邊形（掃描線）。"""
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % n]
                if (ya <= y + .5 < yb) or (yb <= y + .5 < ya):
                    xs.append(xa + (y + .5 - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(int(round(xs[i])), int(round(xs[i + 1]))):
                    self.put(x, y, c, part)

    def stamp(self, other, ox=0, oy=0):
        for (x, y), v in other.px.items():
            self.put(x + ox, y + oy, *v)

    # ---- 後處理 ----
    def finish(self, outline=True, shade=True, shade_parts=None):
        src = dict(self.px)
        out = {}
        for (x, y), (c, part) in src.items():
            col = c
            if shade and (shade_parts is None or part in shade_parts):
                up = src.get((x, y - 1))
                left = src.get((x - 1, y))
                dn = src.get((x, y + 1))
                rt = src.get((x + 1, y))
                if up is None or left is None:
                    col = lighten(c, .22)
                elif dn is None or rt is None:
                    col = darken(c, .22)
            out[(x, y)] = col
        if outline:
            for (x, y) in list(src):
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    p = (x + dx, y + dy)
                    if p not in src and p not in out and 0 <= p[0] < self.w and 0 <= p[1] < self.h:
                        out[p] = OUTLINE
        return out

    def image(self, **kw):
        im = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for (x, y), c in self.finish(**kw).items():
            im.putpixel((x, y), tuple(c) + (255,))
        return im


def sheet(frames_by_row, fw, fh):
    """frames_by_row: list of (name, [Image...])；回傳 (Image, meta)。"""
    cols = max(len(f) for _, f in frames_by_row)
    im = Image.new("RGBA", (cols * fw, len(frames_by_row) * fh), (0, 0, 0, 0))
    meta = {"frameW": fw, "frameH": fh, "anims": {}}
    for r, (name, frames) in enumerate(frames_by_row):
        for c, f in enumerate(frames):
            im.paste(f, (c * fw, r * fh))
        meta["anims"][name] = {"row": r, "n": len(frames)}
    return im, meta
