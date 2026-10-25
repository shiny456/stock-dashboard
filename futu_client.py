"""富途 OpenAPI 連線（唯讀：自選股、報價快照、日 K）。不含任何交易功能。

需要先在本機啟動並登入 OpenD。futu-api 只在本機使用，不放進 requirements.txt（見 requirements-local.txt）。
"""
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from signals import tech_from_closes


def futu_available():
    try:
        import futu  # noqa: F401
        return True
    except Exception:
        return False


_TECH = {}  # code -> (日期, {'rsi','dist200'})：同一天不重複請求日 K


class FutuError(Exception):
    pass


def _check(ret, data, what):
    from futu import RET_OK
    if ret != RET_OK:
        raise FutuError(f"{what}失敗：{data}")
    return data


def list_groups(host, port):
    from futu import OpenQuoteContext
    ctx = OpenQuoteContext(host=host, port=port)
    try:
        ret, data = ctx.get_user_security_group(group_type="ALL")
        return list(_check(ret, data, "取得自選股分組")["group_name"])
    finally:
        ctx.close()


@st.cache_data(ttl=900, show_spinner=False)
def load_watchlist(host, port, group, use_kline, max_kline):
    """回傳 (DataFrame, 備註列表)。欄位：code, name, price, high52, low52, pe, rsi, dist200。"""
    from futu import RET_OK, OpenQuoteContext

    notes = []
    ctx = OpenQuoteContext(host=host, port=port)
    try:
        sec = _check(*ctx.get_user_security(group), "讀取自選股")
        sec = sec[sec["code"].astype(str).str.startswith("US.")]
        if "stock_type" in sec.columns:
            sec = sec[sec["stock_type"].astype(str).isin(["STOCK", "ETF"])]
        codes = list(sec["code"])
        if not codes:
            raise FutuError(f"分組『{group}』中沒有美股股票或 ETF")

        snaps = []
        for i in range(0, len(codes), 400):  # 單次最多 400 檔
            snaps.append(_check(*ctx.get_market_snapshot(codes[i:i + 400]), "取得報價快照"))
        snap = pd.concat(snaps, ignore_index=True)
        df = pd.DataFrame({
            "code": snap["code"], "name": snap["name"], "price": snap["last_price"],
            "high52": snap["highest52weeks_price"], "low52": snap["lowest52weeks_price"],
            "pe": snap["pe_ttm_ratio"],
        })
        df["rsi"], df["dist200"] = np.nan, np.nan

        if use_kline:
            import signals

            start = (date.today() - timedelta(days=420)).strftime("%Y-%m-%d")
            end = date.today().strftime("%Y-%m-%d")

            # 歷史 K 線有額度（約 7 天釋放）。已經抓過的股票不再耗額度，優先處理；
            # 剩餘額度再依『只看報價就已有明顯訊號』的程度分配。
            ret, q = ctx.get_history_kl_quota(get_detail=True)
            fetched, remain = set(), max_kline
            if ret == RET_OK:
                _, remain_quota, detail = q
                fetched = {d["code"] for d in detail}
                remain = min(max_kline, max(remain_quota - 3, 0))  # 留 3 檔緩衝
            pre = signals.evaluate(df, 4.5)
            pre["strength"] = pre["heat"] + pre["cheap"]
            ranked = list(pre.sort_values("strength", ascending=False)["code"])
            free = [c for c in ranked if c in fetched]
            new = [c for c in ranked if c not in fetched][:remain]
            targets = free + new
            skipped = len(df) - len(targets)
            if skipped > 0:
                notes.append(f"歷史 K 線額度有限，這次有 {skipped} 檔沒有計算 RSI／200 日線（只用報價與估值訊號）。"
                             f"已抓過的 {len(free)} 檔不再耗額度。")
            today = date.today().isoformat()
            for code in targets:
                idx = df.index[df["code"] == code][0]
                if code in _TECH and _TECH[code][0] == today:
                    df.loc[idx, "rsi"], df.loc[idx, "dist200"] = _TECH[code][1]["rsi"], _TECH[code][1]["dist200"]
                    continue
                ret, data, _ = ctx.request_history_kline(code, start=start, end=end, ktype="K_DAY", autype="qfq")
                if ret != RET_OK:
                    notes.append(f"{code} 日 K 取得失敗：{data}")
                else:
                    t = tech_from_closes(data["close"])
                    _TECH[code] = (today, t)
                    df.loc[idx, "rsi"], df.loc[idx, "dist200"] = t["rsi"], t["dist200"]
                time.sleep(0.55)  # 官方限制：30 秒最多 60 次
        return df, notes
    finally:
        ctx.close()


def demo_watchlist():
    """示範用虛構資料（不是真實股票）。"""
    rows = [
        # name, price, high52, low52, pe, rsi, dist200
        ("示範・高成長龍頭", 180, 185, 90, 62, 84, 0.58),
        ("示範・穩健配息股", 95, 110, 82, 18, 55, 0.04),
        ("示範・回檔中的優質股", 140, 215, 125, 24, 28, -0.12),
        ("示範・便宜的重債公司", 22, 38, 20, 7, 31, -0.22),
        ("示範・景氣循環股", 60, 66, 40, 9, 62, 0.18),
        ("示範・題材熱炒股", 75, 78, 20, np.nan, 78, 0.65),
        ("示範・大型指數 ETF", 520, 535, 430, 22, 61, 0.09),
        ("示範・被殺過頭的科技股", 48, 95, 45, 15, 24, -0.30),
    ]
    return pd.DataFrame(
        [{"code": f"DEMO.{i + 1}", "name": n, "price": p, "high52": h, "low52": l, "pe": pe, "rsi": rs, "dist200": d}
         for i, (n, p, h, l, pe, rs, d) in enumerate(rows)]
    )
