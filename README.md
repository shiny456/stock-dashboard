# 美股基本面入門課

Streamlit 學習網站：總經篇（單元 1–7）、個股基本面篇（單元 8–13）、時事教室。

## 檔案
- `app.py`：首頁、總經單元與導覽
- `fundamentals.py`：個股基本面單元 8–13
- `news.py` / `news_data.json`：時事教室。頂端指標由 `live_data.py` 從 FRED 即時抓取；案例文字在 `news_data.json`
- `check_news.py`：驗證 `news_data.json` 結構（`python check_news.py`）

## 時事教室如何更新
- 即時指標：開啟頁面時自動從 FRED 公開 CSV 抓取，快取 1 小時；抓不到時顯示 JSON 內的快照。
- 案例文字：每週一由排程任務搜尋新聞、改寫 `news_data.json`、通過 `check_news.py` 後 push。
- 想手動更新：直接編輯 `news_data.json`，跑 `python check_news.py`，再 push。

學習筆記，非投資建議；個股範例皆為虛構。
