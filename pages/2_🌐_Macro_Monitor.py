"""Templeton S - simple FRED macro monitor page."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "macro" / "processed" / "macro_daily.csv"

SERIES = {
    "DGS10": ("미국 10년 국채금리", "%"),
    "DFF": ("미 연방기금금리", "%"),
    "DTWEXBGS": ("미국 달러지수", ""),
    "DEXKOUS": ("USD/KRW", "원/달러"),
    "SP500": ("S&P 500", ""),
    "NASDAQCOM": ("NASDAQ 종합", ""),
}


st.set_page_config(
    page_title="Templeton S · Macro Monitor",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 Macro Monitor")
st.caption("FRED 수집 데이터의 현재 상태를 확인하는 화면입니다. 아직 Macro Score에는 사용하지 않습니다.")

if not DATA_PATH.exists():
    st.warning(
        "아직 수집 데이터 파일이 없습니다. GitHub Actions의 FRED 자동수집이 "
        "한 번 실행된 뒤 이 화면에 표시됩니다."
    )
    st.code("data/macro/processed/macro_daily.csv")
    st.stop()

try:
    df = pd.read_csv(DATA_PATH)
except Exception as exc:
    st.error(f"매크로 데이터 파일을 읽지 못했습니다: {exc}")
    st.stop()

if df.empty or "observation_date" not in df.columns:
    st.info("매크로 데이터가 아직 비어 있습니다.")
    st.stop()

df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
df = df.dropna(subset=["observation_date"]).sort_values("observation_date")

available = [sid for sid in SERIES if sid in df.columns]
if not available:
    st.info("표시할 FRED 시계열이 아직 없습니다.")
    st.stop()

latest_date = df["observation_date"].max()
st.caption(
    f"최근 관측일: {latest_date.strftime('%Y-%m-%d')} · "
    f"표시 시계열: {len(available)}개"
)

cols = st.columns(3)
for i, sid in enumerate(available):
    row = df[["observation_date", sid]].dropna().tail(1)
    if row.empty:
        continue

    value = float(row.iloc[0][sid])
    obs_date = row.iloc[0]["observation_date"]
    name, unit = SERIES[sid]

    if sid in ("DGS10", "DFF"):
        value_text = f"{value:.2f}%"
    elif sid == "DEXKOUS":
        value_text = f"{value:,.2f}원"
    else:
        value_text = f"{value:,.2f}"

    with cols[i % 3]:
        st.metric(name, value_text)
        st.caption(f"{sid} · 관측일 {obs_date.strftime('%Y-%m-%d')}")

st.markdown("---")
st.subheader("최근 추이")

period_days = st.selectbox(
    "표시 기간",
    [30, 90, 180],
    index=0,
    format_func=lambda x: f"최근 {x}일",
)

plot_df = df.set_index("observation_date")
for sid in available:
    series = plot_df[sid].dropna().tail(period_days)
    if series.empty:
        continue

    name, unit = SERIES[sid]
    st.markdown(f"**{name} ({sid})**")
    st.line_chart(series, height=180)
    st.caption(f"단위: {unit or 'FRED 원자료 단위'} · 수집 시점/수정 이력은 raw CSV에서 확인")

with st.expander("데이터 상태"):
    status_rows = []
    for sid in available:
        series = df[["observation_date", sid]].dropna()
        status_rows.append(
            {
                "시계열": sid,
                "설명": SERIES[sid][0],
                "관측치 수": len(series),
                "최초 관측일": series["observation_date"].min().strftime("%Y-%m-%d"),
                "최근 관측일": series["observation_date"].max().strftime("%Y-%m-%d"),
            }
        )
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

st.caption(
    "주의: 현재 레이어는 관측값 수집/모니터링 단계입니다. "
    "실시간 빈티지 재현이나 과거 시점의 수정 전 값 복원은 아직 지원하지 않습니다."
)
