import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_URL || "/templeton-api").replace(/\/$/, "");
const SCORE_KEYS = ["value", "price", "pessimism", "quality", "growth", "risk"];
const SCORE_LABELS = {
  value: "Value",
  price: "Price",
  pessimism: "Pessimism",
  quality: "Quality",
  growth: "Growth",
  risk: "Risk",
};
const WATCH_ORDER = ["005930", "005380", "105560", "069500", "472150", "360750"];

const number = (value, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

const signed = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${Number(value) >= 0 ? "+" : ""}${number(value, digits)}`;
};

const pct = (value, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${signed(value, digits)}%`;
};

const scoreTone = (score) => {
  if (score >= 85) return "strong";
  if (score >= 75) return "positive";
  if (score >= 60) return "neutral";
  if (score >= 40) return "caution";
  return "danger";
};

const opinionTone = (opinion) => {
  if (opinion === "적극적 관심") return "strong";
  if (opinion === "분할매수 관심") return "positive";
  if (opinion === "보유/관찰") return "neutral";
  if (opinion === "관망") return "caution";
  return "danger";
};

function apiUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

async function getJson(path) {
  const response = await fetch(apiUrl(path), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body.detail || body.message || "";
    } catch {
      // Keep the HTTP error concise when the server did not return JSON.
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function MiniChart({ values = [] }) {
  const clean = values.map(Number).filter(Number.isFinite);
  if (clean.length < 2) {
    return <div className="chart-empty">가격 이력 없음</div>;
  }

  const width = 320;
  const height = 90;
  const pad = 5;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const range = max - min || 1;
  const points = clean.map((v, i) => {
    const x = pad + (i / (clean.length - 1)) * (width - pad * 2);
    const y = height - pad - ((v - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <svg className="mini-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="최근 가격 추이">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function ScoreBars({ components }) {
  if (!components) return null;
  return (
    <div className="score-bars">
      {SCORE_KEYS.map((key) => {
        const value = Number(components[key]);
        return (
          <div className="score-row" key={key}>
            <div className="score-row-label">
              <span>{SCORE_LABELS[key]}</span>
              <strong>{number(value)}</strong>
            </div>
            <div className="score-track">
              <div className={`score-fill ${scoreTone(value)}`} style={{ width: `${Math.max(0, Math.min(100, value || 0))}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Metric({ label, value, sub }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}

function DetailList({ score, price }) {
  const vi = score?.value_inputs || {};
  const pi = score?.pessimism_inputs || {};
  const qi = score?.quality_inputs || {};
  const gi = score?.growth_inputs || {};
  const ri = score?.risk_inputs || {};

  return (
    <div className="detail-grid">
      <div><span>PER</span><strong>{number(vi.per, 1)}</strong></div>
      <div><span>PBR</span><strong>{number(vi.pbr, 2)}</strong></div>
      <div><span>EPS</span><strong>{number(price?.eps, 0)}</strong></div>
      <div><span>ROE</span><strong>{pct(qi.roe)}</strong></div>
      <div><span>부채비율</span><strong>{pct(qi.debt_ratio)}</strong></div>
      <div><span>매출 성장</span><strong>{pct(gi.revenue_growth)}</strong></div>
      <div><span>영업이익 성장</span><strong>{pct(gi.operating_profit_growth)}</strong></div>
      <div><span>순이익 성장</span><strong>{pct(gi.net_income_growth)}</strong></div>
      <div><span>연율 변동성</span><strong>{pct(ri.volatility_annual)}</strong></div>
      <div><span>20일 모멘텀</span><strong>{pct(ri.momentum_20d)}</strong></div>
      <div><span>시장 대비</span><strong>{pct(pi.relative_drop)}</strong></div>
      <div><span>비관 신호</span><strong>{signalLabel(pi.signal)}</strong></div>
    </div>
  );
}

function signalLabel(signal) {
  return {
    individual: "개별 악재 가능성",
    market_wide: "시장 전체 위험회피",
    none: "뚜렷한 신호 없음",
  }[signal] || "—";
}

function StockCard({ row, history, onLoadHistory }) {
  const score = row.score;
  const price = row;
  const total = score?.total;
  const tone = opinionTone(score?.opinion);

  return (
    <article className="stock-card">
      <div className="stock-head">
        <div>
          <h3>{row.name}</h3>
          <span className="muted">{row.symbol}</span>
        </div>
        <span className={`pill ${tone}`}>{score?.opinion || "—"}</span>
      </div>

      <div className="stock-primary">
        <div>
          <span className="eyebrow">현재가</span>
          <strong className="stock-price">{number(price.current_price, 0)}원</strong>
          <span className={`change ${Number(price.change_rate) >= 0 ? "up" : "down"}`}>
            {signed(price.change_rate)}%
          </span>
        </div>
        <div className="score-box">
          <span>Templeton Score</span>
          <strong>{number(total)}</strong>
        </div>
      </div>

      <div className="stock-context">
        <span>52주 고점 대비 {pct(price.drop_from_52w_high)}</span>
        <span>비관: {signalLabel(score?.pessimism_inputs?.signal)}</span>
      </div>

      <ScoreBars components={score?.components} />

      <div className="chart-wrap">
        <div className="section-label">최근 가격</div>
        <MiniChart values={history?.closes || []} />
        {!history && (
          <button className="text-button" onClick={() => onLoadHistory(row.symbol)}>
            가격 이력 불러오기
          </button>
        )}
      </div>

      <details className="details">
        <summary>근거 데이터 상세</summary>
        <DetailList score={score} price={price} />
      </details>

      {row.error && <div className="inline-error">{row.error}</div>}
    </article>
  );
}

function App() {
  const [rows, setRows] = useState([]);
  const [market, setMarket] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [history, setHistory] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showScores, setShowScores] = useState(true);
  const [selectedSymbol, setSelectedSymbol] = useState("전체");

  const loadScores = useCallback(async (force = false) => {
    setRefreshing(true);
    try {
      const data = await getJson(`/scores${force ? "?force=true" : ""}`);
      const ordered = [...data].sort((a, b) => {
        const ai = WATCH_ORDER.indexOf(a.symbol);
        const bi = WATCH_ORDER.indexOf(b.symbol);
        return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
      });
      setRows(ordered);
      setLastUpdated(new Date());
      setError("");
    } catch (err) {
      setError(err.message || "데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadMarket = useCallback(async () => {
    try {
      const data = await getJson("/market-overview");
      setMarket(data);
    } catch {
      // Market overview is supplementary; the main score screen remains usable.
    }
  }, []);

  const loadDecisions = useCallback(async () => {
    try {
      const data = await getJson("/decisions?limit=30");
      setDecisions(data.items || []);
    } catch {
      setDecisions([]);
    }
  }, []);

  const loadHistory = useCallback(async (symbol) => {
    if (history[symbol]) return;
    try {
      const data = await getJson(`/prices/${symbol}/history?count=60`);
      setHistory((current) => ({ ...current, [symbol]: data }));
    } catch {
      setHistory((current) => ({ ...current, [symbol]: { closes: [] } }));
    }
  }, [history]);

  const refreshAll = useCallback(async (force = true) => {
    await Promise.all([loadScores(force), loadMarket(), loadDecisions()]);
  }, [loadScores, loadMarket, loadDecisions]);

  useEffect(() => {
    refreshAll(false);
  }, [refreshAll]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(() => refreshAll(false), 30000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, refreshAll]);

  const visibleRows = useMemo(
    () => selectedSymbol === "전체" ? rows : rows.filter((r) => r.symbol === selectedSymbol),
    [rows, selectedSymbol]
  );

  const validRows = rows.filter((r) => r.score && Number.isFinite(Number(r.score.total)));
  const avgScore = validRows.length
    ? validRows.reduce((sum, r) => sum + Number(r.score.total), 0) / validRows.length
    : null;
  const upCount = rows.filter((r) => Number(r.change_rate) > 0).length;
  const downCount = rows.filter((r) => Number(r.change_rate) < 0).length;
  const benchmark = rows.find((r) => r.symbol === "069500");
  const marketChange = benchmark?.change_rate;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand-line">
            <span className="brand-mark">T</span>
            <div>
              <h1>Templeton S</h1>
              <p>가치 · 가격 · 비관 · 품질 · 성장 · 위험</p>
            </div>
          </div>
        </div>
        <div className="top-actions">
          <span className={`connection ${error ? "offline" : "online"}`}>
            <i /> {error ? "연결 확인 필요" : "실데이터 연결"}
          </span>
          <button className="refresh-button" onClick={() => refreshAll(true)} disabled={refreshing}>
            {refreshing ? "새로고침 중…" : "↻ 새로고침"}
          </button>
        </div>
      </header>

      <main className="content">
        {error && (
          <div className="alert error">
            <strong>데이터 조회 실패</strong>
            <span>{error}</span>
          </div>
        )}

        <section className="hero">
          <div>
            <span className="eyebrow">현재 시장 스냅샷</span>
            <h2>오늘의 Templeton S</h2>
            <p>앱을 열면 현재 데이터를 조회합니다. 조회 자체가 역사적 기록을 생성하지는 않습니다.</p>
          </div>
          <div className="hero-meta">
            <span>기준: KODEX 200 (069500)</span>
            <strong>{marketChange === undefined ? "—" : signed(marketChange) + "%"}</strong>
          </div>
        </section>

        <section className="metrics-grid">
          <Metric label="조회 종목" value={`${validRows.length} / ${rows.length || 6}`} sub="실데이터 응답 기준" />
          <Metric label="평균 Score" value={avgScore == null ? "—" : number(avgScore)} sub="현재 조회값" />
          <Metric label="상승 종목" value={`${upCount}개`} sub="당일 등락률 기준" />
          <Metric label="하락 종목" value={`${downCount}개`} sub="당일 등락률 기준" />
        </section>

        <section className="market-banner">
          <div>
            <span className="eyebrow">시장 컨텍스트</span>
            <h3>{marketChange == null ? "시장 데이터 확인 중" : marketChange <= -1 ? "시장 전체 위험회피 신호" : "현재 시장 모드"}</h3>
            <p>
              KODEX 200 {marketChange == null ? "—" : signed(marketChange) + "%"} ·
              {" "}{upCount}개 상승 / {downCount}개 하락
            </p>
          </div>
          <div className="market-note">
            {market?.items?.length ? `${market.items.length}개 시장 지표 연결됨` : "시장 세부지표는 API 응답을 확인합니다."}
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">WATCHLIST</span>
              <h2>관심 종목 현황</h2>
            </div>
            <div className="controls">
              <select value={selectedSymbol} onChange={(e) => setSelectedSymbol(e.target.value)}>
                <option value="전체">전체 종목</option>
                {rows.map((row) => <option value={row.symbol} key={row.symbol}>{row.name}</option>)}
              </select>
              <label className="switch">
                <input type="checkbox" checked={showScores} onChange={(e) => setShowScores(e.target.checked)} />
                <span /> Score 상세
              </label>
              <label className="switch">
                <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
                <span /> 30초 자동 새로고침
              </label>
            </div>
          </div>

          {loading ? (
            <div className="loading-grid">{[1,2,3,4,5,6].map((x) => <div className="skeleton" key={x} />)}</div>
          ) : (
            <div className="stock-grid">
              {visibleRows.map((row) => (
                <StockCard
                  key={row.symbol}
                  row={row}
                  history={history[row.symbol]}
                  onLoadHistory={loadHistory}
                />
              ))}
            </div>
          )}
        </section>

        <section className="section two-col">
          <div className="panel">
            <div className="section-heading compact">
              <div>
                <span className="eyebrow">RECENT DECISIONS</span>
                <h2>최근 판단 기록</h2>
              </div>
            </div>
            {decisions.length === 0 ? (
              <p className="muted">저장된 판단 기록이 없거나 API에서 조회되지 않았습니다.</p>
            ) : (
              <div className="decision-list">
                {decisions.slice(0, 10).map((item, index) => (
                  <div className="decision-row" key={item.id || item.ts || index}>
                    <div>
                      <strong>{item.name || item.symbol || "종목"}</strong>
                      <span>{item.symbol || "—"}</span>
                    </div>
                    <div>
                      <strong>{item.score ?? item.total ?? "—"}</strong>
                      <span>{item.opinion || "—"}</span>
                    </div>
                    <time>{item.ts || item.timestamp || "—"}</time>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel">
            <div className="section-heading compact">
              <div>
                <span className="eyebrow">DATA STATUS</span>
                <h2>데이터 상태</h2>
              </div>
            </div>
            <div className="status-list">
              <div><span>API</span><strong className="status-ok">FastAPI 연결</strong></div>
              <div><span>시장 데이터</span><strong>{market ? "수신 완료" : "조회 중"}</strong></div>
              <div><span>KIS / Score</span><strong>{validRows.length ? "실데이터 수신" : "대기"}</strong></div>
              <div><span>마지막 조회</span><strong>{lastUpdated ? lastUpdated.toLocaleTimeString("ko-KR") : "—"}</strong></div>
              <div><span>자동 기록</span><strong>09:30 / 17:00 KST</strong></div>
            </div>
            <p className="small-note">
              자동 수집은 앱 실행과 별도로 역사적 Snapshot을 축적하는 경로입니다.
              현재 화면의 조회는 그 자체로 기록을 만들지 않습니다.
            </p>
          </div>
        </section>

        <footer>
          <span>Templeton S · Score v0.5</span>
          <span>AI는 참모, 최종 결정은 사용자</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
