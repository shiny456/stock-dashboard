import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st

from common import curve_chart, quiz
from live_data import snapshot, yield_curve

DATA = Path(__file__).parent / "news_data.json"


def _load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def page_news():
    d = _load()
    st.header("🗞️ 時事教室：用最近的新聞複習觀念")

    live = snapshot()
    s = live or d["snapshot"]
    if live:
        st.caption(f"上方數字為即時資料（FRED，每小時更新；殖利率截至 {s['y_date']}，CPI 為 {s['cpi_month']}、就業為 {s['emp_month']}）。"
                   f"下方案例由每週更新任務撰寫於 **{d['as_of']}**。")
    else:
        st.warning(f"暫時抓不到即時資料，以下顯示 {d['as_of']} 的快照。")

    try:
        age = (date.today() - datetime.strptime(d["as_of"], "%Y-%m-%d").date()).days
    except ValueError:
        age = 0
    if age > 14:
        st.warning(f"⚠️ 案例內容已 {age} 天沒更新，文中的數字可能過期；請以上方即時指標為準。")

    m = st.columns(4)
    m[0].metric("聯邦基金利率目標", f"{s['ff_low']:.2f}–{s['ff_high']:.2f}%")
    m[1].metric("10 年期公債殖利率", f"{s['y10']:.2f}%")
    m[2].metric("2 年期公債殖利率", f"{s['y2']:.2f}%", f"10Y−2Y {s['y10'] - s['y2']:+.2f}", delta_color="off")
    m[3].metric("3 個月期殖利率", f"{s['y3m']:.2f}%", f"vs 目標上緣 {s['y3m'] - s['ff_high']:+.2f}", delta_color="off")
    m = st.columns(4)
    m[0].metric("CPI 年增", f"{s['cpi_yoy']:.1f}%")
    m[1].metric("核心 CPI 年增", f"{s['core_yoy']:.1f}%")
    m[2].metric("非農新增就業", f"{s['nfp_change_k']:+,.0f} 千")
    m[3].metric("失業率", f"{s['unrate']:.1f}%", f"前月 {s['unrate_prev']:.1f}%", delta_color="off")
    extras = d.get("extra_metrics", [])
    if extras:
        cols = st.columns(len(extras))
        for c, e in zip(cols, extras):
            c.metric(e["label"], e["value"], e["note"], delta_color="off")

    curve, cdate = yield_curve()
    if curve is not None:
        st.markdown("#### 殖利率曲線：現在 vs 一年前")
        curve_chart(curve)
        st.caption("看看曲線形狀有沒有變陡、整體是不是往上平移（單元 3）。短端（3M）高於 Fed 目標上緣，代表市場在定價升息。")

    st.markdown("#### 一句話看懂現在的市場")
    st.info(d["headline"])

    for i, c in enumerate(d["cases"], 1):
        with st.expander(f"📌 案例 {i}｜{c['title']}（{c['unit']}）", expanded=(i == 1)):
            st.markdown(c["body"])
            st.markdown(f"**思考題**：{c['think']}")
            q = c["quiz"]
            quiz(f"n_{c['id']}", q["q"], q["options"], q["answer"], q["explain"])

    st.subheader("🧮 用最新殖利率算算：股票比債券多給你多少補償？")
    c1, c2 = st.columns(2)
    pe = c1.number_input("輸入大盤『預期本益比』（請自行查最新值）", 10.0, 40.0, 21.0, 0.5, key="news_pe")
    y10 = c2.number_input("10 年期殖利率 %", 0.5, 8.0, round(s["y10"], 2), 0.05, key="news_y10")
    st.metric("簡易股權風險溢價", f"{100 / pe - y10:+.2f}%", help="盈餘殖利率 − 10 年期殖利率")
    st.caption("預設的 P/E 21 只是示意，不是實際的市場數字。用你查到的真實數字取代。")

    st.subheader("📅 接下來要看什麼（用來練習『看預期差』）")
    st.dataframe(
        [{"日期": u["date"], "事件": u["event"], "觀察重點": u["focus"]} for u in d["upcoming"]],
        hide_index=True,
    )
    st.caption("日期與機率以官方行事曆與期貨隱含機率為準。")

    st.subheader("🧠 做一個自己的『時事筆記』練習")
    st.markdown(
        """
每次看到新聞，照這 5 步寫下三行：
1. **發生什麼**（數字）？
2. **是通膨、成長、還是風險偏好**在主導？
3. **對利率／殖利率**的影響方向？
4. **對股票估值／債券價格**的影響方向？
5. **跟預期比，是意外嗎**？
"""
    )

    st.markdown("---")
    st.markdown("**資料來源**（請自行核對最新數字）：" + "｜".join(f"[{x['title']}]({x['url']})" for x in d["sources"]))
    st.caption("教學用整理，非投資建議。市場價格為約數，各來源略有出入；官方數據以 Fed、BLS 為準。")
