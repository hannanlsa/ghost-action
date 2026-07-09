#!/usr/bin/env python3
"""GhostAction Icon Generator v2 - With AI void elements"""

from PIL import Image, ImageDraw, ImageFilter
import math
import random
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(OUTPUT_DIR, exist_ok=True)

random.seed(42)


def draw_glow_circle(draw, cx, cy, r, color, alpha_max=180, layers=6):
    for i in range(layers, 0, -1):
        ratio = i / layers
        a = int(alpha_max * (1 - ratio) * 0.5)
        rr = int(r * (0.5 + 0.5 * ratio))
        c = (*color[:3], a)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c)


def draw_neural_node(draw, x, y, r, color, alpha=200):
    draw.ellipse([x - r, y - r, x + r, y + r], fill=(*color[:3], alpha))
    inner_r = max(1, int(r * 0.4))
    draw.ellipse([x - inner_r, y - inner_r, x + inner_r, y + inner_r], fill=(*color[:3], min(255, alpha + 55)))


def draw_data_stream(draw, x1, y1, x2, y2, color, alpha=60, dots=8):
    for i in range(dots):
        t = i / dots
        px = int(x1 + (x2 - x1) * t)
        py = int(y1 + (y2 - y1) * t)
        r = max(1, int(3 * (1 - abs(t - 0.5) * 2)))
        a = int(alpha * (1 - abs(t - 0.5) * 2))
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(*color[:3], a))


def draw_circuit_line(draw, points, color, alpha=40, width=1):
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(*color[:3], alpha), width=width)


