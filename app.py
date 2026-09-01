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
from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_ENV, SYMBOLS, DART_API_KEY
from ai_interpreter import get_coach, build_change_conditions
from decision_log import log_decision, recent_decisions, decisions_as_table_rows
from events.dart_client import DartClient
from events.trigger import should_refetch_events, trigger_reason
from regime.market_regime import detect_market_regime
from regime.panic_classifier import classify_stock_panic
from regime.opportunity_rank import rank_opportunities
from market_overview import fetch_market_overview
from post_verify import load_and_verify, verified_table_rows

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
APP_PHASE = "Phase 6"

# ── 헬퍼 함수 ────────────────────────────────────
def fmt_price(price) -> str:
    if price is None:
        return "—"
    try:
        return f"{float(price):,.0f}원"
    except (TypeError, ValueError):
        return "—"



def humanize_error(err: str) -> str:
    """API/설정 오류를 사용자용 짧은 안내로 변환."""
    e = (err or "").lower()
    raw = err or "알 수 없는 오류"
    if "kis_app_key" in e or "kis_app_secret" in e or "필수 환경변수" in e:
        return "API 키가 없습니다. 로컬은 config/.env, 웹은 Streamlit Secrets에 KIS_APP_KEY / KIS_APP_SECRET을 넣으세요."
    if "401" in e or "unauthorized" in e or "egw001" in e:
        return "인증 실패(401). 키·시크릿이 맞는지, KIS_ENV(paper/real)와 앱키 종류가 일치하는지 확인하세요."
    if "403" in e or "forbidden" in e or "ip" in e:
        return "접근 거부(403/IP). KIS 포털에 접속 IP가 등록됐는지 확인하세요. Cloud 배포 시 IP가 달라질 수 있습니다."
    if "timeout" in e or "timed out" in e:
        return "응답 시간 초과. 네트워크 또는 KIS 서버 지연일 수 있습니다. 잠시 후 새로고침하세요."
    if "500" in e or "502" in e or "503" in e:
        return "KIS 서버 일시 오류. 잠시 후 다시 시도하세요."
    if "json" in e and "아님" in raw:
        return "KIS 응답이 비정상입니다. 점검 시간이거나 토큰 문제일 수 있습니다."
    if len(raw) > 180:
        return raw[:180] + "…"
    return raw


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
@st.cache_data(ttl=600)
def fetch_disclosures():
    """DART 공시 (키 없으면 빈 dict). TTL 10분."""
    client = DartClient(DART_API_KEY)
    if not client.enabled:
        return {}
    out = {}
    for name, code in WATCHLIST:
        try:
            events = client.get_recent_disclosures(code, name=name, days=45, max_count=5)
            out[code] = [e.to_dict() for e in events]
        except Exception as e:
            out[code] = []
    return out


