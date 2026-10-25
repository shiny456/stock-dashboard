"""自選股的『過熱／回檔／品質』訊號運算。純函式，不依賴富途或 Streamlit，方便測試。

這些是教學用的規則式篩選，不是買賣建議：價格與估值訊號只能告訴你『該先研究誰、該對誰保持警覺』。
"""
import numpy as np
import pandas as pd

# 門檻（頁面上的說明會引用這些數字）
RSI_HOT, RSI_VERY_HOT, RSI_COLD = 70, 80, 30
DIST200_HOT, DIST200_VERY_HOT = 0.30, 0.50
POS52_HOT = 0.95
PE_HIGH = 40
DRAWDOWN_MILD, DRAWDOWN_DEEP = 0.25, 0.40
QUALITY_RULES = {  # 欄位: (比較, 門檻, 說明)
    "roic": (">=", 12.0, "ROIC ≥ 12%"),
    "fcf_conv": (">=", 70.0, "FCF ÷ 淨利 ≥ 70%"),
    "nd_ebitda": ("<=", 3.0, "淨負債/EBITDA ≤ 3x"),
    "coverage": (">=", 5.0, "利息保障 ≥ 5x"),
}


def rsi(close, n=14):
    """Wilder RSI。close 為由舊到新的價格序列；資料不足回傳 NaN。"""
    close = pd.Series(close, dtype=float).dropna()
    if len(close) < n + 1:
        return np.nan
    delta = close.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.iloc[:n].mean()
    avg_loss = loss.iloc[:n].mean()
    for g, l in zip(gain.iloc[n:], loss.iloc[n:]):
        avg_gain = (avg_gain * (n - 1) + g) / n
        avg_loss = (avg_loss * (n - 1) + l) / n
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def tech_from_closes(close):
    """由日 K 收盤價算 RSI 與距離 200 日線的幅度。"""
    close = pd.Series(close, dtype=float).dropna()
    out = {"rsi": rsi(close), "dist200": np.nan, "dist50": np.nan}
    if len(close) >= 200:
        out["dist200"] = close.iloc[-1] / close.iloc[-200:].mean() - 1
    if len(close) >= 50:
        out["dist50"] = close.iloc[-1] / close.iloc[-50:].mean() - 1
    return out


def _valid(x):
    return x is not None and not (isinstance(x, float) and np.isnan(x))


def evaluate(df, y10):
    """輸入欄位：code, name, price, high52, low52, pe, (rsi, dist200), (roic, fcf_conv, nd_ebitda, coverage)。
    回傳加上 pos52, drawdown, ey, erp, heat, cheap, quality, label, reasons 的 DataFrame。"""
    rows = []
    for _, r in df.iterrows():
        heat, cheap = 0, 0
        why_hot, why_cold = [], []

        price, hi, lo = r.get("price"), r.get("high52"), r.get("low52")
        pos52 = (price - lo) / (hi - lo) if _valid(hi) and _valid(lo) and hi > lo else np.nan
        drawdown = 1 - price / hi if _valid(hi) and hi > 0 else np.nan

        pe = r.get("pe")
        pe_ok = _valid(pe) and pe > 0
        ey = 100 / pe if pe_ok else np.nan
        erp = ey - y10 if pe_ok else np.nan

        rs = r.get("rsi", np.nan)
        d200 = r.get("dist200", np.nan)

        if _valid(rs):
            if rs >= RSI_VERY_HOT:
                heat += 2; why_hot.append(f"RSI {rs:.0f}（≥{RSI_VERY_HOT}）")
            elif rs >= RSI_HOT:
                heat += 1; why_hot.append(f"RSI {rs:.0f}（≥{RSI_HOT}）")
            elif rs <= RSI_COLD:
                cheap += 1; why_cold.append(f"RSI {rs:.0f}（≤{RSI_COLD}）")
        if _valid(d200):
            if d200 >= DIST200_VERY_HOT:
                heat += 2; why_hot.append(f"高於 200 日線 {d200:.0%}")
            elif d200 >= DIST200_HOT:
                heat += 1; why_hot.append(f"高於 200 日線 {d200:.0%}")
        if _valid(pos52) and pos52 >= POS52_HOT:
            heat += 1; why_hot.append(f"貼近 52 週高點（位置 {pos52:.0%}）")
        if pe_ok:
            if erp < 0:
                heat += 1; why_hot.append(f"盈餘殖利率 {ey:.1f}% 低於 10Y {y10:.2f}%")
            else:
                cheap += 1; why_cold.append(f"盈餘殖利率高於 10Y {erp:+.1f} 個百分點")
            if pe >= PE_HIGH:
                heat += 1; why_hot.append(f"P/E {pe:.0f}（≥{PE_HIGH}）")
        if _valid(drawdown):
            if drawdown >= DRAWDOWN_DEEP:
                cheap += 2; why_cold.append(f"距 52 週高點回檔 {drawdown:.0%}")
            elif drawdown >= DRAWDOWN_MILD:
                cheap += 1; why_cold.append(f"距 52 週高點回檔 {drawdown:.0%}")

        # 品質（使用者自填；沒填就不評）
        got, passed, fails = 0, 0, []
        for col, (op, th, txt) in QUALITY_RULES.items():
            v = r.get(col, np.nan)
            if _valid(v):
                got += 1
                ok = v >= th if op == ">=" else v <= th
                passed += ok
                if not ok:
                    fails.append(txt)
        quality = passed / got if got >= 3 else np.nan

        if heat >= 4:
            label = "🔥 過熱警示"
        elif heat >= 2:
            label = "🟠 偏熱／偏貴"
        elif cheap >= 2 and heat <= 1:
            if _valid(quality):
                label = "🟢 優先研究" if quality >= 0.75 else "🟡 價格低但品質存疑"
            else:
                label = "🔵 回檔中（品質未驗證）"
        else:
            label = "⚪ 中性"

        reasons = "；".join(why_hot + why_cold + ([f"未達：{'、'.join(fails)}"] if fails else []))
        rows.append({**r.to_dict(), "pos52": pos52, "drawdown": drawdown, "ey": ey, "erp": erp,
                     "heat": heat, "cheap": cheap, "quality": quality, "label": label, "reasons": reasons})
    return pd.DataFrame(rows)
