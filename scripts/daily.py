#!/usr/bin/env python3
"""อัปเดตผลหวยฮานอยลง data/hanoi_lottery.csv

รอบ ปกติ (normal): ผลทางการ XSMB จาก xoso.com.vn (หน้าต่อวัน) ย้อนหลังไกลสุดปี 2002
รอบ VIP: จากหน้า history ของ ผลหวย.com (ผลจริงมีแค่ตั้งแต่ 2026-07-25)
ตรวจซ้ำ: เทียบรอบปกติของ ผลหวย.com กับของ xoso ถ้าไม่ตรงจะจบงานด้วย exit code 2

กฎ: บน 3 ตัว = 3 หลักท้ายของรางวัลพิเศษ, ล่าง 2 ตัว = 2 หลักท้ายของรางวัลที่ 1 (ปกติ)
ดึงสุภาพ: หน่วง 3 วินาที/คำขอ, ระบุตัวตนใน User-Agent, robots.txt ของทั้งสองเว็บอนุญาต

ใช้:  python scripts/daily.py            อัปเดต
      python scripts/daily.py --selftest ตรวจ parser กับวันที่รู้ผลแล้ว
"""
import csv, re, sys, time
from datetime import date, datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

CSV_PATH = "data/hanoi_lottery.csv"
FIELDS = ["source", "draw_date", "top3", "bottom2", "number4", "is_official",
          "matches_official", "is_cancelled", "fetched_at"]
UA = "hanoi-lottery-stats/1.0 (personal statistics project; daily single run; +https://github.com/yukyikbluemoon-debug/hanoi_lottery)"
XOSO_URL = "https://xoso.com.vn/xsmb-{d:%d-%m-%Y}.html"
SITE = "https://xn--t3cmiit.com/hanoi-lottery/{r}/history"  # ผลหวย.com
DELAY = 3.0
MAX_BACK_DAYS = 40
ICT = timezone(timedelta(hours=7))
DB_LABELS = {"ĐB", "G.ĐB", "ĐẶC BIỆT", "GIẢI ĐB", "GIẢI ĐẶC BIỆT", "DB", "G.DB"}
G1_LABELS = {"1", "G.1", "G1", "NHẤT", "GIẢI NHẤT", "GIẢI 1"}
TH_MONTHS = {m: i + 1 for i, m in enumerate(
    ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
     "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"])}
