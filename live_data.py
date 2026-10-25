"""即時總經數據：從 FRED 公開 CSV 抓取（不需要 API key）。失敗時回傳 None，由頁面改用 JSON 快照。"""
import io

import pandas as pd
import requests
import streamlit as st

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"


@st.cache_data(ttl=3600, show_spinner=False)
def fred(series_id, start="2024-10-01"):
    r = requests.get(FRED_URL.format(sid=series_id, start=start), timeout=8)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna()


def _yoy(s):
    """用日期對齊『12 個月前』，不用位置（官方資料偶有缺月，例如停擺期間）。"""
    prev = s.index[-1] - pd.DateOffset(years=1)
    return (s.iloc[-1] / s.loc[prev] - 1) * 100


@st.cache_data(ttl=3600, show_spinner=False)
def snapshot():
    """回傳最新總經快照 dict；任何錯誤回傳 None。"""
    try:
        y10, y2, y3m = fred("DGS10"), fred("DGS2"), fred("DGS3MO")
        up, low = fred("DFEDTARU"), fred("DFEDTARL")
        cpi, core = fred("CPIAUCNS"), fred("CPILFENS")
        payems, unrate = fred("PAYEMS"), fred("UNRATE")
        return {
            "ff_low": float(low.iloc[-1]), "ff_high": float(up.iloc[-1]),
            "y10": float(y10.iloc[-1]), "y2": float(y2.iloc[-1]), "y3m": float(y3m.iloc[-1]),
            "y_date": y10.index[-1].strftime("%Y-%m-%d"),
            "cpi_yoy": float(_yoy(cpi)), "core_yoy": float(_yoy(core)),
            "cpi_month": cpi.index[-1].strftime("%Y-%m"),
            "nfp_change_k": float(payems.iloc[-1] - payems.iloc[-2]),
            "unrate": float(unrate.iloc[-1]), "unrate_prev": float(unrate.iloc[-2]),
            "emp_month": payems.index[-1].strftime("%Y-%m"),
        }
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def yield_curve():
    """回傳 DataFrame：index 為年期，欄位為『最新』與『一年前』。失敗回傳 None。"""
    ids = {"3M": "DGS3MO", "2Y": "DGS2", "5Y": "DGS5", "10Y": "DGS10", "30Y": "DGS30"}
    try:
        now, ago = {}, {}
        for label, sid in ids.items():
            s = fred(sid)
            now[label] = float(s.iloc[-1])
            past = s[s.index <= s.index[-1] - pd.Timedelta(days=365)]
            ago[label] = float(past.iloc[-1])
        date = fred("DGS10").index[-1].strftime("%Y-%m-%d")
        return pd.DataFrame({f"最新 ({date})": now, "一年前": ago}), date
    except Exception:
        return None, None
