import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
import requests
from dotenv import load_dotenv
from jose import jwt
from pyvis.network import Network  # type: ignore[import-untyped]

# Load .env from project root (one level above scripts/)
load_dotenv(Path(__file__).parent.parent / ".env")

API = "http://localhost:8000"


_token_cache: dict[str, str | datetime] = {}


def _mint_token() -> tuple[str, datetime]:
    """Mint a new JWT and return (token, expiry datetime)."""
    secret = os.environ.get("JWT_SECRET", "")
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    expire_minutes = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    exp = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    token = jwt.encode({"sub": "dashboard", "exp": exp}, secret, algorithm=algorithm)
    return token, exp


def get_token() -> str:
    """Return a valid JWT, regenerating if expired or within 5 minutes of expiry."""
    exp = _token_cache.get("exp")
    if exp is None or datetime.now(UTC) >= exp - timedelta(minutes=5):  # type: ignore[operator]
        token, exp = _mint_token()
        _token_cache["token"] = token
        _token_cache["exp"] = exp
    return _token_cache["token"]  # type: ignore[return-value]

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Research Trend Tracker",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace !important;
}

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
/* Keep sidebar collapse/expand arrow visible */
[data-testid="collapsedControl"] { visibility: visible; }
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #0f0f1a;
    border: 1px solid #1e1e2e;
    border-radius: 4px;
    padding: 16px 20px;
    border-top: 2px solid #00ff88;
}
[data-testid="metric-container"]:nth-child(2) { border-top-color: #0088ff; }
[data-testid="metric-container"]:nth-child(3) { border-top-color: #aa44ff; }
[data-testid="metric-container"]:nth-child(4) { border-top-color: #ff4466; }

[data-testid="stMetricLabel"] {
    font-size: 10px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    color: #555570 !important;
}

[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 600 !important;
    color: #eeeeff !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0f0f1a !important;
    border-right: 1px solid #1e1e2e;
}

[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* Section headers */
.section-header {
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #00ff88;
    border-bottom: 1px solid #1e1e2e;
    padding-bottom: 8px;
    margin-bottom: 16px;
    margin-top: 8px;
}

/* Paper card */
.paper-card {
    background: #0f0f1a;
    border: 1px solid #1e1e2e;
    border-left: 3px solid #0088ff;
    border-radius: 0 4px 4px 0;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}

.paper-id {
    font-size: 10px;
    color: #0088ff;
    letter-spacing: 1px;
    margin-bottom: 6px;
}

.paper-title {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 13px;
    color: #eeeeff;
    line-height: 1.5;
    margin-bottom: 8px;
}

.paper-meta {
    font-size: 11px;
    color: #555570;
}

.cat-pill {
    display: inline-block;
    background: rgba(0,136,255,0.1);
    border: 1px solid rgba(0,136,255,0.2);
    color: #0088ff;
    font-size: 9px;
    padding: 2px 7px;
    border-radius: 2px;
    margin-right: 4px;
    letter-spacing: 0.5px;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid #1e1e2e !important;
}

/* Input widgets */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] select {
    background: #0f0f1a !important;
    border: 1px solid #1e1e2e !important;
    color: #00ff88 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

/* Buttons */
[data-testid="stButton"] button {
    background: transparent !important;
    border: 1px solid #00ff88 !important;
    color: #00ff88 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    border-radius: 3px !important;
}

[data-testid="stButton"] button:hover {
    background: #00ff88 !important;
    color: #0a0a0f !important;
}

/* Slider */
[data-testid="stSlider"] { color: #00ff88 !important; }

/* Divider */
hr { border-color: #1e1e2e !important; }

/* Grid background on main area */
.main .block-container {
    background-image:
        linear-gradient(rgba(0,255,136,0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,136,0.02) 1px, transparent 1px);
    background-size: 40px 40px;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
def _auth_headers() -> dict:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {get_token()}"}

@st.cache_data(ttl=60)
def fetch_health() -> bool:
    try:
        r = requests.get(f"{API}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=60)
def fetch_trends(category: str, window_days: int, top_n: int = 20):
    try:
        r = requests.get(
            f"{API}/api/v1/trends",
            params={"category": category, "window_days": window_days, "top_n": top_n},
            headers=_auth_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code}")
        return []
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_papers(category: str, days_back: int, limit: int = 15):
    try:
        r = requests.get(
            f"{API}/api/v1/papers",
            params={"category": category, "days_back": days_back, "limit": limit},
            headers=_auth_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code}")
        return []
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        return []

def plotly_dark_layout():
    return dict(
        paper_bgcolor="#0f0f1a",
        plot_bgcolor="#0a0a0f",
        font=dict(family="IBM Plex Mono", color="#c8c8d8", size=12),
    )

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-header">◈ Research Trend Tracker</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">// connection</div>', unsafe_allow_html=True)
    health = fetch_health()
    if health:
        st.success("● API online", icon=None)
    else:
        st.error("● API offline — start uvicorn first")

    st.markdown('<div class="section-header">// filters</div>', unsafe_allow_html=True)
    category = st.selectbox("Category", ["cs.AI", "cs.LG", "cs.CL", "stat.ML"])
    window_days = st.slider("Window (days)", min_value=1, max_value=30, value=7)
    top_n = st.slider("Top N keywords", min_value=5, max_value=30, value=15)

    st.markdown("---")
    refresh = st.button("⟳  refresh data")
    if refresh:
        st.cache_data.clear()

    st.markdown("---")
    st.markdown(
        '<div style="font-size:10px;color:#555570">auth: auto (JWT_SECRET from .env)</div>',
        unsafe_allow_html=True,
    )

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:24px">
  <div style="font-size:10px;color:#00ff88;letter-spacing:3px;text-transform:uppercase;margin-bottom:4px">// arxiv intelligence</div>
  <div style="font-size:26px;font-weight:600;color:#eeeeff;letter-spacing:-0.5px">Research Trend Tracker</div>
  <div style="font-size:12px;color:#555570;margin-top:4px;font-family:'IBM Plex Sans',sans-serif">Real-time arXiv ingestion · Trend analytics · LLM summarization</div>
</div>
""", unsafe_allow_html=True)

# ── Metrics ────────────────────────────────────────────────────────────────────
trends_data = fetch_trends(category, window_days, top_n)
papers_data = fetch_papers(category, window_days)

top_keyword = trends_data[0]["keyword"] if trends_data else "—"
top_count = trends_data[0]["count"] if trends_data else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("// papers fetched", len(papers_data), help=f"{category} · last {window_days}d")
with col2:
    st.metric("// keywords tracked", len(trends_data), help="unique trending terms")
with col3:
    st.metric("// top trend", top_keyword)
with col4:
    st.metric("// top count", top_count, help="occurrences in window")

st.markdown("---")

# ── Two-column layout ──────────────────────────────────────────────────────────
left, right = st.columns([1, 1.4])

# Trends chart
with left:
    st.markdown('<div class="section-header">▸ trending keywords</div>', unsafe_allow_html=True)
    if trends_data:
        keywords = [d["keyword"] for d in reversed(trends_data)]
        counts = [d["count"] for d in reversed(trends_data)]

        fig = go.Figure(go.Bar(
            x=counts,
            y=keywords,
            orientation="h",
            marker=dict(
                color=counts,
                colorscale=[[0, "#003322"], [0.5, "#00aa55"], [1, "#00ff88"]],
                showscale=False,
            ),
            text=counts,
            textposition="outside",
            textfont=dict(size=11, color="#c8c8d8"),
        ))
        fig.update_layout(
            **plotly_dark_layout(),
            height=480,
            yaxis=dict(tickfont=dict(size=11)),
            xaxis=dict(title=None),
            bargap=0.3,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("No trend data — run ingestion first")

# Papers
with right:
    st.markdown('<div class="section-header">▸ recent papers</div>', unsafe_allow_html=True)
    if papers_data:
        papers_container = st.container()
        with papers_container:
            for p in papers_data[:10]:
                authors = p.get("authors", [])
                author_str = authors[0] if authors else "—"
                if len(authors) > 1:
                    author_str += f" +{len(authors)-1}"
                date_str = ""
                if p.get("published_at"):
                    try:
                        date_str = datetime.fromisoformat(
                            p["published_at"].replace("Z","")
                        ).strftime("%b %d, %Y")
                    except Exception:
                        date_str = p["published_at"][:10]
                cats_html = "".join(
                    f'<span class="cat-pill">{c}</span>'
                    for c in p.get("categories", [])[:3]
                )
                st.markdown(f"""
                <div class="paper-card">
                  <div class="paper-id">
                    <a href="https://arxiv.org/abs/{p['arxiv_id']}" target="_blank"
                       style="color:#0088ff;text-decoration:none">[{p['arxiv_id']}] ↗</a>
                  </div>
                  <div class="paper-title">{p['title']}</div>
                  <div class="paper-meta">
                    {author_str} &nbsp;·&nbsp; {date_str}
                    &nbsp; {cats_html}
                  </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No papers yet — run ingestion first")

st.markdown("---")

# ── Category comparison ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">▸ category comparison</div>', unsafe_allow_html=True)

cats = ["cs.AI", "cs.LG", "cs.CL", "stat.ML"]
colors = ["#00ff88", "#0088ff", "#aa44ff", "#ff4466"]

def fetch_top_concepts(top_n: int = 20) -> list[dict]:
    try:
        r = requests.get(
            f"{API}/graph/top-concepts",
            params={"top_n": top_n},
            headers=_auth_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code}")
        return []
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        return []


def fetch_predictions_latest(topic_context: str = "AI/ML research", limit: int = 5) -> list[dict]:
    try:
        r = requests.get(
            f"{API}/graph/predictions/latest",
            params={"topic_context": topic_context, "limit": limit},
            headers=_auth_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code}")
        return []
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        return []


def post_generate_prediction(topic_context: str = "AI/ML research") -> dict | None:
    try:
        r = requests.post(
            f"{API}/graph/predictions/generate",
            json={"topic_context": topic_context},
            headers=_auth_headers(),
            timeout=180,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Generate failed: {e}")
        return None


_TREND_COLORS = {
    "accelerating": "#00d4aa",
    "decelerating": "#ff6b6b",
    "stable": "#4a9eff",
}


@st.cache_data(ttl=60)
def fetch_all_cats(window_days):
    counts = {}
    for cat in cats:
        try:
            r = requests.get(
                f"{API}/api/v1/papers/count",
                params={"category": cat, "days_back": window_days},
                headers=_auth_headers(),
                timeout=10,
            )
            counts[cat] = r.json().get("count", 0) if r.status_code == 200 else 0
        except Exception:
            counts[cat] = 0
    return counts

cat_counts = fetch_all_cats(window_days)

fig2 = go.Figure()
for cat, color in zip(cats, colors):
    fig2.add_trace(go.Bar(
        name=cat,
        x=[cat],
        y=[cat_counts.get(cat, 0)],
        marker_color=color,
        text=[cat_counts.get(cat, 0)],
        textposition="outside",
        textfont=dict(color="#c8c8d8"),
    ))

fig2.update_layout(
    **plotly_dark_layout(),
    height=260,
    showlegend=False,
    bargap=0.3,
    yaxis=dict(title="papers", gridcolor="#1e1e2e"),
    margin=dict(l=0, r=20, t=10, b=0),
)
st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

# ── Knowledge Graph / Prediction / Velocity tabs ───────────────────────────────
st.markdown("---")
tab_graph, tab_pred, tab_vel = st.tabs(["◈ Knowledge Graph", "◈ Prediction Report", "◈ Velocity Chart"])

# ── Tab 1: Knowledge Graph ──────────────────────────────────────────────────────
with tab_graph:
    st.markdown('<div class="section-header">▸ concept knowledge graph</div>', unsafe_allow_html=True)

    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 1])
    with col_ctrl1:
        graph_top_n = st.slider("Top N concepts", min_value=5, max_value=50, value=20, key="graph_top_n")
    with col_ctrl2:
        trend_options = ["All", "Accelerating", "Decelerating", "Stable"]
        graph_trend_filter = st.selectbox("Filter by trend", trend_options, key="graph_trend_filter")
    with col_ctrl3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        refresh_graph = st.button("⟳ Refresh graph", key="refresh_graph")

    if refresh_graph:
        st.cache_data.clear()

    concepts = fetch_top_concepts(top_n=graph_top_n)

    if graph_trend_filter != "All":
        concepts = [c for c in concepts if c.get("trend", "").lower() == graph_trend_filter.lower()]

    if concepts:
        net = Network(height="600px", width="100%", bgcolor="#1a1a2e", font_color="white", directed=True)
        net.barnes_hut()

        for c in concepts:
            trend = c.get("trend", "stable")
            color = _TREND_COLORS.get(trend, "#4a9eff")
            size = c.get("composite_score", 0.1) * 50 + 10
            net.add_node(
                c["concept_name"],
                label=c["concept_name"],
                color=color,
                size=size,
                title=(
                    f"centrality: {c.get('centrality_score', 0):.3f}<br>"
                    f"velocity: {c.get('velocity', 0):.1f}<br>"
                    f"trend: {trend}<br>"
                    f"composite: {c.get('composite_score', 0):.3f}"
                ),
            )

        # Add edges between concepts that share similar trends (simple heuristic)
        accel = [c["concept_name"] for c in concepts if c.get("trend") == "accelerating"]
        for i in range(len(accel) - 1):
            net.add_edge(accel[i], accel[i + 1], weight=1)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_f:
            tmp_path = tmp_f.name
        net.save_graph(tmp_path)
        with open(tmp_path) as html_f:
            html = html_f.read()
        os.unlink(tmp_path)
        components.html(html, height=620, scrolling=False)

        # Legend
        leg_cols = st.columns(3)
        for col, (label, color) in zip(
            leg_cols,
            [("Accelerating", "#00d4aa"), ("Decelerating", "#ff6b6b"), ("Stable", "#4a9eff")],
        ):
            col.markdown(
                f'<div style="font-size:11px;color:{color};letter-spacing:1px">● {label}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No concept data — run analyze_graph DAG task first")

# ── Tab 2: Prediction Report ────────────────────────────────────────────────────
with tab_pred:
    st.markdown('<div class="section-header">▸ prediction report viewer</div>', unsafe_allow_html=True)

    topic_context = st.selectbox(
        "Topic context",
        ["AI/ML research", "NLP research", "Computer Vision", "Reinforcement Learning"],
        key="pred_topic_context",
    )

    reports = fetch_predictions_latest(topic_context=topic_context, limit=5)

    if st.button("⟳ Generate New Report", key="gen_report"):
        with st.spinner("Generating prediction report (this may take a minute)…"):
            result = post_generate_prediction(topic_context=topic_context)
        if result:
            st.success("Report generated.")
            reports = [result] + reports

    if reports:
        latest = reports[0]
        report = latest.get("report", {})

        st.metric("Overall Confidence", report.get("overall_confidence", "—").upper())

        dir_col, gap_col, conv_col = st.columns(3)

        with dir_col:
            st.markdown('<div class="section-header">Emerging Directions</div>', unsafe_allow_html=True)
            for item in report.get("emerging_directions", []):
                with st.expander(item.get("direction", "—")):
                    st.markdown(f"**Confidence:** {item.get('confidence', '—')}")
                    st.markdown(item.get("reasoning", ""))

        with gap_col:
            st.markdown('<div class="section-header">Unexplored Gaps</div>', unsafe_allow_html=True)
            for item in report.get("underexplored_gaps", []):
                with st.expander(item.get("gap", "—")):
                    st.markdown(item.get("reasoning", ""))

        with conv_col:
            st.markdown('<div class="section-header">Predicted Convergences</div>', unsafe_allow_html=True)
            for item in report.get("predicted_convergences", []):
                label = f"{item.get('concept_a', '?')} ↔ {item.get('concept_b', '?')}"
                with st.expander(label):
                    st.markdown(item.get("reasoning", ""))

        generated_at = latest.get("generated_at", "")
        model_name = latest.get("model_name", "")
        st.caption(f"Generated at {generated_at} by {model_name}")

        if len(reports) > 1:
            st.markdown('<div class="section-header">▸ report archive</div>', unsafe_allow_html=True)
            archive_rows = [
                {
                    "generated_at": r.get("generated_at", ""),
                    "confidence": r.get("report", {}).get("overall_confidence", "—"),
                    "model": r.get("model_name", ""),
                }
                for r in reports[:5]
            ]
            st.dataframe(pd.DataFrame(archive_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No prediction reports yet — generate one above or run the generate_predictions DAG task")

# ── Tab 3: Velocity Chart ───────────────────────────────────────────────────────
with tab_vel:
    st.markdown('<div class="section-header">▸ concept velocity</div>', unsafe_allow_html=True)

    vel_top_n = st.slider("Top N concepts", min_value=5, max_value=50, value=20, key="vel_top_n")
    vel_data = fetch_top_concepts(top_n=vel_top_n)

    if vel_data:
        concept_names = [c["concept_name"] for c in vel_data]
        velocities = [c["velocity"] for c in vel_data]
        composites = [c["composite_score"] for c in vel_data]
        trend_colors = [_TREND_COLORS.get(c.get("trend", "stable"), "#4a9eff") for c in vel_data]

        fig_vel = go.Figure(
            go.Bar(
                x=concept_names,
                y=velocities,
                marker_color=trend_colors,
                text=[f"{v:.1f}" for v in velocities],
                textposition="outside",
                textfont=dict(size=10, color="#c8c8d8"),
            )
        )
        fig_vel.update_layout(
            **plotly_dark_layout(),
            title=dict(text="Velocity by Concept", font=dict(size=13, color="#c8c8d8")),
            height=350,
            xaxis=dict(tickangle=-40, tickfont=dict(size=10)),
            yaxis=dict(title="velocity", gridcolor="#1e1e2e"),
            bargap=0.25,
        )
        st.plotly_chart(fig_vel, use_container_width=True, config={"displayModeBar": False})

        fig_comp = go.Figure(
            go.Bar(
                x=composites,
                y=concept_names,
                orientation="h",
                marker_color=trend_colors,
                text=[f"{s:.3f}" for s in composites],
                textposition="outside",
                textfont=dict(size=10, color="#c8c8d8"),
            )
        )
        fig_comp.update_layout(
            **plotly_dark_layout(),
            title=dict(text="Composite Score by Concept", font=dict(size=13, color="#c8c8d8")),
            height=max(300, len(vel_data) * 22),
            xaxis=dict(title="composite score", gridcolor="#1e1e2e"),
            bargap=0.25,
        )
        st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar": False})

        st.markdown('<div class="section-header">▸ full concept table</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(vel_data), use_container_width=True, hide_index=True)
    else:
        st.info("No concept data — run analyze_graph DAG task first")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="font-size:10px;color:#555570;text-align:right;margin-top:16px;border-top:1px solid #1e1e2e;padding-top:12px">
  research-trend-tracker · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ·
  <span style="color:#00ff88">api: {'online' if health else 'offline'}</span>
</div>
""", unsafe_allow_html=True)