@st.cache_data(ttl=120)
def fetch_markets():
    """한·미·일 주요 지수/대용. TTL 2분."""
    try:
        return fetch_market_overview(KISClient())
    except Exception as e:
        return [{"key": "error", "name": "시장요약", "ok": False, "error": str(e),
                 "price": None, "change_rate": None, "closes": [], "region": ""}]


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
    try:
        benchmark_closes = client.get_daily_closes(MARKET_BENCHMARK_SYMBOL, 10)
    except Exception:
        benchmark_closes = []

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

            # ── Phase 4.4: 급락 트리거 → 공시 조회 ──
            mkt_chg = benchmark.get("change_rate")
            need_events = should_refetch_events(change, mkt_chg)
            reason = trigger_reason(change, mkt_chg)
            events_for_stock: list = []
            if need_events and DART_API_KEY:
                try:
                    dart = DartClient(DART_API_KEY)
                    events_for_stock = [
                        e.to_dict()
                        for e in dart.get_recent_disclosures(
                            code, name=name, days=30, max_count=5
                        )
                    ]
                except Exception:
                    events_for_stock = []
            # critical/high 공시는 트리거와 무관하게 캐시 맵에서 보강 (아래 메인에서 merge 가능)
            event_ids = [
                str(ev.get("event_id"))
                for ev in events_for_stock
                if isinstance(ev, dict) and ev.get("event_id")
            ]

            results.append({
                "name": name,
                "code": code,
                "price_data": price,
                "closes": closes,
                "score_data": score_data,
                "events": events_for_stock,
                "event_trigger": reason if need_events else "none",
                "event_triggered": need_events,
                "ok": True,
            })

        except Exception as e:
            results.append({
                "name": name,
                "code": code,
                "error": str(e),
                "error_user": humanize_error(str(e)),
                "ok": False,
            })

    return results, benchmark, benchmark_closes

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

    events = r.get("events") or []
    event_triggered = bool(r.get("event_triggered"))
    # 급락 트리거이거나 high/critical 공시가 있으면 AI에 공시 전달
    events_for_ai = events if (
        event_triggered
        or any(
            isinstance(ev, dict) and ev.get("importance") in ("high", "critical")
            for ev in events
        )
    ) else events  # 트리거 아니어도 조회된 공시는 참고용 전달 (최대 활용)
    # 정책: 트리거 시에만 강제 포함, 그 외에는 공시가 있으면 포함
    if not event_triggered and not events:
        events_for_ai = None
    elif not event_triggered:
        # 평시에도 medium 이상만 전달해 노이즈 감소
        events_for_ai = [
            ev for ev in events
            if isinstance(ev, dict) and ev.get("importance") in ("medium", "high", "critical")
        ] or None

    coach = get_coach()
    ai = coach.generate_comment(
        name=name,
        code=code,
        score_data=s,
        opinion=opinion,
        market_ctx=market_ctx_text,
        events=events_for_ai,
    )

    change_conds = build_change_conditions(
        name=name,
        score_data=s,
        current_price=current_price,
    )
    if event_triggered:
        change_conds = [
            f"이벤트 트리거 활성 ({r.get('event_trigger')}) — 공시·뉴스 재확인"
        ] + change_conds
        change_conds = change_conds[:5]

    color = opinion_color(opinion)

    # ── 종목 전체 카드 ─────────────────────────────
    with st.container(border=True):

        # ── 종목명 / 코드 ───────────────────────────
        trigger_badge = ""
        if r.get("event_triggered"):
            trigger_badge = (
                f" · <span style=\"color:#dc2626;font-weight:600;\">"
                f"⚡ 이벤트 트리거 {r.get('event_trigger', '')}</span>"
            )
        n_ev = len(r.get("events") or [])
        ev_badge = f" · 공시 {n_ev}건" if n_ev else ""
        pc = r.get("panic_class") or {}
        panic_badge = ""
        if pc.get("type") and pc.get("type") not in ("none",):
            panic_badge = f" · <span style=\"color:#b45309;\">{pc.get('label_ko', '')}</span>"
        if r.get("opportunity_rank"):
            panic_badge += f" · 검토순위 {r.get('opportunity_rank')}"

        st.markdown(
            f"""
            <h3 style="margin:0 0 4px 0;">{name}</h3>
            <div style="
                color:#6b7280;
                font-size:0.85em;
                margin-bottom:12px;
            ">
                {code} · {ctx.get('signal', '—')}{trigger_badge}{ev_badge}{panic_badge}
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
            <div style="margin:8px 0 12px 0; padding:10px 12px; border-radius:8px;
                        background:#f8fafc; border-left:4px solid {color};">
              <div style="font-size:0.8rem; color:#64748b; margin-bottom:2px;">투자 의견 (AI는 참모)</div>
              <div style="font-size:1.15rem; font-weight:700; color:{color};">
                {opinion_emoji(opinion)} {opinion}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 밸류에이션 · 맥락 한 블록 ─────────────
        per = p.get("per")
        pbr = p.get("pbr")
        eps = p.get("eps")

        per_str = f"{per:.1f}" if per else "—"
        pbr_str = f"{pbr:.2f}" if pbr else "—"
        eps_str = f"{eps:,.0f}" if eps else "—"
        vs_m = ctx.get("vs_market")
        vs_m_str = f"{vs_m:+.2f}%p" if isinstance(vs_m, (int, float)) else "—"

        st.markdown("**근거 요약**")
        st.caption(
            f"PER {per_str} · PBR {pbr_str} · EPS {eps_str} · "
            f"Value `{ctx.get('value_label', '—')}`"
        )
        st.caption(
            f"비관 `{ctx.get('pessimism_signal', '—')}` · 시장 대비 {vs_m_str} · "
            f"{ctx.get('risk_label', '—')}"
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
        with st.expander("🤖 판단 상세 (근거 · 반대 · 변경 조건)", expanded=False):

            st.markdown("##### 종합 코멘트")
            st.info(ai.get("comment") or "—")

            if events_for_ai:
                st.markdown("##### 반영된 공시")
                for ev in events_for_ai[:5]:
                    if not isinstance(ev, dict):
                        continue
                    st.markdown(
                        f"- `{ev.get('importance', '—')}` "
                        f"{ev.get('title', '—')} "
                        f"({ev.get('ts', '')})"
                    )

            st.markdown("##### 긍정 · 부정 요인")
            cp, cn = st.columns(2)
            with cp:
                st.success("긍정")
                for x in ai.get("positives", []) or ["—"]:
                    st.markdown(f"- {x}")
            with cn:
                st.error("부정·주의")
                for x in ai.get("negatives", []) or ["—"]:
                    st.markdown(f"- {x}")

            st.markdown("##### 반대 근거 (왜 틀릴 수 있는가)")
            st.warning(ai.get("counter_argument") or "—")

            st.markdown("##### 이 판단을 바꿀 조건")
            for cond in change_conds:
                st.markdown(f"- {cond}")
            st.caption(f"해석 소스: {ai.get('source', '—')} · 최종 결정은 사용자")

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
    st.caption("Phase 4: DART 공시 " + ("ON" if DART_API_KEY else "OFF"))
    st.caption("Phase 5-R: 시장모드·기회순위")
    st.caption("Phase 6: 사후 검증(1주/1개월)")
    st.markdown("---")
    if st.button("🔄 지금 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── 메인 ──────────────────────────────────────────
st.markdown("# 📊 TEMPLETON S")
st.caption(f"개인 투자코치 · {APP_PHASE} · AI 해석 · Score {SCORE_VERSION} · 환경: **{KIS_ENV.upper()}**")
st.caption("시장 벤치마크 KODEX 200 · 종목 하락의 성격(시장 전체 vs 개별)을 구분하는 기준")

# ── 주요 시장 요약 (한·미·일) ─────────────────────
_markets = fetch_markets()
if _markets and not (len(_markets) == 1 and _markets[0].get("key") == "error"):
    mcols = st.columns(len(_markets))
    for col, m in zip(mcols, _markets):
        with col:
            chg = m.get("change_rate")
            price = m.get("price")
            if m.get("ok") and price is not None:
                delta = f"{chg:+.2f}%" if chg is not None else None
                # 지수는 소수점, 한국은 보통 2자리
                if price >= 1000:
                    pstr = f"{price:,.2f}"
                else:
                    pstr = f"{price:,.2f}"
                col.metric(m.get("name") or m.get("key"), pstr, delta=delta)
            else:
                col.metric(m.get("name") or "—", "—", delta=None)

    with st.expander("📈 최근 추이 그래프 (약 1개월)", expanded=False):
        chart_cols = st.columns(min(3, max(1, len([x for x in _markets if x.get("closes")]))))
        plotted = 0
        for m in _markets:
            closes = m.get("closes") or []
            if len(closes) < 2:
                continue
            df = pd.DataFrame({"종가": closes})
            with chart_cols[plotted % len(chart_cols)]:
                st.caption(m.get("name") or m.get("key"))
                st.line_chart(df, height=180)
            plotted += 1
        if plotted == 0:
            st.caption("그래프용 일봉을 아직 받지 못했습니다.")
        srcs = sorted({m.get("source") for m in _markets if m.get("source")})
        if srcs:
            st.caption("데이터: " + ", ".join(str(s) for s in srcs) + " · 참고용(지연 가능)")
else:
    st.caption("주요 시장 요약을 불러오지 못했습니다.")

# 설정 점검 (웹 Secrets / 로컬 .env)
_missing_keys = []
if not KIS_APP_KEY:
    _missing_keys.append("KIS_APP_KEY")
if not KIS_APP_SECRET:
    _missing_keys.append("KIS_APP_SECRET")
if _missing_keys:
    st.error(
        "**필수 API 키가 없습니다:** "
        + ", ".join(_missing_keys)
        + "\n\n로컬: `config/.env` · 웹(Streamlit Cloud): **Settings → Secrets** (TOML, 값은 따옴표)"
    )
elif KIS_ENV == "real":
    st.caption("⚠️ 실전(KIS_ENV=real) 모드입니다. Cloud에서는 IP 허용 여부를 확인하세요.")

results, benchmark, benchmark_closes = collect_data()

# 평시에도 캐시된 DART 공시를 카드/로그 보강용으로 병합 (트리거로 이미 넣은 경우 유지)
try:
    disc_map = fetch_disclosures() if DART_API_KEY else {}
except Exception:
    disc_map = {}
for r in results:
    if not r.get("ok"):
        continue
    if r.get("events"):
        continue
    cached = disc_map.get(r["code"]) or []
    if cached:
        r["events"] = cached
        # 중요 공시만 있을 때 event_ids를 후행 기록하지는 않음 (중복 로그 방지)

ok_results = [r for r in results if r["ok"]]
benchmark_chg = benchmark.get("change_rate", 0.0)

# ── Phase 5-R: 시장 모드 · 공황 분류 · 기회 순위 ──
_day_changes = [r["price_data"].get("change_rate") for r in ok_results]
_regime = detect_market_regime(
    benchmark_closes,
    _day_changes,
    benchmark_day_change=benchmark_chg,
)
for r in ok_results:
    r["panic_class"] = classify_stock_panic(
        market_regime=_regime.regime,
        change_rate=r["price_data"].get("change_rate"),
        market_change=benchmark_chg,
        events=r.get("events") or [],
    )
_ranked = rank_opportunities(ok_results)
_rank_map = {x["code"]: x for x in _ranked}
for r in ok_results:
    rr = _rank_map.get(r["code"])
    if rr:
        r["opportunity_rank"] = rr.get("opportunity_rank")
        r["opportunity_score"] = rr.get("opportunity_score")
    else:
        r["opportunity_rank"] = None
        r["opportunity_score"] = None

# 판단 기록 (중복 억제 포함, 모드·순위 저장)
for r in ok_results:
    try:
        log_decision(
            symbol=r["code"],
            name=r["name"],
            score_data=r["score_data"],
            price=r["price_data"].get("current_price"),
            event_ids=[
                str(ev.get("event_id"))
                for ev in (r.get("events") or [])
                if isinstance(ev, dict) and ev.get("event_id")
            ],
            event_trigger=r.get("event_trigger") or "none",
            market_regime=_regime.regime,
            panic_type=(r.get("panic_class") or {}).get("type"),
            opportunity_rank=r.get("opportunity_rank"),
            opportunity_score=r.get("opportunity_score"),
        )
    except Exception:
        pass

scores = [r["score_data"]["total"] for r in ok_results]
avg_score = sum(scores) / len(scores) if scores else 0
up_count = sum(1 for r in ok_results if r["price_data"].get("change_rate", 0) > 0)
down_count = sum(1 for r in ok_results if r["price_data"].get("change_rate", 0) < 0)

col1, col2, col3, col4 = st.columns(4)
col1.metric("조회 종목", f"{len(ok_results)} / {len(results)}")
col2.metric("평균 Score", f"{avg_score:.1f}")
col3.metric("상승 종목", f"{up_count}개")
col4.metric("하락 종목", f"{down_count}개")

# 시장 모드 배지
_reg_colors = {
    "normal": "#64748b",
    "watch": "#ca8a04",
    "panic_zone": "#dc2626",
}
_rc = _reg_colors.get(_regime.regime, "#64748b")
st.markdown(
    f"""
    <div style="margin:12px 0; padding:12px 16px; border-radius:10px;
                border-left:5px solid {_rc}; background:#f8fafc;">
      <div style="font-size:0.85rem; color:#64748b;">시장 모드 (2~3일 관찰 후 확정 · 급매수 권유 없음)</div>
      <div style="font-size:1.25rem; font-weight:700; color:{_rc};">{_regime.label_ko}</div>
      <div style="font-size:0.9rem; color:#334155; margin-top:6px;">
        1일 {_regime.bench_1d if _regime.bench_1d is not None else '—'}%
        · 2일 {_regime.bench_2d if _regime.bench_2d is not None else '—'}%
        · 3일 {_regime.bench_3d if _regime.bench_3d is not None else '—'}%
        · 관심종목 하락비율 {f'{_regime.down_ratio:.0%}' if _regime.down_ratio is not None else '—'}
      </div>
      <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
        {" · ".join(_regime.reasons[:3])}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if _regime.regime in ("watch", "panic_zone"):
    with st.expander(
        "📉 가치 기준 검토 순위 (분할매수 검토 후보 · 자동매수 아님)",
        expanded=(_regime.regime == "panic_zone"),
    ):
        st.caption(
            "공포 구간에서는 서두르지 않습니다. "
            "가치·품질·낙폭·공시 분류를 종합한 검토 순서입니다."
        )
        opp_rows = []
        for item in _ranked:
            pc = item.get("panic_class") or {}
            opp_rows.append({
                "순위": item.get("opportunity_rank"),
                "종목": item.get("name"),
                "기회점수": item.get("opportunity_score"),
                "분류": pc.get("label_ko") or "—",
                "Score": round((item.get("score_data") or {}).get("total") or 0, 1),
                "의견": (item.get("score_data") or {}).get("opinion") or "—",
                "등락률": f"{(item.get('price_data') or {}).get('change_rate', 0):+.2f}%",
            })
        if opp_rows:
            st.dataframe(pd.DataFrame(opp_rows), use_container_width=True, hide_index=True)
        else:
            st.info("순위 산출할 종목 없음")

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
    st.warning(f"조회 실패 종목 {len(failed)}개 — 아래를 펼쳐 원인을 확인하세요.")
    with st.expander(f"⚠️ 조회 실패 상세 ({len(failed)}개)", expanded=True):
        for r in failed:
            st.error(f"**{r['name']}** ({r['code']})\n\n{r.get('error_user') or humanize_error(r.get('error', '—'))}")
            with st.popover("원본 오류"):
                st.code(r.get("error") or "—")

# ── 판단 기록 + Phase 6 사후 검증 ─────────────────
st.markdown("---")
st.markdown("## 📰 최근 공시 (DART)")
if not DART_API_KEY:
    st.caption("DART_API_KEY가 없어 공시 조회를 건너뜁니다. config/.env 에 키를 넣으면 활성화됩니다.")
else:
    disc_map = fetch_disclosures()
    any_row = False
    disc_rows = []
    for name, code in WATCHLIST:
        for ev in disc_map.get(code) or []:
            any_row = True
            disc_rows.append({
                "종목": name,
                "일자": ev.get("ts") or "—",
                "제목": ev.get("title") or "—",
                "분류": ev.get("category") or "—",
                "중요도": ev.get("importance") or "—",
                "가치영향": ev.get("value_impact") or "—",
            })
    if not any_row:
        st.info("최근 공시 없음 또는 조회 결과 없음")
    else:
        st.dataframe(pd.DataFrame(disc_rows), use_container_width=True, hide_index=True)
        st.caption("규칙 기반 분류(Phase 4.2 초안) · 상세는 DART 원문 확인")

st.markdown("---")
st.markdown("## 📜 최근 판단 기록")
st.caption("Score·의견·트리거를 저장합니다. 의견/점수 변동·이벤트·6시간 경과 시에만 추가 기록합니다.")

hist_limit = st.slider("표시 건수", min_value=10, max_value=100, value=30, step=10)
symbol_options = ["전체"] + [f"{name} ({code})" for name, code in WATCHLIST]
hist_filter = st.selectbox("종목 필터", symbol_options, index=0)
filter_code = None
if hist_filter != "전체":
    filter_code = hist_filter.rsplit("(", 1)[-1].rstrip(")")

records = recent_decisions(limit=hist_limit, symbol=filter_code)
if not records:
    st.info("아직 저장된 판단 기록이 없습니다. 새로고침하면 현재 조회 결과가 기록됩니다.")
else:
    hist_df = pd.DataFrame(decisions_as_table_rows(records))
    st.dataframe(hist_df, use_container_width=True, hide_index=True)
    st.caption(f"총 {len(records)}건 표시 · 저장 위치: data/decisions.jsonl")

# ── Phase 6: 사후 검증 ────────────────────────────
st.markdown("---")
st.markdown("## 📈 사후 검증 (1주 / 1개월)")
st.caption(
    "기록 시점 가격 대비 이후 약 5거래일·20거래일 수익률입니다. "
    "자동매수 없음 · 검증은 사후 참고용 · 표본이 쌓여야 의미가 있습니다."
)

run_verify = st.checkbox("사후 검증 실행 (일봉 조회)", value=False, key="run_post_verify")
if not records:
    st.info("판단 기록이 없어 검증할 대상이 없습니다.")
elif not run_verify:
    st.caption("체크하면 종목별 일봉을 조회해 1주·1개월 수익을 계산합니다.")
else:
    try:
        try:
            _client = client  # 상단에서 생성된 KISClient 재사용
        except NameError:
            _client = KISClient()

        with st.spinner("일봉 조회 및 수익률 계산 중…"):
            verified, summary = load_and_verify(
                _client, limit=hist_limit, symbol=filter_code
            )

        if summary:
            st.markdown("#### 의견별 요약")
            sum_df = pd.DataFrame(summary)
            st.dataframe(sum_df, use_container_width=True, hide_index=True)
            st.caption(
                "히트율: 긍정 의견은 수익>0, 매수 회피는 수익<0일 때 히트. "
                "관망·보유/관찰은 히트율 분모에서 제외."
            )
        else:
            st.info("요약할 검증 데이터가 없습니다.")

        if verified:
            st.markdown("#### 개별 기록 + 선도 수익")
            v_df = pd.DataFrame(verified_table_rows(verified))
            st.dataframe(v_df, use_container_width=True, hide_index=True)
            n_ok = sum(1 for r in verified if r.get("verify_status") == "ok")
            n_wait = sum(1 for r in verified if r.get("verify_status") == "waiting")
            st.caption(
                f"검증됨 {n_ok}건 · 기간 대기 {n_wait}건 · "
                f"1주≈5거래일, 1개월≈20거래일"
            )
    except Exception as e:
        st.error(f"사후 검증 실패: {humanize_error(str(e))}")
        with st.popover("원본 오류"):
            st.code(str(e))

st.markdown("---")
st.caption(
    f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
    f"Templeton S {APP_PHASE} ({SCORE_VERSION}) · AI는 참모, 최종 결정은 사용자"
)