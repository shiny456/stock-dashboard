import streamlit as st


def quiz(key, question, options, answer, explain):
    """單題測驗：選完按「送出」才顯示對錯與解析，成績記在 session_state。"""
    st.markdown(f"**{question}**")
    choice = st.radio("選擇答案", options, index=None, key=f"q_{key}", label_visibility="collapsed")
    if st.button("送出答案", key=f"b_{key}"):
        if choice is None:
            st.warning("先選一個答案喔")
            return
        correct = options.index(choice) == answer
        st.session_state.setdefault("scores", {})[key] = correct
        if correct:
            st.success(f"答對了！{explain}")
        else:
            st.error(f"再想想～正確答案是「{options[answer]}」。{explain}")


def takeaway(*points):
    st.info("**本課重點**\n\n" + "\n".join(f"- {p}" for p in points))


def bond_price(face, coupon_rate, ytm, years, freq=2):
    n = int(round(years * freq))
    c = face * coupon_rate / freq
    y = ytm / freq
    if y == 0:
        return c * n + face
    return sum(c / (1 + y) ** t for t in range(1, n + 1)) + face / (1 + y) ** n


def modified_duration(face, coupon_rate, ytm, years, freq=2):
    """用 ±1bp 價格差數值估算修正存續期間。"""
    p0 = bond_price(face, coupon_rate, ytm, years, freq)
    up = bond_price(face, coupon_rate, ytm + 0.0001, years, freq)
    dn = bond_price(face, coupon_rate, ytm - 0.0001, years, freq)
    return (dn - up) / (2 * p0 * 0.0001)


def curve_chart(df, y_title="殖利率 %"):
    """殖利率曲線折線圖：x 軸維持輸入順序（不照字母排序）。df 的 index 為年期標籤。"""
    import altair as alt

    order = list(df.index)
    long = df.reset_index(names="年期").melt("年期", var_name="曲線", value_name="值")
    chart = (
        alt.Chart(long)
        .mark_line(point=True)
        .encode(
            x=alt.X("年期:N", sort=order, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("值:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color("曲線:N", legend=alt.Legend(orient="bottom", title=None)),
        )
    )
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:  # 較舊版 Streamlit
        st.altair_chart(chart, use_container_width=True)
