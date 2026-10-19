#!/usr/bin/env python3
"""
download_icons.py — ดาวน์โหลด icon ของแต่ละ hero จาก rovmeta.com โดยตรง
- ดึง portrait URL จาก alt="[ชื่อภาษาไทย] portrait" ในหน้าของ hero นั้น
- ถ้าไม่มี portrait ให้ fetch หน้านั้นใหม่จาก rovmeta แล้วดึง og:image หรือ structured data
- บันทึกเป็น out/icons/<heroId>.jpg
"""
import json, re, time, random, gzip
from pathlib import Path
from urllib import request, error

UA = "RoVGuideApp-IconFetch/1.0 (personal hobby project)"
BASE = "https://rovmeta.com"

def http_get(url, timeout=15):
    req = request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,*/*;q=0.8",
        "Accept-Encoding": "gzip",
    })
    with request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
            data = gzip.decompress(data)
        return r.status, data

def download_img(url, dest: Path, timeout=15) -> bool:
    try:
        req = request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
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

def find_portrait_url(html: str) -> str | None:
    """หา URL portrait ของ hero นี้จาก alt text ภาษาไทย"""
    # alt="[ชื่อไทย] portrait" — เป็นรูปของ hero หน้านั้นเอง
    imgs = re.findall(r'<img[^>]+src="(https://cdn-webth[^"]+)"[^>]*alt="([^"]*)"', html)
    for src, alt in imgs:
        if 'portrait' in alt.lower():
            return src
    return None

def find_any_own_icon(html: str, slug: str) -> str | None:
    """
    สำหรับ hero ที่ไม่มี portrait — หาจาก JSON-LD หรือ script __NEXT_DATA__
    ซึ่งมีข้อมูล hero ของหน้านั้นโดยตรง
    """
    # ลอง __NEXT_DATA__ JSON
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            # traverse หา image URL
            text = json.dumps(data)
            # หา CDN URL ที่น่าจะเป็นรูปของ hero นั้น
            urls = re.findall(r'https://cdn-webth\.garenanow\.com[^"\'\\]+\.(?:jpg|jpeg|png|webp)', text)
            # กรองเอาแค่ URL ที่ไม่ใช่ hero icon ของตัวอื่น (hero icon มักเล็กกว่า portrait)
            for url in urls:
                if 'portrait' in url.lower() or 'hero_icon' not in url.lower():
                    return url
        except Exception:
            pass
    
    # ลอง structured data JSON-LD
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
            img = data.get('image') or data.get('thumbnailUrl')
            if img and 'cdn-webth' in img:
                return img
        except Exception:
            pass
    
    return None

def main():
    html_dir  = Path('out/rovmeta_raw')
    icons_dir = Path('out/icons')
    icons_dir.mkdir(parents=True, exist_ok=True)

    # สร้าง slug list จาก HTML ที่มี
    slugs = sorted([f.stem for f in html_dir.glob('*.html') if not f.name.startswith('_')])
    print(f"Heroes to process: {len(slugs)}")

    ok = fail = skip = refetch = 0

    for slug in slugs:
        dest = icons_dir / f'{slug}.jpg'

        # ถ้ามีแล้วและขนาดสมเหตุสมผล → skip
        if dest.exists() and dest.stat().st_size > 5000:
            skip += 1
            continue

        # อ่าน HTML ที่มีอยู่
        html_file = html_dir / f'{slug}.html'
        html = html_file.read_text(encoding='utf-8', errors='ignore')

        # ลองหา portrait URL
        url = find_portrait_url(html)

        # ถ้าไม่มี portrait → fetch หน้าใหม่จาก rovmeta
        if not url:
            try:
                _, fresh = http_get(f"{BASE}/th/heroes/{slug}")
                fresh_html = fresh.decode('utf-8', errors='ignore')
                url = find_portrait_url(fresh_html)
                if not url:
                    url = find_any_own_icon(fresh_html, slug)
                # บันทึก HTML ใหม่ทับ
                if url:
                    html_file.write_bytes(fresh)
                refetch += 1
                time.sleep(1.5 + random.uniform(0, 0.5))
            except Exception as e:
                print(f"  REFETCH FAIL  {slug}: {e}")

        if not url:
            print(f"  NO URL        {slug}")
            fail += 1
            continue

        # download รูป
        if download_img(url, dest):
            print(f"  ok  {slug:25}  ({dest.stat().st_size//1024}KB)")
            ok += 1
        else:
            print(f"  DOWNLOAD FAIL {slug}  {url[-50:]}")
            fail += 1

        time.sleep(0.3)

    print(f'\n✅ ok={ok}  skip={skip}  refetch={refetch}  fail={fail}')
    print(f'   icons → {icons_dir}  ({len(list(icons_dir.glob("*.jpg")))} files)')

if __name__ == '__main__':
    main()