TH_MONTHS.update({m: i + 1 for i, m in enumerate(
    ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."])})


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    return r.text if r.status_code == 200 else None


# ---------- xoso.com.vn (ปกติ) ----------
def parse_xoso(html):
    """คืน (db5, g1_5) หรือ None ถ้าหน้ายังไม่มีผล"""
    soup = BeautifulSoup(html, "html.parser")
    db = g1 = None
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        label = cells[0].strip().upper()
        nums = re.findall(r"(?<!\d)\d{5}(?!\d)", " ".join(cells[1:]))
        if not nums:
            continue
        if db is None and label in DB_LABELS:
            db = nums[0]
        elif g1 is None and label in G1_LABELS:
            g1 = nums[0]
        if db and g1:
            break
    return (db, g1) if db and g1 else None


def fetch_xoso(d):
    html = get(XOSO_URL.format(d=d))
    return parse_xoso(html) if html else None


# ---------- ผลหวย.com (VIP และตัวตรวจซ้ำรอบปกติ) ----------
DATE_RE = re.compile(r"(\d{1,2})\s*(" + "|".join(re.escape(m) for m in TH_MONTHS) + r")\s*(\d{4})")


def parse_site(html):
    """คืน dict {date: (special5, top3, bottom2)} จากตาราง history"""
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        m = DATE_RE.search(cells[0])
        if not m:
            continue
        day, mon, yr = int(m.group(1)), TH_MONTHS[m.group(2)], int(m.group(3))
        yr = yr - 543 if yr > 2400 else yr
        rest = cells[1:]
        sp = next((c for c in rest if re.fullmatch(r"\d{5}", c)), None)
        t3 = next((c for c in rest if re.fullmatch(r"\d{3}", c)), None)
        b2 = next((c for c in rest if re.fullmatch(r"\d{2}", c)), None)
        if not (sp and t3 and b2) or sp[-3:] != t3:
            continue
        try:
            out[date(yr, mon, day)] = (sp, t3, b2)
        except ValueError:
            continue
    return out


def fetch_site(rnd):
    html = get(SITE.format(r=rnd))
    return parse_site(html) if html else {}


# ---------- CSV ----------
def load():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    rows.sort(key=lambda r: (r["draw_date"], r["source"]), reverse=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def new_row(source, d, special5, top3, bottom2, official):
    return {"source": source, "draw_date": d.isoformat(), "top3": top3, "bottom2": bottom2,
            "number4": special5[-4:], "is_official": "1" if official else "0",
            "matches_official": "", "is_cancelled": "0",
            "fetched_at": datetime.now(timezone.utc).isoformat()}


def selftest():
    ok = True
    x = fetch_xoso(date(2026, 10, 17))
    print("xoso 2026-10-17:", x, "OK" if x == ("64538", "25177") else "FAIL")
    ok &= x == ("64538", "25177")
    time.sleep(DELAY)
    v = fetch_site("vip")
    got = v.get(date(2026, 10, 17))
    print("site vip 2026-10-17:", got, "rows", len(v), "OK" if got == ("23316", "316", "30") else "FAIL")
    ok &= got == ("23316", "316", "30")
    return ok


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)

    rows = load()
    normal = {r["draw_date"]: r for r in rows if r["source"] == "normal"}
    vip = {r["draw_date"] for r in rows if r["source"] == "vip"}
    today = datetime.now(ICT).date()
    rows = [r for r in rows if r["source"] in ("normal", "vip")]

    # 1) ปกติจาก xoso
    last = max(date.fromisoformat(x) for x in normal)
    d = max(last + timedelta(days=1), today - timedelta(days=MAX_BACK_DAYS))
    added_n = 0
    while d <= today:
        if d.isoformat() not in normal:
            try:
                res = fetch_xoso(d)
            except requests.RequestException as e:
                print(f"{d} xoso network error: {e}")
                res = None
            if res:
                db, g1 = res
                row = new_row("normal", d, db, db[-3:], g1[-2:], True)
                rows.append(row)
                normal[row["draw_date"]] = row
                added_n += 1
                print(f"normal {d} OK {db[-3:]}/{g1[-2:]}")
            else:
                print(f"normal {d} no result yet")
            time.sleep(DELAY)
        d += timedelta(days=1)

    # 2) VIP จาก ผลหวย.com
    added_v = 0
    site_vip = fetch_site("vip")
    if not site_vip:
        print("WARN: อ่านตาราง VIP จาก ผลหวย.com ไม่ได้")
    for d, (sp, t3, b2) in sorted(site_vip.items()):
        if d.isoformat() not in vip:
            rows.append(new_row("vip", d, sp, t3, b2, False))
            added_v += 1
            print(f"vip {d} OK {t3}/{b2}")
    time.sleep(DELAY)

    # 3) ตรวจซ้ำรอบปกติระหว่างสองแหล่ง
    mismatches = []
    site_norm = fetch_site("normal")
    for d, (sp, t3, b2) in site_norm.items():
        r = normal.get(d.isoformat())
        if r and (r["top3"], r["bottom2"]) != (t3, b2):
            mismatches.append((d.isoformat(), r["top3"], r["bottom2"], t3, b2))
    save(rows)
    print(f"added normal {added_n}, vip {added_v}; cross-checked {len(site_norm)} normal rows")
    if mismatches:
        for m in mismatches:
            print(f"::error::MISMATCH {m[0]} xoso={m[1]}/{m[2]} site={m[3]}/{m[4]}")
        sys.exit(2)


if __name__ == "__main__":
    main()
