# -*- coding: utf-8 -*-
"""ตรวจข้อมูลรอบปกติเทียบ xoso.com.vn ทีละปี:  python scripts/audit.py 2016 [--delay 1.5]
เขียนผลที่ data/audit/normal-YYYY.json และพิมพ์ ::warning:: ทุกจุดที่ไม่ตรง"""
import csv, json, sys, time, os
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(__file__))
import daily

year = int(sys.argv[1])
delay = float(sys.argv[sys.argv.index("--delay") + 1]) if "--delay" in sys.argv else 1.5
rows = {r["draw_date"]: r for r in csv.DictReader(open(daily.CSV_PATH, encoding="utf-8-sig")) if r["source"] == "normal"}
d, end = date(year, 1, 1), min(date(year, 12, 31), date.today())
mism, missing_csv, failed, same, checked = [], [], [], 0, 0
while d <= end:
    iso = d.isoformat()
    res = None
    for _ in range(3):
        res = daily.fetch_xoso(d)
        if res:
            break
        time.sleep(delay * 2)
    time.sleep(delay)
    r = rows.get(iso)
    if not res:
        failed.append(iso)
    else:
        checked += 1
        db, g1 = res
        exp = (db[-3:], g1[-2:], db[-4:])
        if not r:
            missing_csv.append({"date": iso, "xoso": exp})
            print(f"::warning::AUDIT {iso} ไม่มีในไฟล์ xoso={exp}")
        else:
            got = (r["top3"], r["bottom2"], r["number4"])
            if got != exp:
                mism.append({"date": iso, "csv": got, "xoso": exp})
                print(f"::warning::AUDIT MISMATCH {iso} csv={got} xoso={exp}")
            else:
                same += 1
    d += timedelta(days=1)
out = {"year": year, "checked": checked, "same": same, "mismatch": mism,
       "missing_in_csv": missing_csv, "xoso_failed": failed,
       "csv_rows_in_year": sum(1 for k in rows if k.startswith(str(year)))}
os.makedirs("data/audit", exist_ok=True)
json.dump(out, open(f"data/audit/normal-{year}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"::notice::AUDIT {year} checked={checked} same={same} mismatch={len(mism)} missing={len(missing_csv)} failed={len(failed)}")
