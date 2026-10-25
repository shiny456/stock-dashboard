import numpy as np
import pandas as pd
import streamlit as st

import signals
from futu_client import FutuError, demo_watchlist, futu_available, list_groups, load_watchlist
from live_data import snapshot

QUALITY_COLS = ["roic", "fcf_conv", "nd_ebitda", "coverage"]
QUALITY_LABELS = {"roic": "ROIC %", "fcf_conv": "FCF÷淨利 %", "nd_ebitda": "淨負債/EBITDA", "coverage": "利息保障倍數"}


def _blank_quality(df):
    base = pd.DataFrame({"code": df["code"], "name": df["name"]})
    for c in QUALITY_COLS:
        base[c] = np.nan
    return base


def page_my_stocks():
    st.header("⭐ 我的自選股：過熱與回檔儀表板")
    st.warning(
        "這是**教學用的規則式篩選工具**，不是投資建議，我也不是持牌投資顧問。"
        "它只回答兩件事：**哪些股票現在『價格或估值訊號偏熱』，哪些『回檔到值得先做功課』**。"
        "要不要買，仍需用單元 8–13 的方法確認公司品質，並依你自己的目標與風險承受度決定。"
    )

    with st.expander("如何連接富途牛牛（只讀取自選股，不含任何交易功能）"):
        st.markdown(
            """
富途的 API 需要在**你自己的電腦**上執行 OpenD 閘道並登入，所以這一頁的真實資料只有在本機執行網站時才會出現；
線上公開版只能看『示範資料』。

1. 在富途 OpenAPI 官網下載並安裝 **OpenD**，啟動後登入你的富途牛牛帳號（預設連線位置 `127.0.0.1:11111`）。
2. 在專案資料夾安裝本機套件：`pip install -r requirements-local.txt`
3. 在本機啟動網站：`streamlit run app.py`，回到這一頁選『富途 OpenD』。
4. 你的帳號需要有美股報價權限；歷史 K 線有額度限制（依帳戶資產與交易狀況，額度約 7 天釋放），所以預設會快取 15 分鐘並限制檔數。

官方文件：[Futu OpenAPI](https://openapi.futunn.com/futu-api-doc/en/)
"""
        )

    # ---- 資料來源 ----
    can_futu = futu_available()
    options = ["示範資料（虛構）"] + (["富途 OpenD（本機）"] if can_futu else [])
    mode = st.radio("資料來源", options, horizontal=True)
    if not can_futu:
        st.caption("未偵測到 futu-api 套件，只能使用示範資料。本機安裝方式見上方說明。")

    live = snapshot()
    y10_default = round(live["y10"], 2) if live else 4.96
    y10 = st.number_input("10 年期公債殖利率 %（用來比較股票的盈餘殖利率）", 0.5, 10.0, y10_default, 0.05)

    df = None
    if mode.startswith("示範"):
        df = demo_watchlist()
        st.info("目前顯示的是**虛構的示範資料**，用來展示介面與判斷邏輯。")
    else:
        c1, c2 = st.columns(2)
        host = c1.text_input("OpenD 主機", "127.0.0.1")
        port = c2.number_input("連接埠", 1, 65535, 11111)
        try:
            groups = list_groups(host, int(port))
        except Exception as e:
            st.error(f"連不上 OpenD：{e}。請確認 OpenD 已啟動並登入。")
            return
        default = groups.index("美股") if "美股" in groups else 0
        group = st.selectbox("自選股分組", groups, index=default)
        use_kline = st.checkbox("計算技術面（RSI、200 日線），會使用歷史 K 線額度", value=True)
        max_kline = st.slider("最多抓幾檔的歷史 K 線（額度約 100 檔／7 天）", 5, 100, 70)
        if st.button("載入自選股", type="primary"):
            load_watchlist.clear()
        try:
            with st.spinner("向富途取得資料中…"):
                df, notes = load_watchlist(host, int(port), group, use_kline, max_kline)
            for n in notes:
                st.caption(n)
        except FutuError as e:
            st.error(str(e))
            return
        except Exception as e:
            st.error(f"讀取失敗：{e}")
            return

    # ---- 選填：品質數字 ----
    st.subheader("① （選填）補上你查到的品質數字")
    st.caption("填寫單元 9、11 教的幾個指標，工具才能分辨『便宜但有理由』和『便宜且體質好』。至少填 3 項才會計入。"
               "資料會留在你這個瀏覽器工作階段；可以下載成 CSV，下次上傳回來。")
    codes_key = tuple(df["code"])
    if st.session_state.get("quality_codes") != codes_key:
        st.session_state["quality_codes"] = codes_key
        st.session_state["quality_base"] = _blank_quality(df)
        st.session_state["editor_v"] = st.session_state.get("editor_v", 0) + 1
    up = st.file_uploader("上傳之前下載的品質 CSV", type="csv")
    if up is not None and st.session_state.get("last_upload") != (up.name, up.size):
        try:
            loaded = pd.read_csv(up)
            keep = [c for c in QUALITY_COLS if c in loaded.columns]
            base = st.session_state["quality_base"].drop(columns=keep).merge(loaded[["code"] + keep], on="code", how="left")
            st.session_state["quality_base"] = base[["code", "name"] + QUALITY_COLS]
            st.session_state["editor_v"] += 1
            st.session_state["last_upload"] = (up.name, up.size)
        except Exception:
            st.error("CSV 讀取失敗（需要 code 欄位與 roic、fcf_conv、nd_ebitda、coverage 欄位）")
    edited = st.data_editor(
        st.session_state["quality_base"], hide_index=True, disabled=["code", "name"],
        key=f"quality_editor_{st.session_state['editor_v']}",
        column_config={c: st.column_config.NumberColumn(QUALITY_LABELS[c]) for c in QUALITY_COLS},
    )
    st.download_button("下載品質 CSV", edited.to_csv(index=False).encode("utf-8-sig"), "quality.csv", "text/csv")

    merged = df.merge(edited[["code"] + QUALITY_COLS], on="code", how="left")
    res = signals.evaluate(merged, y10)

    # ---- 結果 ----
    st.subheader("② 結果")
    hot = res[res["label"].str.startswith(("🔥", "🟠"))].sort_values("heat", ascending=False)
    research = res[res["label"].str.startswith(("🟢", "🔵", "🟡", "🟣"))].sort_values(["has_pe", "cheap"], ascending=[False, False])
    k = st.columns(3)
    k[0].metric("🔥／🟠 偏熱的", len(hot))
    k[1].metric("🟢／🔵／🟡／🟣 回檔觀察", len(research))
    k[2].metric("⚪ 中性", len(res) - len(hot) - len(research))

    def show(sub, empty, top=8):
        if sub.empty:
            st.caption(empty)
        if len(sub) > top:
            st.caption(f"共 {len(sub)} 檔，這裡列出最明顯的前 {top} 檔，完整清單在下方『全部明細』。")
        for _, r in sub.head(top).iterrows():
            st.markdown(f"**{r['name']}** `{r['code']}`　{r['label']}")
            st.caption(r["reasons"] or "—")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🔥 過熱／偏貴：先別追高，做風險檢查")
        show(hot, "沒有明顯過熱的標的。")
    with c2:
        st.markdown("#### 🟢 回檔觀察：優先做功課")
        show(research, "目前沒有符合條件的標的。")
    st.caption("『過熱』不代表馬上會跌，強勢股可以更熱；『回檔』不代表便宜，可能是基本面變差。"
               "🟢 = 價格訊號 + 你填的品質數字都過關；🔵 = 價格訊號有，但品質還沒驗證；🟡 = 價格低但品質數字有缺口，價值陷阱風險；🟣 = 目前虧損或沒有 P/E，回檔不代表便宜，風險最高。")

    with st.expander("全部明細"):
        out = pd.DataFrame({
            "代號": res["code"], "名稱": res["name"], "現價": res["price"].round(2),
            "P/E(TTM)": res["pe"].round(1), "盈餘殖利率%": res["ey"].round(1), "比10Y多給(ERP)": res["erp"].round(1),
            "52週位置%": (res["pos52"] * 100).round(0), "距高點回檔%": (res["drawdown"] * 100).round(0),
            "RSI": res["rsi"].round(0), "距200日線%": (res["dist200"] * 100).round(0),
            "過熱分": res["heat"], "回檔分": res["cheap"], "品質通過率": (res["quality"] * 100).round(0),
            "技術面": np.where(res["rsi"].notna(), "✓", "—"), "判斷": res["label"],
        })
        st.dataframe(out, hide_index=True)

    with st.expander("判斷規則（全部公開，可自己檢驗）"):
        st.markdown(
            f"""
**過熱分**（≥4 🔥；2–3 🟠）
- RSI(14) ≥ {signals.RSI_HOT} 得 1 分，≥ {signals.RSI_VERY_HOT} 得 2 分
- 股價高於 200 日線 ≥ {signals.DIST200_HOT:.0%} 得 1 分，≥ {signals.DIST200_VERY_HOT:.0%} 得 2 分
- 位於 52 週區間 ≥ {signals.POS52_HOT:.0%}（貼近高點）得 1 分
- 盈餘殖利率（1 ÷ P/E）低於 10 年期公債殖利率得 1 分（股票沒有給出額外補償，單元 4）
- P/E ≥ {signals.PE_HIGH} 得 1 分

**回檔分**（≥2 且過熱分 ≤1 才進入回檔觀察）
- RSI ≤ {signals.RSI_COLD} 得 1 分
- 距 52 週高點回檔 ≥ {signals.DRAWDOWN_MILD:.0%} 得 1 分，≥ {signals.DRAWDOWN_DEEP:.0%} 得 2 分
- 盈餘殖利率高於 10 年期殖利率得 1 分

**品質（你填的）**：ROIC ≥ 12%、FCF÷淨利 ≥ 70%、淨負債/EBITDA ≤ 3、利息保障 ≥ 5。通過率 ≥ 75% 才算『品質過關』。

**局限**
- 這些是價格與粗略估值訊號；公司的護城河、成長品質、財報細節它看不到（請用單元 13 檢查表）。
- 沒有 P/E 的標的（虧損公司、部分 ETF）無法評估估值，只用價格訊號。
- 門檻是經驗值，會隨利率環境而變；10 年期殖利率在 5% 時，大多數高 P/E 股票的盈餘殖利率都會低於債券。
- 技術訊號滯後，也可能被消息面打破（如單日財報、戰事）。
"""
        )
    st.markdown("**下一步**：挑一檔 🟢／🔵 → 到『13. 實戰檢查表』逐項打分 → 到『12. 估值』用 DCF 與敏感度表看看市場在假設什麼。")
