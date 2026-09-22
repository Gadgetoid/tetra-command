"""Type specimen: the same text through .af and through real TTF/OTF."""

import builtins, picovector, host
for _n in ("image", "color", "shape", "rect", "vec2", "mat3", "brush", "font"):
    setattr(builtins, _n, getattr(picovector, _n))
W, H = host.size()
builtins.screen = picovector.image(W, H, host.framebuffer())
screen.antialias = image.X4

# Lexend both ways, which is the comparison this page is for. It was SF and
# Georgia once; neither is redistributable, so neither is in the repo.
af = font.load("fonts/lexend-regular.af")
light = font.load("fonts/Lexend[wght].ttf", variations={"wght": 300})
heavy = font.load("fonts/Lexend[wght].ttf", variations={"wght": 800})
seven = font.load("fonts/DSEG7Classic-Bold.ttf")

PANGRAM = "The quick brown fox jumps over the lazy dog"
GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefg 0123456789 &@#?!%"

BG    = color.rgb(16, 17, 22)
LABEL = color.rgb(118, 126, 148)
RULE  = color.rgb(38, 41, 52)

FACES = [
    (af,      "alright-fonts .af  -  128/em, quantised", color.rgb(236, 239, 248)),
    (light,   "FreeType  Lexend variable  wght=300",     color.rgb(86, 224, 205)),
    (heavy,   "FreeType  Lexend variable  wght=800",     color.rgb(196, 202, 218)),
    (seven,   "FreeType  DSEG7 Classic Bold",            color.rgb(238, 168, 60)),
]

MARGIN = 44
COL_W = W - MARGIN * 2


def fit(face, text, max_w, cap):
    """Return the largest size at or under `cap` that keeps `text` inside `max_w`."""
    screen.font = face
    width = screen.measure_text(text, font_size=cap)[0]
    if width <= 0:
        return cap
    return cap if width <= max_w else max(8, int(cap * max_w / width))


LAYOUT = []
for face, label, pen in FACES:
    LAYOUT.append((face, label, pen,
                   fit(face, PANGRAM, COL_W, 52),
                   fit(face, GLYPHS, COL_W, 34)))

row_h = (H - 40) // len(LAYOUT)
n = 0

while True:
    screen.pen = BG
    screen.clear()

    y = 30
    for face, label, pen, big, small in LAYOUT:
        screen.font = af
        screen.pen = LABEL
        screen.text(label, vec2(MARGIN, y + 18), 21)

        screen.font = face
        screen.pen = pen
        screen.text(PANGRAM, vec2(MARGIN, y + 30 + big), big)
        screen.pen = LABEL
        screen.text(GLYPHS, vec2(MARGIN, y + 44 + big + small), small)

        screen.pen = RULE
        screen.rectangle(rect(MARGIN, y + row_h - 14, COL_W, 1))
        y += row_h

    n += 1
    if n == 1:
        print("specimen sizes:", [(l[3], l[4]) for l in LAYOUT])
    host.present()