def draw_ghost_icon(size=512):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    s = size / 512

    bg_deep = (12, 8, 30, 255)
    bg_mid = (25, 15, 55, 255)
    ghost_body = (100, 80, 200, 255)
    ghost_highlight = (140, 120, 235, 255)
    ghost_shadow = (65, 50, 150, 255)
    ghost_glow = (120, 90, 220, 50)
    eye_white = (255, 255, 255, 255)
    eye_pupil = (20, 12, 45, 255)
    accent_cyan = (0, 220, 255, 255)
    accent_glow = (0, 180, 255, 80)
    play_color = (0, 255, 200, 255)
    ai_purple = (160, 80, 255)
    ai_cyan = (0, 200, 240)
    ai_pink = (255, 80, 200)
    ai_gold = (255, 200, 60)

    margin = int(20 * s)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(100 * s),
        fill=bg_deep,
    )

    for gx in range(0, size, max(1, int(4 * s))):
        for gy in range(0, size, max(1, int(4 * s))):
            dx = gx - cx
            dy = gy - cy
            dist = math.sqrt(dx * dx + dy * dy)
            max_dist = size * 0.45
            if dist < max_dist:
                noise = random.random() * 0.3
                val = (1 - dist / max_dist) * 0.15 + noise * 0.05
                a = int(val * 255)
                if a > 5:
                    r_comp = int(25 + 20 * val)
                    g_comp = int(15 + 10 * val)
                    b_comp = int(55 + 30 * val)
                    draw.rectangle(
                        [gx, gy, gx + max(1, int(3 * s)), gy + max(1, int(3 * s))],
                        fill=(r_comp, g_comp, b_comp, min(a, 40)),
                    )

    neural_nodes = []
    for _ in range(18):
        nx = random.randint(int(50 * s), int(462 * s))
        ny = random.randint(int(50 * s), int(462 * s))
        dx = nx - cx
        dy = ny - cy
        if math.sqrt(dx * dx + dy * dy) > int(180 * s):
            nr = random.randint(int(2 * s), int(5 * s))
            nc = random.choice([ai_purple, ai_cyan, ai_pink])
            na = random.randint(40, 120)
            draw_neural_node(draw, nx, ny, nr, nc, na)
            neural_nodes.append((nx, ny))

    for i in range(len(neural_nodes)):
        for j in range(i + 1, len(neural_nodes)):
            n1 = neural_nodes[i]
            n2 = neural_nodes[j]
            d = math.sqrt((n1[0] - n2[0]) ** 2 + (n1[1] - n2[1]) ** 2)
            if d < int(200 * s):
                lc = random.choice([ai_purple, ai_cyan])
                draw_circuit_line(draw, [n1, n2], lc, alpha=25, width=max(1, int(1 * s)))

    for _ in range(12):
        sx = random.randint(int(60 * s), int(452 * s))
        sy = random.randint(int(60 * s), int(452 * s))
        dx = sx - cx
        dy = sy - cy
        if math.sqrt(dx * dx + dy * dy) > int(160 * s):
            ex = sx + random.randint(int(-80 * s), int(80 * s))
            ey = sy + random.randint(int(-80 * s), int(80 * s))
            sc = random.choice([ai_cyan, ai_purple, ai_pink])
            draw_data_stream(draw, sx, sy, ex, ey, sc, alpha=50, dots=random.randint(5, 10))

    for _ in range(6):
        hx = random.randint(int(80 * s), int(432 * s))
        hy = random.randint(int(80 * s), int(432 * s))
        hr = random.randint(int(15 * s), int(40 * s))
        hc = random.choice([ai_purple, ai_cyan])
        draw_glow_circle(draw, hx, hy, hr, hc, alpha_max=30, layers=4)

    draw_glow_circle(draw, int(cx - int(10 * s)), int(220 * s), int(130 * s), (100, 70, 200), alpha_max=40, layers=8)

    ghost_cx = cx - int(10 * s)
    ghost_top = int(100 * s)
    ghost_width = int(200 * s)
    ghost_bottom = int(340 * s)
    head_radius = int(100 * s)

    head_cx = ghost_cx
    head_cy = ghost_top + head_radius

    draw.ellipse(
        [head_cx - head_radius, head_cy - head_radius,
         head_cx + head_radius, head_cy + head_radius],
        fill=ghost_body,
    )

    body_left = ghost_cx - ghost_width // 2
    body_right = ghost_cx + ghost_width // 2
    draw.rectangle(
        [body_left, head_cy, body_right, ghost_bottom],
        fill=ghost_body,
    )

    highlight_offset = int(15 * s)
    highlight_r = int(75 * s)
    draw.ellipse(
        [head_cx - highlight_r - highlight_offset, head_cy - highlight_r - int(10 * s),
         head_cx + highlight_r - highlight_offset, head_cy + highlight_r - int(10 * s)],
        fill=ghost_highlight,
    )

    wave_count = 5
    wave_width = ghost_width / wave_count
    for i in range(wave_count):
        wx = body_left + i * wave_width
        wave_cx = wx + wave_width / 2
        wave_r = wave_width / 2
        if i % 2 == 0:
            draw.ellipse(
                [wave_cx - wave_r, ghost_bottom - wave_r,
                 wave_cx + wave_r, ghost_bottom + wave_r],
                fill=ghost_body,
            )
        else:
            draw.ellipse(
                [wave_cx - wave_r, ghost_bottom - wave_r,
                 wave_cx + wave_r, ghost_bottom + wave_r],
                fill=bg_deep,
            )

    draw.ellipse(
        [wave_cx - wave_r, ghost_bottom - wave_r,
         wave_cx + wave_r, ghost_bottom + wave_r],
        fill=ghost_body,
    )

    eye_y = head_cy - int(5 * s)
    eye_spacing = int(35 * s)
    eye_rx = int(22 * s)
    eye_ry = int(28 * s)

    for side in [-1, 1]:
        ex = ghost_cx + side * eye_spacing
        draw.ellipse(
            [ex - eye_rx, eye_y - eye_ry, ex + eye_rx, eye_y + eye_ry],
            fill=eye_white,
        )
        pupil_r = int(12 * s)
        pupil_offset_x = int(4 * s)
        pupil_offset_y = int(2 * s)
        draw.ellipse(
            [ex + pupil_offset_x - pupil_r, eye_y + pupil_offset_y - pupil_r,
             ex + pupil_offset_x + pupil_r, eye_y + pupil_offset_y + pupil_r],
            fill=eye_pupil,
        )
        draw_glow_circle(draw, ex + pupil_offset_x, eye_y + pupil_offset_y, int(8 * s), ai_cyan, alpha_max=60, layers=4)
        glint_r = int(4 * s)
        draw.ellipse(
            [ex + pupil_offset_x - glint_r - int(3 * s),
             eye_y + pupil_offset_y - glint_r - int(3 * s),
             ex + pupil_offset_x - glint_r + int(1 * s),
             eye_y + pupil_offset_y - glint_r + int(1 * s)],
            fill=(255, 255, 255, 220),
        )

    mouth_y = head_cy + int(30 * s)
    mouth_rx = int(15 * s)
    mouth_ry = int(10 * s)
    draw.ellipse(
        [ghost_cx - mouth_rx, mouth_y - mouth_ry,
         ghost_cx + mouth_rx, mouth_y + mouth_ry],
        fill=ghost_shadow,
    )

    arm_start_x = body_right - int(10 * s)
    arm_start_y = int(220 * s)
    hand_cx = ghost_cx + int(110 * s)
    hand_cy = int(280 * s)
    arm_end_x = hand_cx - int(20 * s)
    arm_end_y = hand_cy

    arm_pts = [
        (arm_start_x, arm_start_y - int(12 * s)),
        (arm_end_x, arm_end_y - int(12 * s)),
        (arm_end_x, arm_end_y + int(12 * s)),
        (arm_start_x, arm_start_y + int(12 * s)),
    ]
    draw.polygon(arm_pts, fill=ghost_body)

    draw.ellipse(
        [hand_cx - int(20 * s), hand_cy - int(20 * s),
         hand_cx + int(20 * s), hand_cy + int(20 * s)],
        fill=ghost_body,
    )

    click_x = hand_cx + int(5 * s)
    click_y = hand_cy + int(25 * s)
    draw_glow_circle(draw, click_x, click_y, int(35 * s), accent_cyan, alpha_max=50, layers=5)
    draw.ellipse(
        [click_x - int(8 * s), click_y - int(8 * s),
         click_x + int(8 * s), click_y + int(8 * s)],
        fill=accent_cyan,
    )
    for ring_r in [int(16 * s), int(24 * s), int(32 * s)]:
        draw.ellipse(
            [click_x - ring_r, click_y - ring_r,
             click_x + ring_r, click_y + ring_r],
            fill=None,
            outline=accent_glow,
            width=max(1, int(2 * s)),
        )

    play_cx = int(400 * s)
    play_cy = int(380 * s)
    play_size = int(40 * s)
    tri_pts = [
        (play_cx - play_size * 0.4, play_cy - play_size * 0.6),
        (play_cx - play_size * 0.4, play_cy + play_size * 0.6),
        (play_cx + play_size * 0.6, play_cy),
    ]
    tri_pts = [(int(x), int(y)) for x, y in tri_pts]
    draw_glow_circle(draw, play_cx, play_cy, int(55 * s), play_color, alpha_max=40, layers=5)
    draw.polygon(tri_pts, fill=play_color)

    for ring_r in [int(50 * s), int(60 * s)]:
        draw.ellipse(
            [play_cx - ring_r, play_cy - ring_r,
             play_cx + ring_r, play_cy + ring_r],
            fill=None,
            outline=(0, 255, 200, 50),
            width=max(1, int(2 * s)),
        )

    ai_badge_x = int(420 * s)
    ai_badge_y = int(100 * s)
    ai_badge_r = int(38 * s)
    draw_glow_circle(draw, ai_badge_x, ai_badge_y, int(50 * s), ai_purple, alpha_max=50, layers=6)
    draw.ellipse(
        [ai_badge_x - ai_badge_r, ai_badge_y - ai_badge_r,
         ai_badge_x + ai_badge_r, ai_badge_y + ai_badge_r],
        fill=(20, 12, 50, 220),
        outline=(*ai_purple[:3], 180),
        width=max(1, int(2 * s)),
    )

    spark_pts = []
    for angle_deg in [0, 60, 120, 180, 240, 300]:
        angle = math.radians(angle_deg - 90)
        outer_r = int(22 * s)
        inner_r = int(10 * s)
        ox = ai_badge_x + int(outer_r * math.cos(angle))
        oy = ai_badge_y + int(outer_r * math.sin(angle))
        spark_pts.append((ox, oy))
        mid_angle = angle + math.radians(30)
        ix = ai_badge_x + int(inner_r * math.cos(mid_angle))
        iy = ai_badge_y + int(inner_r * math.sin(mid_angle))
        spark_pts.append((ix, iy))

    draw.polygon(spark_pts, fill=ai_gold)
    inner_spark = []
    for angle_deg in [0, 60, 120, 180, 240, 300]:
        angle = math.radians(angle_deg - 90)
        outer_r = int(14 * s)
        inner_r = int(6 * s)
        ox = ai_badge_x + int(outer_r * math.cos(angle))
        oy = ai_badge_y + int(outer_r * math.sin(angle))
        inner_spark.append((ox, oy))
        mid_angle = angle + math.radians(30)
        ix = ai_badge_x + int(inner_r * math.cos(mid_angle))
        iy = ai_badge_y + int(inner_r * math.sin(mid_angle))
        inner_spark.append((ix, iy))

    draw.polygon(inner_spark, fill=(255, 240, 180))

    for _ in range(8):
        sx = random.randint(int(350 * s), int(480 * s))
        sy = random.randint(int(60 * s), int(160 * s))
        sr = random.randint(int(1 * s), int(2 * s))
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(*ai_gold[:3], random.randint(80, 200)))

    inner_margin = int(30 * s)
    draw.rounded_rectangle(
        [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
        radius=int(90 * s),
        fill=None,
        outline=(80, 60, 140, 60),
        width=max(1, int(2 * s)),
    )

    return img


def gen_png_sizes(img, sizes=[16, 32, 64, 128, 256, 512, 1024]):
    paths = []
    for sz in sizes:
        resized = img.resize((sz, sz), Image.LANCZOS)
        path = os.path.join(OUTPUT_DIR, f"icon_{sz}x{sz}.png")
        resized.save(path, "PNG")
        paths.append(path)
        print(f"  {path}")
    return paths


def gen_ico(img, sizes=[16, 32, 48, 64, 128, 256]):
    ico_path = os.path.join(OUTPUT_DIR, "GhostAction.ico")
    icons = []
    for sz in sizes:
        icons.append(img.resize((sz, sz), Image.LANCZOS))
    ico_img = icons[0]
    ico_img.save(ico_path, format="ICO", sizes=[(i.width, i.height) for i in icons],
                 append_images=icons[1:])
    print(f"  {ico_path}")
    return ico_path


def gen_icns(img):
    iconset_dir = os.path.join(OUTPUT_DIR, "GhostAction.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    size_map = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    for name, sz in size_map.items():
        resized = img.resize((sz, sz), Image.LANCZOS)
        resized.save(os.path.join(iconset_dir, name), "PNG")

    icns_path = os.path.join(OUTPUT_DIR, "GhostAction.icns")
    ret = os.system(f"iconutil -c icns \"{iconset_dir}\" -o \"{icns_path}\"")
    if ret == 0:
        print(f"  {icns_path}")
    else:
        print(f"  iconutil failed")
        alt_path = os.path.join(OUTPUT_DIR, "GhostAction.png")
        img.resize((512, 512), Image.LANCZOS).save(alt_path, "PNG")
        print(f"  Saved 512x512 PNG as fallback: {alt_path}")

    return icns_path if ret == 0 else None


if __name__ == "__main__":
    print("Generating GhostAction icon v2 (with AI void elements)...")
    img = draw_ghost_icon(1024)

    print("\nPNG sizes:")
    gen_png_sizes(img)

    print("\nWindows ICO:")
    gen_ico(img)

    print("\nmacOS ICNS:")
    gen_icns(img)

    preview_path = os.path.join(OUTPUT_DIR, "icon_preview.png")
    img.resize((256, 256), Image.LANCZOS).save(preview_path, "PNG")
    print(f"\nPreview: {preview_path}")
    print("Done!")
