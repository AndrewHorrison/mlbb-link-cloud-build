#!/usr/bin/env python3
"""Enrich MLBB Link with official skill labels/art, portrait-based fallback icons, and skill metadata.

The Moonton endpoint is optional: the build remains reproducible when it is unavailable,
but every selectable hero still receives three visible skill-icon resources.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

API_URL = "https://api.gms.moontontech.com/api/gms/source/2669606/2756564"
ALIASES = {
    "Chang'e": "change", "Popol and Kupa": "popol_and_kupa",
    "X.Borg": "x_borg", "Yi Sun-shin": "yi_sun_shin",
    "Lapu-Lapu": "lapu_lapu", "Luo Yi": "luo_yi",
}
LABELS = ("S1", "S2", "ULT")
ACCENTS = ((91, 202, 245), (193, 117, 255), (255, 190, 94))


def slug(name: str) -> str:
    return ALIASES.get(name, re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))


def load_java_array(source: str, declaration: str) -> list[str]:
    match = re.search(declaration + r"\s*=\s*(\{.*?\});", source, re.S)
    if not match:
        raise RuntimeError(f"Could not read Java array: {declaration}")
    return json.loads("[" + match.group(1)[1:-1] + "]")


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "User-Agent": "MLBB-Link-Skill-Enricher/1.0",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=18) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def get_skill_records() -> dict[str, list[dict]]:
    payload = {
        "pageSize": 200, "pageIndex": 1, "filters": [],
        "sorts": [{"data": {"field": "hero_id", "order": "desc"}, "type": "sequence"}],
        "fields": [], "object": [],
    }
    body = request_json(API_URL, payload)
    records = (body.get("data") or {}).get("records") or []
    if not records:
        raise RuntimeError("Moonton returned no hero records")
    mapped: dict[str, list[dict]] = {}
    for record in records:
        raw = record.get("data") or {}
        wrapped = raw.get("hero") or {}
        hero = wrapped.get("data") or raw
        name = str(hero.get("name") or "")
        if not name:
            continue
        flat: list[dict] = []
        groups = hero.get("heroskilllist") or []
        for group_index, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            for skill in group.get("skilllist") or []:
                if isinstance(skill, dict) and (skill.get("skillname") or skill.get("skillicon")):
                    flat.append({
                        "name": str(skill.get("skillname") or ""),
                        "url": str(skill.get("skillicon") or ""),
                        "description": str(skill.get("skilldesc") or ""),
                        "cooldown": str(skill.get("skillcd&cost") or ""),
                        "group": group_index + 1,
                        "id": str(skill.get("skillid") or ""),
                    })
        if not flat:
            continue
        # MLBB records normally begin with the passive; the controller has 3 active slots.
        active = flat[1:4] if len(flat) >= 4 else flat[:3]
        if active:
            mapped[slug(name)] = active
    return mapped


def open_image_url(url: str) -> Image.Image | None:
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MLBB-Link-Skill-Enricher/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read()
        im = Image.open(BytesIO(raw)).convert("RGB")
        return ImageOps.fit(im, (160, 160), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    except Exception:
        return None


def find_image(folder: Path, base: str) -> Path | None:
    for ext in (".webp", ".png", ".jpg", ".jpeg"):
        candidate = folder / (base + ext)
        if candidate.is_file() and candidate.stat().st_size:
            return candidate
    return None


def load_portrait(folder: Path, key: str) -> Image.Image | None:
    path = find_image(folder, "hero_" + key)
    if not path:
        return None
    try:
        with Image.open(path) as original:
            return ImageOps.fit(original.convert("RGB"), (160, 160), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    except Exception:
        return None


def generated_skill_icon(folder: Path, key: str, skill_index: int, hero_name: str) -> Image.Image:
    """Readable fallback: distinct hero portrait, colored skill ring, slot tag and ability glyph."""
    portrait = load_portrait(folder, key)
    if portrait is None:
        palette = ((17, 44, 65), (38, 25, 59), (58, 38, 17))
        portrait = Image.new("RGB", (160, 160), palette[skill_index])
        d = ImageDraw.Draw(portrait)
        initial = "".join(part[0] for part in re.findall(r"[A-Za-z0-9]+", hero_name)[:2]).upper() or "?"
        font_big = load_font(48)
        d.text((80, 71), initial, font=font_big, anchor="mm", fill=(234, 245, 250))
    else:
        portrait = ImageEnhance.Brightness(portrait).enhance(0.72)
    overlay = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    accent = ACCENTS[skill_index]
    d.ellipse((4, 4, 156, 156), outline=accent + (255,), width=7)
    # Different silhouettes per control slot; remains legible on tiny skill buttons.
    if skill_index == 0:
        d.polygon([(83, 28), (44, 83), (71, 83), (58, 127), (111, 65), (83, 65)], fill=accent + (240,))
    elif skill_index == 1:
        d.polygon([(80, 27), (104, 63), (132, 71), (106, 88), (112, 119), (80, 103), (48, 119), (54, 88), (28, 71), (56, 63)], fill=accent + (235,))
    else:
        d.ellipse((39, 36, 121, 118), outline=(255, 255, 255, 230), width=6)
        d.ellipse((57, 54, 103, 100), fill=accent + (240,))
        d.polygon([(80, 20), (89, 43), (112, 34), (100, 57), (128, 72), (103, 81), (117, 104), (91, 96), (80, 129), (68, 96), (43, 104), (57, 81), (31, 72), (60, 57), (48, 34), (71, 43)], outline=(255, 255, 255, 235))
    d.rounded_rectangle((10, 10, 57, 35), radius=8, fill=(6, 13, 21, 230), outline=accent + (255,), width=2)
    d.text((33, 22), LABELS[skill_index], font=load_font(14), anchor="mm", fill=(255, 255, 255, 255))
    return Image.alpha_composite(portrait.convert("RGBA"), overlay).convert("RGB")


def load_font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def save_webp(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=88, method=6)


def java_quote(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def update_java_skill_names(java_path: Path, keys: list[str], hero_names: list[str],
                            skill_data: dict[str, list[dict]]) -> int:
    source = java_path.read_text()
    match = re.search(r"(private final String\[\]\[\] skillNames\s*=\s*\{)(.*?)(\n\s*\};)", source, re.S)
    if not match:
        raise RuntimeError("Could not locate skillNames table")
    rows = re.findall(r"\{([^{}]*)\}", match.group(2))
    parsed: list[list[str]] = []
    for row in rows:
        parsed.append(re.findall(r'"((?:\\.|[^"\\])*)"', row))
    if len(parsed) != len(keys):
        raise RuntimeError(f"Skill-name rows={len(parsed)} but hero keys={len(keys)}")
    for index, key in enumerate(keys):
        data = skill_data.get(key) or []
        names = [str(s.get("name") or "").strip() for s in data]
        names = [n for n in names if n]
        if len(names) >= 3:
            parsed[index] = names[:3]
        elif len(parsed[index]) != 3:
            parsed[index] = ["SKILL 1", "SKILL 2", "ULTIMATE"]
    rows_text = ",\n".join("                {" + ", ".join(java_quote(v) for v in row[:3]) + "}" for row in parsed)
    source = source[:match.start()] + match.group(1) + "\n" + rows_text + match.group(3) + source[match.end():]
    # The current aim prompt now explains which skill is being aimed, not just the gesture.
    old = '''            String prompt = heroIndex == 2 && aimSkill == 2 && soraForm == 0
                    ? "SWIPE LEFT: THUNDER  •  RIGHT: TORRENT"
                    : "DRAG TO AIM  •  RELEASE TO CAST";
            text(c, prompt, w*0.475f, h*0.115f, unit*0.016f, 0xFFFFD77A, true, Paint.Align.CENTER);'''
    new = '''            String prompt = heroIndex == 2 && aimSkill == 2 && soraForm == 0
                    ? "SWIPE LEFT: THUNDER  •  RIGHT: TORRENT"
                    : currentSkillName(aimSkill) + "  •  DRAG TO AIM";
            text(c, prompt, w*0.475f, h*0.115f, unit*0.0135f, 0xFFFFD77A, true, Paint.Align.CENTER);'''
    if old in source:
        source = source.replace(old, new, 1)
    java_path.write_text(source)
    return sum(1 for key in keys if skill_data.get(key))


def make_details(folder: Path, hero_names: list[str], keys: list[str], skill_data: dict[str, list[dict]]) -> None:
    records = []
    for name, key in zip(hero_names, keys):
        details = skill_data.get(key) or []
        slots = []
        for i in range(3):
            item = details[i] if i < len(details) else {}
            image = find_image(folder, f"skill_{key}_{i+1}")
            slots.append({
                "slot": LABELS[i],
                "name": item.get("name") or ("Skill 1" if i == 0 else "Skill 2" if i == 1 else "Ultimate"),
                "description": item.get("description", ""),
                "cooldownCost": item.get("cooldown", ""),
                "iconResource": image.stem if image else None,
                "source": "Moonton GMS" if item else "fallback",
            })
        records.append({"hero": name, "key": key, "skills": slots})
    dest = folder.parent / "assets" / "hero_skill_details.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"schemaVersion": 1, "heroes": records}, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: enrich_hero_skills.py <phone-app-root> <generated-mainactivity-java>", file=sys.stderr)
        return 2
    app_root = Path(sys.argv[1])
    java_path = Path(sys.argv[2])
    assets = app_root / "src/main/res/drawable-nodpi"
    java = java_path.read_text()
    heroes = load_java_array(java, r"private final String\[\] heroes")
    keys = load_java_array(java, r"String\[\] keys")
    if len(heroes) != len(keys):
        raise RuntimeError(f"hero roster has {len(heroes)} names but {len(keys)} resource keys")
    skill_data: dict[str, list[dict]] = {}
    api_ok = False
    try:
        skill_data = get_skill_records()
        api_ok = True
        print(f"Loaded skill records for {len(skill_data)} heroes from the Moonton GMS API")
    except Exception as exc:
        print(f"WARNING: Official skill API unavailable; portraits + generated skill icons will be used: {exc}")
    downloaded = 0
    for hero_name, key in zip(heroes, keys):
        source_skills = skill_data.get(key) or []
        for i in range(3):
            target = assets / f"skill_{key}_{i+1}.webp"
            # Preserve verified artwork from existing sources. Fill only missing slots from the API.
            if not target.exists():
                actual = source_skills[i].get("url", "") if i < len(source_skills) else ""
                image = open_image_url(actual)
                if image is not None:
                    save_webp(image, target)
                    downloaded += 1
                else:
                    save_webp(generated_skill_icon(assets, key, i, hero_name), target)
        if not all((assets / f"skill_{key}_{i}.webp").exists() for i in (1, 2, 3)):
            raise RuntimeError(f"Failed to make all skill icons for {hero_name}")
    print(f"Ensured {len(heroes) * 3} icon files exist for {len(heroes)} hero entries; downloaded {downloaded} official icons")
    actual_names = update_java_skill_names(java_path, keys, heroes, skill_data)
    print(f"Applied official active skill names for {actual_names} heroes")
    make_details(assets, heroes, keys, skill_data)
    print("Wrote structured hero_skill_details.json metadata")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[skill-enricher] ERROR: {exc}", file=sys.stderr)
        raise
