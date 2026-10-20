#!/usr/bin/env python3
"""
download_icons.py — ดาวน์โหลด icon ของแต่ละ hero
แหล่ง URL (ตามลำดับ):
1. _heroes_list.html — anchor href="/th/heroes/SLUG" → img src แรก (ถูกต้องทุกตัว)
2. hero page HTML — alt="[ชื่อไทย] portrait" (fallback)
"""
import re, time, random, gzip, json
from pathlib import Path
from urllib import request

UA_BOT  = "RoVGuideApp-IconFetch/1.0"
UA_IMG  = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"

def http_get(url, timeout=15):
    req = request.Request(url, headers={
        "User-Agent": UA_BOT,
        "Accept": "text/html,*/*;q=0.8",
        "Accept-Encoding": "gzip",
    })
    with request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
            data = gzip.decompress(data)
        return r.status, data.decode("utf-8", errors="ignore")

def download_img(url: str, dest: Path, timeout=15) -> bool:
    try:
        req = request.Request(url, headers={
            "User-Agent": UA_IMG,
            "Referer": "https://rovmeta.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        })
        with request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        if len(data) < 1000:
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False

def parse_list_urls(html: str) -> dict:
    """ดึง slug → icon URL จาก _heroes_list.html"""
    result = {}
    anchors = re.findall(
        r'href="/th/heroes/([A-Za-z0-9_\-]+)"[^>]*>(.*?)</a>',
        html, re.S
    )
    for slug, content in anchors:
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', content)
        if imgs:
            result[slug] = imgs[0]
    return result

def parse_portrait_url(html: str) -> str | None:
    """fallback: หา portrait จากหน้า hero เอง"""
    imgs = re.findall(r'<img[^>]+src="(https://cdn-webth[^"]+)"[^>]*alt="([^"]*)"', html)
    for src, alt in imgs:
        if 'portrait' in alt.lower():
            return src
    return None

def main():
    html_dir  = Path("out/rovmeta_raw")
    icons_dir = Path("out/icons")
    icons_dir.mkdir(parents=True, exist_ok=True)

    # โหลด URL map จาก _heroes_list.html
    list_file = html_dir / "_heroes_list.html"
    list_url_map = {}
    if list_file.exists():
        list_url_map = parse_list_urls(list_file.read_text(encoding="utf-8", errors="ignore"))
        print(f"List page URLs: {len(list_url_map)}")
    else:
        # fetch ใหม่จาก rovmeta
        try:
            _, html = http_get("https://rovmeta.com/th/heroes")
            list_url_map = parse_list_urls(html)
            list_file.write_text(html, encoding="utf-8")
            print(f"Fetched list page: {len(list_url_map)} heroes")
        except Exception as e:
            print(f"WARN: cannot fetch list page: {e}")

    slugs = sorted([f.stem for f in html_dir.glob("*.html") if not f.name.startswith("_")])
    print(f"Heroes to download: {len(slugs)}")

    ok = fail = 0

    for slug in slugs:
        dest = icons_dir / f"{slug}.jpg"

        # หา URL — list page ก่อน ถ้าไม่มีค่อย fallback hero page
        url = list_url_map.get(slug)

        if not url:
            html = (html_dir / f"{slug}.html").read_text(encoding="utf-8", errors="ignore")
            url = parse_portrait_url(html)

        if not url:
            print(f"  NO URL   {slug}")
            fail += 1
            continue

        if download_img(url, dest):
            print(f"  ok  {slug:25} ({dest.stat().st_size//1024}KB)")
            ok += 1
        else:
            print(f"  FAIL     {slug}  {url[-50:]}")
            fail += 1

        time.sleep(0.25 + random.uniform(0, 0.15))

    print(f"\n✅ ok={ok}  fail={fail}")
    print(f"   icons → {icons_dir}  ({len(list(icons_dir.glob('*.jpg')))} files)")

if __name__ == "__main__":
    main()
