# app.py - 템플턴S v0.5 (함수 순서 수정)
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from kis_client import KISClient
from market_data import compute_volatility, compute_momentum
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ENV, SYMBOLS
from ai_interpreter import get_coach, build_change_conditions
from decision_log import log_decision

# ── 페이지 설정 ──────────────────────────────────
st.set_page_config(
    page_title="Templeton S",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 상수 ──────────────────────────────────────────
# config.SYMBOLS를 단일 소스로 사용 (표시 순서만 여기서 지정)
_DISPLAY_ORDER = [
    "005930",  # 삼성전자
    "005380",  # 현대차
    "105560",  # KB금융
    "069500",  # KODEX 200
    "472150",  # TIGER 배당커버드콜액티브
    "360750",  # TIGER 미국S&P500
]
WATCHLIST = [
    (SYMBOLS[code], code)
    for code in _DISPLAY_ORDER
    if code in SYMBOLS
]
# 누락된 종목이 있으면 뒤에 추가
_seen = set(_DISPLAY_ORDER)
for code, name in SYMBOLS.items():
    if code not in _seen:
        WATCHLIST.append((name, code))

SCORE_VERSION = "v0.5"
APP_PHASE = "Phase 3"

# ── 헬퍼 함수 ────────────────────────────────────
def fmt_price(price) -> str:
    if price is None:
        return "—"
    try:
        return f"{float(price):,.0f}원"
    except (TypeError, ValueError):
        return "—"


def opinion_emoji(opinion: str) -> str:
    return {
        "매수 회피": "🔴",
        "관망": "🟠",
        "보유/관찰": "🟡",
        "분할매수 관심": "🟢",
        "적극적 관심": "🟢",
    }.get(opinion, "⚪")


def opinion_color(opinion: str) -> str:
    return {
        "매수 회피": "#dc2626",
        "관망": "#ea580c",
        "보유/관찰": "#ca8a04",
        "분할매수 관심": "#16a34a",
        "적극적 관심": "#15803d",
    }.get(opinion, "#6b7280")

# ── 데이터 수집 ──────────────────────────────────
@st.cache_data(ttl=60)
def collect_data():
    client = KISClient()
    results = []

    # 시장 벤치마크 조회
    try:
        benchmark = client.get_current_price(MARKET_BENCHMARK_SYMBOL)
    except Exception:
        benchmark = {
            "current_price": 0,
            "change_rate": 0.0,
        }

    for name, code in WATCHLIST:
        try:
            price = client.get_current_price(code)
            closes = client.get_daily_closes(code, 60)

            try:
                financial = client.get_financial_ratios(code)
            except Exception:
                financial = {}

            # 일봉 데이터로 Risk 관련 지표 계산
            volatility_annual = compute_volatility(closes)
            momentum_20d = compute_momentum(closes)

            # Score Engine에 전달할 데이터 구성
            score_input = {
                **price,
                "closes": closes,
                "volatility_annual": volatility_annual,
                "momentum_20d": momentum_20d,
                "candle_days": len(closes),
                "drop_from_52w_high": (
                    round(
                        (price["high_52w"] - price["current_price"])
                        / price["high_52w"]
                        * 100,
                        2,
                    )
                    if (
                        price.get("high_52w") is not None
                        and price.get("current_price") is not None
                        and price.get("high_52w") > 0
                    )
                    else None
                ),
                **financial,
            }

            score_data = calculate_templeton_score(
                score_input,
                market=benchmark,
            )

            # ── 구버전 UI/AI와의 데이터 구조 호환 ──
            change = price.get("change_rate")
            market_change = benchmark.get("change_rate")
            relative_drop = (
                market_change - change
                if market_change is not None and change is not None
                else None
            )

            high_52w = price.get("high_52w")
            current_price = price.get("current_price")
            drop_from_52w_high = (
                (high_52w - current_price) / high_52w * 100
                if high_52w and current_price is not None and high_52w > 0
                else None
            )

            score_data["context"] = {
                "signal": score_data["pessimism_inputs"].get("signal", "none"),
                "value_label": score_data["value_inputs"].get("method", "neutral"),
                "pessimism_signal": score_data["pessimism_inputs"].get(
                    "signal", "none"
                ),
                "vs_market": relative_drop,
                "risk_label": (
                    f"연율화 변동성 {score_data['risk_inputs'].get('volatility_annual'):.1f}%"
                    if score_data["risk_inputs"].get("volatility_annual") is not None
                    else "중립 (데이터 없음)"
                ),
                "vs_52w_high": drop_from_52w_high,
            }

            try:
                log_decision(
                    symbol=code,
                    name=name,
                    score_data=score_data,
                    price=price.get("current_price"),
                )
            except Exception:
                pass

            results.append({
                "name": name,
                "code": code,
                "price_data": price,
                "closes": closes,
                "score_data": score_data,
                "ok": True,
            })

        except Exception as e:
            results.append({
                "name": name,
                "code": code,
                "error": str(e),
                "ok": False,
            })

    return results, benchmark

# ── 카드 렌더링 함수 (호출 전에 정의) ─────────────
def _render_stock_card(r, market_ctx_text, show_score, show_raw):
    name = r["name"]
    code = r["code"]
    p = r["price_data"]
    s = r["score_data"]
    components = s["components"]
    ctx = s["context"]
    total = s["total"]
    opinion = s["opinion"]
    current_price = p.get("current_price", 0)

    coach = get_coach()
    ai = coach.generate_comment(
        name=name,
        code=code,
        score_data=s,
        opinion=opinion,
        market_ctx=market_ctx_text,
    )

    change_conds = build_change_conditions(
        name=name,
        score_data=s,
        current_price=current_price,
    )

    color = opinion_color(opinion)

    # ── 종목 전체 카드 ─────────────────────────────
    with st.container(border=True):

        # ── 종목명 / 코드 ───────────────────────────
        st.markdown(
            f"""
            <h3 style="margin:0 0 4px 0;">{name}</h3>
            <div style="
                color:#6b7280;
                font-size:0.85em;
                margin-bottom:12px;
            ">
                {code} · {ctx.get('signal', '—')}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 핵심 지표 ─────────────────────────────
        c1, c2, c3 = st.columns(3)

        c1.metric(
            "현재가",
            fmt_price(current_price),
        )

        c2.metric(
            "등락률",
            f"{p.get('change_rate', 0):+.2f}%",
        )

        c3.metric(
            "Score",
            f"{total:.1f}",
        )

        st.markdown(
            f"""
            **의견**
            <span style="color:{color}; font-weight:600;">
            {opinion_emoji(opinion)} {opinion}
            </span>
            """,
            unsafe_allow_html=True,
        )

        # ── 밸류에이션 ────────────────────────────
        per = p.get("per")
        pbr = p.get("pbr")
        eps = p.get("eps")

        per_str = f"{per:.1f}" if per else "—"
        pbr_str = f"{pbr:.2f}" if pbr else "—"
        eps_str = f"{eps:,.0f}" if eps else "—"

        st.caption(
            f"PER {per_str} · PBR {pbr_str} · EPS {eps_str} · "
            f"Value 근거: {ctx.get('value_label', '—')}"
        )

        st.caption(
            f"비관 신호: {ctx.get('pessimism_signal', '—')} · "
            f"시장 대비 {ctx.get('vs_market', 0):+.2f}%p"
        )

        st.caption(
            f"위험: {ctx.get('risk_label', '—')}"
        )

        # ── Score 구성요소 그래프 ──────────────────
        if show_score:
            st.markdown("**Templeton Score 구성**")

            comp_df = pd.DataFrame({
                "요소": list(components.keys()),
                "점수": list(components.values()),
            })

            st.bar_chart(
                comp_df.set_index("요소"),
                height=180,
            )

        st.caption(
            f"52주 고점 대비 {ctx.get('vs_52w_high', 0):.1f}%"
        )

        # ── AI 투자 코멘트 ─────────────────────────
        with st.expander("🤖 AI 투자 코멘트", expanded=False):

            st.info(ai["comment"])

            cp, cn = st.columns(2)

            with cp:
                st.markdown("**✓ 긍정 요인**")
                for x in ai.get("positives", []):
                    st.markdown(f"- {x}")

            with cn:
                st.markdown("**✗ 부정 요인**")
                for x in ai.get("negatives", []):
                    st.markdown(f"- {x}")

            st.markdown("**⚖️ 반대 근거**")
            st.warning(
                ai.get("counter_argument", "—")
            )

            st.markdown("**🔄 판단 변경 조건**")
            for cond in change_conds:
                st.markdown(f"- {cond}")

        # ── 원본 데이터 ────────────────────────────
        if show_raw:
            with st.expander("원본 데이터"):
                st.json({
                    "price": p,
                    "score": s,
                    "ai": ai,
                })

# ── 사이드바 ─────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    auto_refresh = st.toggle("자동 새로고침 (30초)", value=False)
    show_score = st.toggle("Score 구성요소 표시", value=True)
    show_raw = st.toggle("원본 데이터 표시", value=False)
    st.markdown("---")
    st.caption(f"Templeton Score {SCORE_VERSION}")
    st.caption("Value: PER/PBR 실계산")
    st.caption("Pessimism: 시장 대비 상태")
    st.caption("Risk: 일봉 변동성 연율화")
    st.caption("Quality: ROE/부채 · Growth: 성장률")
    st.markdown("---")
    if st.button("🔄 지금 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── 메인 ──────────────────────────────────────────
st.markdown("# 📊 TEMPLETON S")
st.caption(f"개인 투자코치 · {APP_PHASE} · AI 해석 · Score {SCORE_VERSION} · 환경: **{KIS_ENV.upper()}**")
st.caption("시장 벤치마크 KODEX 200 · 종목 하락의 성격(시장 전체 vs 개별)을 구분하는 기준")

results, benchmark = collect_data()
ok_results = [r for r in results if r["ok"]]
benchmark_chg = benchmark.get("change_rate", 0.0)

scores = [r["score_data"]["total"] for r in ok_results]
avg_score = sum(scores) / len(scores) if scores else 0
up_count = sum(1 for r in ok_results if r["price_data"].get("change_rate", 0) > 0)
down_count = sum(1 for r in ok_results if r["price_data"].get("change_rate", 0) < 0)

col1, col2, col3, col4 = st.columns(4)
col1.metric("조회 종목", f"{len(ok_results)} / {len(results)}")
col2.metric("평균 Score", f"{avg_score:.1f}")
col3.metric("상승 종목", f"{up_count}개")
col4.metric("하락 종목", f"{down_count}개")

st.markdown("---")
st.markdown("## 📋 관심 종목 현황")

market_ctx_text = (
    f"벤치마크(KODEX 200): {benchmark_chg:+.2f}%, "
    f"{up_count}개 상승 / {down_count}개 하락"
)

table_rows = []
for r in ok_results:
    p = r["price_data"]
    s = r["score_data"]
    table_rows.append({
        "종목": r["name"],
        "코드": r["code"],
        "현재가": fmt_price(p.get("current_price", 0)),
        "등락률": f"{p.get('change_rate', 0):+.2f}%",
        "52주고점대비": f"{s['context'].get('vs_52w_high', 0):.1f}%",
        "PER": f"{p.get('per', 0):.1f}" if p.get('per') else "—",
        "PBR": f"{p.get('pbr', 0):.2f}" if p.get('pbr') else "—",
        "Score": f"{s['total']:.1f}",
        "의견": opinion_emoji(s["opinion"]) + " " + s["opinion"],
    })

if table_rows:
    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("## 🔍 종목별 상세")

for i in range(0, len(ok_results), 2):
    cols = st.columns(2)
    for j, col in enumerate(cols):
        idx = i + j
        if idx >= len(ok_results):
            break
        r = ok_results[idx]
        with col:
            _render_stock_card(r, market_ctx_text, show_score, show_raw)

failed = [r for r in results if not r["ok"]]
if failed:
    with st.expander(f"⚠️ 조회 실패 종목 ({len(failed)}개)"):
        for r in failed:
            st.error(f"**{r['name']}** ({r['code']}): {r.get('error', '—')}")

st.markdown("---")
st.caption(
    f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
    f"Templeton S {APP_PHASE} ({SCORE_VERSION}) · AI는 참모, 최종 결정은 사용자"
)