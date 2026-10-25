"""驗證 news_data.json 的結構。每週更新任務在 push 前必須通過：python check_news.py"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

errors = []


def need(cond, msg):
    if not cond:
        errors.append(msg)


d = json.loads((Path(__file__).parent / "news_data.json").read_text(encoding="utf-8"))

for k in ("as_of", "headline", "snapshot", "cases", "upcoming", "sources"):
    need(k in d, f"缺少欄位 {k}")

try:
    asof = datetime.strptime(d["as_of"], "%Y-%m-%d").date()
    need(asof <= date.today(), "as_of 不可是未來日期")
except Exception:
    errors.append("as_of 格式需為 YYYY-MM-DD")

snap = d.get("snapshot", {})
for k in ("ff_low", "ff_high", "y10", "y2", "y3m", "y_date", "cpi_yoy", "core_yoy", "cpi_month",
          "nfp_change_k", "unrate", "unrate_prev", "emp_month"):
    need(k in snap, f"snapshot 缺少 {k}")

cases = d.get("cases", [])
need(4 <= len(cases) <= 8, "案例數量需介於 4–8")
ids = set()
for c in cases:
    for k in ("id", "title", "unit", "body", "think", "quiz"):
        need(k in c, f"案例 {c.get('id')} 缺少 {k}")
    need(c.get("id") not in ids, f"案例 id 重複：{c.get('id')}")
    ids.add(c.get("id"))
    q = c.get("quiz", {})
    need(len(q.get("options", [])) >= 2, f"案例 {c.get('id')} 選項不足")
    need(isinstance(q.get("answer"), int) and 0 <= q.get("answer", -1) < len(q.get("options", [])),
         f"案例 {c.get('id')} 答案索引不合法")
    need(bool(q.get("q")) and bool(q.get("explain")), f"案例 {c.get('id')} 缺少題目或解析")

for u in d.get("upcoming", []):
    need(all(k in u for k in ("date", "event", "focus")), "upcoming 項目需有 date/event/focus")
for s in d.get("sources", []):
    need(str(s.get("url", "")).startswith("https://"), f"來源網址需為 https：{s}")
need(len(d.get("sources", [])) >= 3, "至少需要 3 個來源")

if errors:
    print("驗證失敗：")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("news_data.json 驗證通過")
