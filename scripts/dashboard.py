import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests
from datetime import datetime

API = "http://localhost:8000"

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
def get_headers(token: str) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

@st.cache_data(ttl=60)
def fetch_health() -> bool:
    try:
        r = requests.get(f"{API}/health", timeout=3)
        return r.status_code == 200
    except:
        return False

@st.cache_data(ttl=60)
def fetch_trends(token: str, category: str, window_days: int, top_n: int = 20):
    try:
        r = requests.get(
            f"{API}/api/v1/trends",
            params={"category": category, "window_days": window_days, "top_n": top_n},
            headers=get_headers(token),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code} — check your JWT token")
        return []
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_papers(token: str, category: str, days_back: int, limit: int = 15):
    try:
        r = requests.get(
            f"{API}/api/v1/papers",
            params={"category": category, "days_back": days_back, "limit": limit},
            headers=get_headers(token),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        st.error(f"API error {e.response.status_code} — check your JWT token")
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
    st.markdown('<div class="section-header">◈ research_trend_tracker</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">// connection</div>', unsafe_allow_html=True)
    token = st.text_input("JWT Token", type="password", placeholder="Bearer token...")

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
    st.markdown("""
    <div style="font-size:10px;color:#555570;line-height:1.8">
    Generate token:<br>
    <span style="color:#00ff88">uv run python -c "<br>
    from app.core.security<br>
    import create_access_token;<br>
    print(create_access_token(<br>
    {'sub':'demo'}))\"</span>
    </div>
    """, unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:24px">
  <div style="font-size:10px;color:#00ff88;letter-spacing:3px;text-transform:uppercase;margin-bottom:4px">// arxiv intelligence</div>
  <div style="font-size:26px;font-weight:600;color:#eeeeff;letter-spacing:-0.5px">research<span style="color:#00ff88">_</span>trend<span style="color:#00ff88">_</span>tracker</div>
  <div style="font-size:12px;color:#555570;margin-top:4px;font-family:'IBM Plex Sans',sans-serif">Real-time arXiv ingestion · Trend analytics · LLM summarization</div>
</div>
""", unsafe_allow_html=True)

# ── Metrics ────────────────────────────────────────────────────────────────────
trends_data = fetch_trends(token, category, window_days, top_n)
papers_data = fetch_papers(token, category, window_days)

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
        st.info("No trend data — run ingestion first or check JWT token")

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
                    except:
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
        st.info("No papers yet — run ingestion first or check JWT token")

st.markdown("---")

# ── Category comparison ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">▸ category comparison</div>', unsafe_allow_html=True)

cats = ["cs.AI", "cs.LG", "cs.CL", "stat.ML"]
colors = ["#00ff88", "#0088ff", "#aa44ff", "#ff4466"]

@st.cache_data(ttl=60)
def fetch_all_cats(token, window_days):
    counts = {}
    for cat in cats:
        try:
            r = requests.get(
                f"{API}/api/v1/papers",
                params={"category": cat, "days_back": window_days, "limit": 100},
                headers=get_headers(token),
                timeout=10,
            )
            counts[cat] = len(r.json()) if r.status_code == 200 else 0
        except Exception:
            counts[cat] = 0
    return counts

cat_counts = fetch_all_cats(token, window_days)

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

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="font-size:10px;color:#555570;text-align:right;margin-top:16px;border-top:1px solid #1e1e2e;padding-top:12px">
  research-trend-tracker · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ·
  <span style="color:#00ff88">api: {'online' if health else 'offline'}</span>
</div>
""", unsafe_allow_html=True)
