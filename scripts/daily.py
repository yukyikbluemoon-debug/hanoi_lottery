#!/usr/bin/env python3
"""อัปเดตผลหวยฮานอยรอบ 'ปกติ' (XSMB ทางการ) ลง data/hanoi_lottery.csv

กฎ: บน 3 ตัว = 3 หลักท้ายของรางวัลพิเศษ (ĐB), ล่าง 2 ตัว = 2 หลักท้ายของรางวัลที่ 1 (G1)
แหล่งข้อมูล: xoso.com.vn (หน้าต่อวัน) ดึงสุภาพ: หน่วง 3 วินาที/คำขอ และระบุตัวตนใน User-Agent
ใช้:  python scripts/daily.py            อัปเดตวันที่ขาดจนถึงวันนี้
      python scripts/daily.py --selftest ตรวจ parser กับวันที่รู้ผลแล้ว (2026-10-17 -> 538/77)
"""
import csv, re, sys, time
from datetime import date, datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

CSV_PATH = "data/hanoi_lottery.csv"
FIELDS = ["source", "draw_date", "top3", "bottom2", "number4", "is_official",
          "matches_official", "is_cancelled", "fetched_at"]
UA = "hanoi-lottery-stats/1.0 (personal statistics project; daily single run; +https://github.com/yukyikbluemoon-debug/hanoi_lottery)"
URL = "https://xoso.com.vn/xsmb-{d:%d-%m-%Y}.html"
DELAY = 3.0
MAX_BACK_DAYS = 40
ICT = timezone(timedelta(hours=7))
DB_LABELS = {"ĐB", "G.ĐB", "ĐẶC BIỆT", "GIẢI ĐB", "GIẢI ĐẶC BIỆT", "DB", "G.DB"}
G1_LABELS = {"1", "G.1", "G1", "NHẤT", "GIẢI NHẤT", "GIẢI 1"}


def parse(html):
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
    if db and g1:
        return db, g1
    return None


def fetch(d):
    r = requests.get(URL.format(d=d), headers={"User-Agent": UA}, timeout=30)
    if r.status_code != 200:
        return None
    return parse(r.text)


def load():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    rows.sort(key=lambda r: (r["draw_date"], r["source"]), reverse=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    if "--selftest" in sys.argv:
        got = fetch(date(2026, 10, 17))
        ok = got == ("64538", "25177")
        print("selftest", got, "OK" if ok else "FAIL")
        sys.exit(0 if ok else 1)

    rows = [r for r in load() if r["source"] == "normal"]
    have = {r["draw_date"] for r in rows}
    today = datetime.now(ICT).date()
    last = max(date.fromisoformat(x) for x in have)
    start = max(last + timedelta(days=1), today - timedelta(days=MAX_BACK_DAYS))
    added = 0
    d = start
    while d <= today:
        if d.isoformat() not in have:
            try:
                res = fetch(d)
            except requests.RequestException as e:
                print(f"{d} network error: {e}")
                res = None
            if res:
                db, g1 = res
                rows.append({"source": "normal", "draw_date": d.isoformat(), "top3": db[-3:],
                             "bottom2": g1[-2:], "number4": db[-4:], "is_official": "1",
                             "matches_official": "", "is_cancelled": "0",
                             "fetched_at": datetime.now(timezone.utc).isoformat()})
                added += 1
                print(f"{d} OK top3={db[-3:]} bottom2={g1[-2:]}")
            else:
                print(f"{d} no result (not published yet / no draw)")
            time.sleep(DELAY)
        d += timedelta(days=1)
    save(rows)
    print(f"added {added} rows; total normal {len(rows)}")


if __name__ == "__main__":
    main()
