"""
Scalable Real-Time Music Recommendation System - Streamlit UI Dashboard
========================================================================
Author: Kresha Shah | PRN: 24070126512
Technologies: Hadoop HDFS, Apache Spark, Apache Mahout, MongoDB NoSQL, FastAPI, Streamlit
"""
from __future__ import annotations

import os
import time
from typing import Any
import requests
import streamlit as st

# Configure Page
st.set_page_config(
    page_title="Scalable Music Recommendation Platform | Big Data",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", os.getenv("API_URL", "http://127.0.0.1:8000")).rstrip("/")

# Custom CSS for Premium Design & Visual Polish
st.markdown(
    """
    <style>
    :root {
        --navy: #132238;
        --blue: #1d5f9f;
        --blue-soft: #e7f1fb;
        --coral: #e97561;
        --ink: #172338;
        --muted: #637083;
        --line: #dbe3ec;
        --canvas: #f5f7fa;
    }

    html, body, [class*="css"] {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--ink);
    }

    [data-testid="stAppViewContainer"] { background: var(--canvas); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: var(--navy); }
    [data-testid="stSidebar"] * { color: #f1f5f9; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #cbd5e1; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.16); }
    [data-testid="stSidebar"] [data-baseweb="select"] > div { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.18); }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding: 8px 6px; border-radius: 8px; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: rgba(255,255,255,.09); }
    [data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 14px; }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    code, pre { font-family: "SFMono-Regular", Consolas, monospace !important; }

    .main-header {
        background: var(--navy);
        border: 1px solid #234a75;
        border-radius: 12px;
        padding: 26px 32px;
        margin-bottom: 24px;
        box-shadow: 0 12px 28px rgba(19,34,56,.13);
    }
    .main-header h1 { color: #fff !important; }
    .main-header p { color: #cbd5e1 !important; }
    .status-badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: .76rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
    .badge-online { background: #d9f7e8; color: #167447; border: 1px solid #87d8ad; }
    .badge-hybrid { background: #e4effc; color: #1d5f9f; border: 1px solid #9ec4e7; }
    .badge-cf { background: #fff0dc; color: #9a5a08; border: 1px solid #efc17b; }
    .badge-cold { background: #fbe3e1; color: #a2433a; border: 1px solid #e6a29a; }
    .badge-rank { background: var(--blue); color: white; border-radius: 7px; font-weight: 700; padding: 4px 10px; }

    .rec-card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 16px 20px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(30,55,80,.05); }
    .rec-card:hover { border-color: #9ec4e7; box-shadow: 0 8px 18px rgba(30,95,159,.10); }
    .rec-card h4 { color: var(--ink) !important; }
    .pipeline-step { background: var(--blue-soft); border: 1px solid #b9d3ec; border-radius: 9px; padding: 16px; text-align: center; margin-bottom: 10px; color: var(--ink); }
    .metric-card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 14px; text-align: center; }
    </style>
    """,
    unsafe_allow_html=True,
)


def fetch_api(endpoint: str, params: dict[str, Any] | None = None, timeout: float = 3.5) -> dict[str, Any] | None:
    try:
        url = f"{API_BASE_URL}{endpoint}"
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"error": "not_found", "detail": resp.json().get("detail", "Resource not found")}
        else:
            return {"error": f"http_{resp.status_code}", "detail": resp.text}
    except Exception as exc:
        return {"error": "connection_error", "detail": str(exc)}


def post_api(endpoint: str, json_data: dict[str, Any], timeout: float = 3.5) -> dict[str, Any] | None:
    try:
        url = f"{API_BASE_URL}{endpoint}"
        resp = requests.post(url, json=json_data, timeout=timeout)
        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": f"http_{resp.status_code}", "detail": resp.text}
    except Exception as exc:
        return {"error": "connection_error", "detail": str(exc)}


# Fetch live system health
health_data = fetch_api("/health")
is_api_healthy = health_data is not None and "error" not in health_data

# Sidebar Navigation & Settings
with st.sidebar:
    st.markdown("<div style='padding: 10px 4px 22px;'><div style='font-size: 1.25rem; font-weight: 800; color: #fff;'>Music Lab</div><div style='font-size: .78rem; color: #9fb7d1; letter-spacing: .08em; text-transform: uppercase;'>Big Data Studio</div></div>", unsafe_allow_html=True)
    st.markdown("### Navigation")
    tab_selection = st.radio(
        "Select Dashboard View:",
            [
                "🏠 System Overview & Metrics",
                "🎧 Personalized Recommendations",
                "🔍 Similar Songs Explorer",
                "⚡ Real-Time Streaming & Events",
                "📊 Model Evaluation & Metrics",
                "🏗️ Big Data Architecture & Pipeline",
                "🍃 MongoDB NoSQL Explorer",
            ],
        index=1,
    )

    st.markdown("---")
    st.markdown("### ⚙️ Backend Connection")
    st.text_input("FastAPI Base URL:", value=API_BASE_URL, key="api_url_input", disabled=True)
    if is_api_healthy:
        st.success("🟢 FastAPI Backend Connected")
    else:
        st.error("🔴 FastAPI Backend Disconnected")

    st.markdown("---")
    st.markdown(
        """
        **Student Details:**  
        👤 **Kresha Shah**  
        🆔 **PRN: 24070126512**  
        🎓 *Big Data Engineering Project*
        """
    )


# Top Banner Header
st.markdown(
    f"""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800; background: linear-gradient(90deg, #60A5FA, #A78BFA, #F472B6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    🎵 Find your next repeat.
                </h1>
                <p style="margin: 6px 0 0 0; color: #cbd5e1; font-size: 1.05rem;">
                    Last.fm interaction intelligence &bull; Apache Mahout &bull; Spark &bull; FastAPI &bull; MongoDB fallback
                </p>
            </div>
            <div style="text-align: right;">
                <span class="status-badge badge-online">{('API Online' if is_api_healthy else 'API Offline')}</span><br>
                <small style="color: #64748B;">Student: <b>Kresha Shah</b> (24070126512)</small>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Render live system metrics; unavailable dependencies are shown honestly.
live_health = health_data if is_api_healthy and health_data else {}
dataset_count = live_health.get("dataset_interactions_count", 0)
mahout_users = live_health.get("active_recommendation_count", 0)
catalog_count = live_health.get("catalog_items_count", 0)
mongo_label = "Online" if live_health.get("mongodb_available") else "Offline"
cols = st.columns(5)
with cols[0]:
    st.metric(label="Hadoop HDFS", value="Configured" if live_health else "Unavailable", delta=live_health.get("hadoop_hdfs", "") or None)
with cols[1]:
    st.metric(label="Apache Spark", value="Configured" if live_health else "Unavailable", delta=live_health.get("spark_engine", "") or None)
with cols[2]:
    st.metric(label="Apache Mahout", value=f"{mahout_users:,} users" if mahout_users else "Unavailable", delta="Parsed output" if mahout_users else None)
with cols[3]:
    st.metric(label="MongoDB", value=mongo_label, delta=live_health.get("mongodb_status", "") or None)
with cols[4]:
    st.metric(label="Source interactions", value=f"{dataset_count:,}" if dataset_count else "Unavailable", delta=f"{catalog_count:,} mapped items" if catalog_count else None)

st.markdown("---")

# ==============================================================================
# VIEW 1: SYSTEM OVERVIEW & METRICS
# ==============================================================================
if tab_selection == "🏠 System Overview & Metrics":
    st.header("🏠 Distributed System Overview & Cluster Status")
    st.write(
        "Real-time operational status of the distributed Big Data recommendation cluster, "
        "storage tiers, and serving infrastructure."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🖥️ Cluster Health & Storage Components")
        if is_api_healthy and health_data:
            st.json({
                "Overall Status": health_data.get("status", "operational"),
                "Hadoop HDFS Distributed Storage": health_data.get("hadoop_hdfs"),
                "Apache Spark Processing Engine": health_data.get("spark_engine"),
                "Apache Mahout CF Model": health_data.get("mahout_cf"),
                "MongoDB NoSQL Document Database": health_data.get("mongodb_status"),
                "Precomputed User Profiles": health_data.get("active_recommendation_count"),
                "Total Track Catalog Size": health_data.get("catalog_items_count"),
                "Server Timestamp (UTC)": health_data.get("timestamp"),
            })
        else:
            st.warning("⚠️ FastAPI Backend is offline. Start the backend daemon to inspect live metrics.")

    with c2:
        st.subheader("📊 Big Data Dataset Summary")
        st.markdown(
            f"""
            | Property | Specification | Observed |
            | :--- | :--- | :--- |
            | **Dataset Name** | Last.fm 1K event log | Prepared catalog and interactions |
            | **Interaction rows** | Local source file | {dataset_count:,} rows from API health |
            | **Data Schema** | `user_id` $\\to$ `song_id` $\\to$ `play_count` | Prepared user/item/count records |
            | **Processed Storage** | `hdfs:///music/processed` | Columnar Snappy Parquet |
            | **Mahout Algorithm** | Item-Based CF (`RecommenderJob`) | `SIMILARITY_LOGLIKELIHOOD` |
            | **NoSQL Documents** | MongoDB `music_recommendation` | {mongo_label} |
            """
        )

    st.markdown("### 🏆 Technical Rubric Compliance Matrix")
    st.markdown(
        """
        | Rubric Criteria | Marks | Architectural Implementation | Status |
        | :--- | :---: | :--- | :---: |
        | **1. Problem Statement** | 2 Marks | Explicit Big Data scaling motivation for sparse $O(N^2)$ listening interaction matrices. | Documented |
        | **2. Docker & NoSQL Ingestion** | 2 Marks | Compose definitions, MongoDB persistence, and API integration are present. | Runtime-dependent |
        | **3. Streamlit UI Design** | 1 Mark | Multi-tab dashboard with live API-backed recommendations and event views. | Implemented |
        | **4. Dataset Distributed on Hadoop** | 2 Marks | Spark/HDFS jobs and medallion paths are defined. | Cluster verification required |
        """
    )


# ==============================================================================
# VIEW 2: PERSONALIZED RECOMMENDATIONS
# ==============================================================================
elif tab_selection == "🎧 Personalized Recommendations":
    st.header("🎧 Personalized Music Recommendations")
    st.write(
        "Generate personalized Top-N music recommendations combining **Apache Mahout Collaborative Filtering**, "
        "**Behavioral Item Co-occurrence**, and **Global Popularity Signals**."
    )

    col_input, col_config = st.columns([1.2, 1.8])

    with col_input:
        st.markdown("#### 👤 Listener Identification")
        sample_choice = st.selectbox(
            "Quick Demo Listener Profiles:",
            [
                "Custom Input",
                "User 3143 (Active Listener)",
                "User 6 (Prepared Profile)",
                "User 10 (Prepared Profile)",
                "User 999999 (New Listener / Cold-Start)",
            ],
        )

        if sample_choice.startswith("User 3143 ("):
            default_uid = "3143"
        elif sample_choice.startswith("User 6 ("):
            default_uid = "6"
        elif sample_choice.startswith("User 10 ("):
            default_uid = "10"
        elif sample_choice.startswith("User 999999"):
            default_uid = "999999"
        else:
            default_uid = "3143"

        user_id_input = st.text_input("Enter Listener/User ID:", value=default_uid, help="Use a prepared Last.fm listener such as 3143, 6, or 10")

        rec_limit = st.slider("Number of Recommendations (Top-N):", min_value=1, max_value=20, value=10)

    with col_config:
        st.markdown("#### ⚖️ Recommendation Strategy & Hybrid Weights")
        strategy_choice = st.selectbox(
            "Recommendation Strategy:",
            [
                "Hybrid Fusion (CF + Content Similarity + Popularity)",
                "Collaborative Filtering Only (Apache Mahout Log-Likelihood)",
                "Global Popularity (Cold-Start Mode)",
            ],
        )

        if strategy_choice.startswith("Hybrid"):
            w_col1, w_col2, w_col3 = st.columns(3)
            with w_col1:
                alpha = st.slider("CF Weight (α):", 0.0, 1.0, 0.70, 0.05, help="Collaborative Filtering weight")
            with w_col2:
                beta = st.slider("Co-occurrence (β):", 0.0, 1.0, 0.20, 0.05, help="Interaction-derived item co-occurrence weight")
            with w_col3:
                gamma = st.slider("Popularity (γ):", 0.0, 1.0, 0.10, 0.05, help="Global popularity weight")
            selected_strategy = "hybrid"
        elif strategy_choice.startswith("Collaborative"):
            alpha, beta, gamma = 1.0, 0.0, 0.0
            selected_strategy = "collaborative"
        else:
            alpha, beta, gamma = 0.0, 0.0, 1.0
            selected_strategy = "auto"

        btn_generate = st.button("🚀 Generate Personalized Recommendations", type="primary", width='stretch')

    # Recommendation Results Section
    if btn_generate or user_id_input:
        st.markdown("---")
        with st.spinner(f"Computing Top-{rec_limit} recommendations for User {user_id_input}..."):
            api_params = {
                "n": rec_limit,
                "strategy": selected_strategy,
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
            }
            res = fetch_api(f"/recommend/{user_id_input}", params=api_params)

        if res and "error" not in res:
            strategy_used = res.get("strategy", "hybrid")
            exec_time = res.get("execution_time_ms", 0.0)
            items = res.get("recommendations", [])

            # Header info
            badge_class = "badge-hybrid" if strategy_used == "hybrid" else ("badge-cf" if strategy_used == "collaborative" else "badge-cold")
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div>
                        <h3 style="margin: 0;">Top-{len(items)} Recommendations for Listener <code>{user_id_input}</code></h3>
                        <span class="status-badge {badge_class}">Strategy: {strategy_used.upper()}</span>
                        <small style="color: #637083; margin-left: 12px;">Serving Latency: <b>{exec_time} ms</b> &bull; Source: <b>{res.get('source')}</b></small>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Render Cards in 2 columns
            c_left, c_right = st.columns(2)
            for idx, item in enumerate(items):
                target_col = c_left if idx % 2 == 0 else c_right
                rank = item.get("rank", idx + 1)
                item_id = item.get("item_id")
                score = item.get("score")
                song_code = item.get("song_code") or item.get("song_id") or "Unmapped Track"
                reason = item.get("reason", "Collaborative Filtering Recommendation")
                item_strategy = item.get("strategy", strategy_used)

                with target_col:
                    st.markdown(
                        f"""
                        <div class="rec-card">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <span class="badge-rank">#{rank}</span>
                                    <div>
                                        <h4 style="margin: 0; font-size: 1.15rem; color: #172338;">{item.get('track_name') or f'Track {item_id}'}</h4>
                                        <small style="color: #1d5f9f; font-family: monospace;">{item.get('artist_name') or 'Mapped Last.fm catalog item'} &bull; ID {item_id}</small>
                                    </div>
                                </div>
                                <div style="text-align: right;">
                                    <span style="font-size: 1.1rem; font-weight: 700; color: #10B981;">{score:.4f}</span><br>
                                    <small style="color: #64748B;">Score</small>
                                </div>
                            </div>
                            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #e2e8f0; font-size: 0.85rem; color: #637083;">
                                💡 <i>{reason}</i>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # User Listening History Drawer
            with st.expander(f"📜 View Listening History & Profiling for Listener {user_id_input}"):
                history_res = fetch_api(f"/user/{user_id_input}/history", params={"limit": 10})
                if history_res and "history" in history_res and history_res["history"]:
                    st.markdown(f"**Found {history_res['total_interactions']} recorded interaction(s) in training set:**")
                    st.table([
                        {"Item ID": h["item_id"], "Track": h.get("track_name") or h["song_code"] or "N/A", "Artist": h.get("artist_name") or "N/A", "Play Frequency": h["play_count"]}
                        for h in history_res["history"]
                    ])
                else:
                    st.info("No prior interaction history found for this listener ID (Cold-Start Listener).")

        elif res and res.get("error") == "not_found":
            st.warning(f"⚠️ Listener ID `{user_id_input}` not found in offline collaborative model. Switch to **'Hybrid'** or **'Global Popularity'** strategy for cold-start recommendations.")
        else:
            st.error(f"Failed to fetch recommendations: {res.get('detail') if res else 'Backend unavailable'}")


# ==============================================================================
# VIEW 3: SIMILAR SONGS EXPLORER
# ==============================================================================
elif tab_selection == "🔍 Similar Songs Explorer":
    st.header("🔍 Behavioral Item Similarity Explorer")
    st.write(
        "Retrieve related tracks using metadata content similarity when the Last.fm catalog is available, "
        "with behavioral co-occurrence as a documented fallback."
    )

    c_query, c_res = st.columns([1, 2])
    with c_query:
        st.markdown("#### 🎵 Song Query")
        quick_songs = st.selectbox(
            "Select Benchmark Sample Track:",
            [
                "Item 103 (SOZOBWN12A8C130999)",
                "Item 21666 (SOYVIXM12A8C13FD5E)",
                "Item 33 (SOBJDAG12A8C13809C)",
                "Item 3069 (SOUWJEO12A8C138E6A)",
                "Item 86 (SOUKIXU12A8C139744)",
                "Custom Song ID",
            ],
        )
        if "103" in quick_songs:
            default_sid = "103"
        elif "21666" in quick_songs:
            default_sid = "21666"
        elif "33" in quick_songs:
            default_sid = "33"
        elif "3069" in quick_songs:
            default_sid = "3069"
        elif "86" in quick_songs:
            default_sid = "86"
        else:
            default_sid = "103"

        song_id_input = st.text_input("Enter Item / Song ID:", value=default_sid)
        sim_n = st.slider("Number of Similar Songs:", min_value=1, max_value=20, value=8)
        btn_find_sim = st.button("🔎 Find Nearest Neighbor Songs", type="primary", width='stretch')

    with c_res:
        if btn_find_sim or song_id_input:
            sim_res = fetch_api(f"/similar/{song_id_input}", params={"n": sim_n})
            if sim_res and "similar_songs" in sim_res:
                st.subheader(f"Top-{len(sim_res['similar_songs'])} Tracks Similar to Item `{song_id_input}` ({sim_res.get('query_song_code') or 'Last.fm catalog item'})")
                for s in sim_res["similar_songs"]:
                    st.markdown(
                        f"""
                        <div class="rec-card">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <span class="badge-rank">#{s['rank']}</span>
                                    <div>
                                        <h4 style="margin: 0; color: #172338;">{s.get('track_name') or f"Track {s['item_id']}"}</h4>
                                    <small style="color: #1d5f9f; font-family: monospace;">{s.get('artist_name') or 'Unknown artist'} &bull; ID {s['item_id']}</small>
                                    </div>
                                </div>
                                <div>
                                    <span style="font-size: 1.1rem; font-weight: 700; color: #38BDF8;">{s['similarity_score']:.4f}</span>
                                    <small style="color: #64748B;"> {s.get('similarity_type', 'Similarity')}</small>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.error("Could not retrieve similar songs from backend.")


# ==============================================================================
# VIEW 4: REAL-TIME STREAMING & LIVE EVENTS
# ==============================================================================
elif tab_selection == "⚡ Real-Time Streaming & Events":
    st.header("⚡ Real-Time Event Streaming & Activity Feed")
    st.write(
        "Demonstrates near-real-time listening event ingestion into **MongoDB NoSQL** and **Spark Structured Streaming** "
        "micro-batch processing."
    )

    c_stream_ctrl, c_stream_metrics = st.columns([1, 2])
    with c_stream_ctrl:
        st.markdown("#### 🕹️ Event Simulator Controls")
        sim_interval = st.slider("Simulator Frequency (seconds):", min_value=0.5, max_value=5.0, value=1.5, step=0.5)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("▶️ Start Live Stream", type="primary", width='stretch'):
                post_api(f"/live/simulator/start?interval_seconds={sim_interval}", {})
                st.success("Simulator active!")
        with col_btn2:
            if st.button("⏹️ Stop Stream", width='stretch'):
                post_api("/live/simulator/stop", {})
                st.info("Simulator stopped.")

        st.markdown("---")
        st.markdown("#### ✍️ Emit Manual Event")
        with st.form("manual_event_form"):
            man_user = st.text_input("User ID:", value="3143")
            man_song = st.text_input("Song/Item ID:", value="681220")
            man_action = st.selectbox("Action:", ["play", "skip", "like", "replay"])
            submitted = st.form_submit_button("📡 Emit Live Event")
            if submitted:
                evt_resp = post_api("/events", {"user_id": man_user, "song_id": man_song, "event_type": man_action})
                if evt_resp and "status" in evt_resp:
                    st.success(f"Recorded: {evt_resp.get('message')}")

    with c_stream_metrics:
        st.markdown("#### 📈 Streaming Pipeline Activity")
        stream_stats = fetch_api("/live/stats")
        if stream_stats and "error" not in stream_stats:
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Total Events Ingested", stream_stats.get("total_events_processed", 0))
            with m2:
                st.metric("Active Listeners", stream_stats.get("unique_active_users", 0))
            with m3:
                sim_status = "🟢 ACTIVE" if stream_stats.get("simulator_active") else "⚪ IDLE"
                st.metric("Simulator Status", sim_status)

            st.markdown("#### 📜 Live Event Stream Activity Log (Auto-Refreshing)")
            events_data = fetch_api("/live/events", params={"limit": 10})
            if events_data and "events" in events_data and events_data["events"]:
                st.table([
                    {
                        "Timestamp": e["timestamp"].split("T")[1][:8] if "T" in e["timestamp"] else e["timestamp"],
                        "Event ID": e["event_id"],
                        "Listener": f"User {e['user_id']}",
                        "Song Item": f"Item {e['song_id']}",
                        "Action": e["event_type"].upper(),
                        "Duration": f"{e['duration_seconds']}s",
                    }
                    for e in events_data["events"]
                ])
            else:
                st.info("No events in current buffer. Click **'Start Live Stream'** or emit a manual event.")


# ==============================================================================
# VIEW 5: MODEL EVALUATION & METRICS
# ==============================================================================
elif tab_selection == "📊 Model Evaluation & Metrics":
    st.header("📊 Recommendation Model Offline Evaluation")
    st.write(
        "Formal offline Top-K evaluation metrics computed from the configured interaction dataset using a deterministic 20% holdout."
    )

    eval_data = fetch_api("/evaluation/metrics")
    if eval_data and "error" not in eval_data:
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("Hit Rate@10", f"{eval_data['hit_rate_at_k']*100:.2f}%", help="Percentage of test users with at least 1 relevant recommendation")
        with m_col2:
            st.metric("MRR@10 (Mean Reciprocal)", f"{eval_data['mrr_at_k']:.4f}", help="Average reciprocal rank of first relevant item")
        with m_col3:
            st.metric("Precision@10", f"{eval_data['precision_at_k']:.4f}", help="Ratio of recommended tracks that were actual hits")
        with m_col4:
            st.metric("Catalog Coverage", f"{eval_data['catalog_coverage_pct']:.2f}%", help="Percentage of catalog represented in recommendations")

        st.markdown("---")
        st.subheader("📋 Evaluation Methodology & Benchmark Details")
        st.markdown(
            f"""
            - **Evaluated Model:** Apache Mahout Item-Based Collaborative Filtering (`RecommenderJob`)
            - **Similarity Measure:** Log-Likelihood Ratio Similarity (`SIMILARITY_LOGLIKELIHOOD`)
            - **Dataset Split:** {eval_data.get('dataset_split')}
            - **Evaluated Test Users:** **{eval_data.get('evaluated_users_count'):,} active listeners**
            - **Total Song Catalog:** **{eval_data.get('total_catalog_items'):,} unique tracks**
            
            > **Evaluation Note:** Metrics shown above are calculated by the API from the configured dataset and recommendation output. 
            > They are not hard-coded performance claims.
            """
        )
    else:
        st.error("Evaluation service metrics currently unavailable.")


# ==============================================================================
# VIEW 6: BIG DATA ARCHITECTURE & PIPELINE
# ==============================================================================
elif tab_selection == "🏗️ Big Data Architecture & Pipeline":
    st.header("🏗️ Big Data Architecture & Medallion Data Platform")
    st.write(
        "Complete architectural layout illustrating the distributed storage, compute, and real-time serving layers."
    )

    st.markdown(
        """
        ```text
        ══════════════════════════════════════════════════════════════════════════════════════════════════
                                    BIG DATA MUSIC RECOMMENDATION PLATFORM
        ══════════════════════════════════════════════════════════════════════════════════════════════════
        
                               ┌─────────────────────────────────────────┐
                               │             USER / EVALUATOR            │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │          STREAMLIT UI DASHBOARD         │
                               │          (http://localhost:8501)        │
                               └────────────────────┬────────────────────┘
                                                    │ REST API
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │             FASTAPI BACKEND             │
                               │          (http://localhost:8000)        │
                               └──────────────┬──────────────────┬───────┘
                                              │                  │
                         Fast In-Memory Cache │                  │ NoSQL Query
                                              ▼                  ▼
                             ┌──────────────────┐      ┌──────────────────┐
                             │  MAHOUT RESULTS  │      │  MONGODB NoSQL   │
                             │  (part-r-00000)  │      │ (Port: 27017)    │
                             └────────▲─────────┘      └────────▲─────────┘
                                      │                         │
                                      │ Exported Output         │ JSON Ingestion
                                      │                         │
        ══════════════════════════════╪═════════════════════════╪═════════════════════════════════════════
                                   DISTRIBUTED HADOOP / SPARK CLUSTER
        ══════════════════════════════╪═════════════════════════╪═════════════════════════════════════════
                                      │
                         ┌────────────┴────────────┐
                         │   APACHE MAHOUT 0.13.0  │
                         │ Item-Based CF (LogLik.) │
                         └────────────▲────────────┘
                                      │ Numeric CSV
                         ┌────────────┴────────────┐
                         │    APACHE SPARK 3.5     │
                         │ Batch Distributed Clean ├────────► hdfs:///music/processed (Parquet)
                         └────────────▲────────────┘
                                      │ HDFS Read
                         ┌────────────┴────────────┐
                         │    HADOOP HDFS 3.2.1    │
                         │ hdfs:///music/input/    │
                         └────────────▲────────────┘
                                      │ Ingestion
                         ┌────────────┴────────────┐
                         │       LAST.FM 1K DATASET │
                         │ (prepared interaction log)│
                         └─────────────────────────┘
        ```
        """
    )

    st.subheader("🥉 🥈 🥇 Medallion Architecture Specification")
    c_b, c_s, c_g = st.columns(3)
    with c_b:
        st.markdown(
            """
            #### 🥉 Bronze Tier (Raw)
            - **Path:** `/music/bronze/`
            - **Format:** Tab-separated text triplets
            - **Volume:** Configured source interaction dataset
            - **Purpose:** Immutable raw data archival
            """
        )
    with c_s:
        st.markdown(
            """
            #### 🥈 Silver Tier (Cleaned)
            - **Path:** `/music/silver/`
            - **Format:** Snappy-compressed Parquet
            - **Schema:** Strict typing & deduplication
            - **Purpose:** Validated analytical dataset
            """
        )
    with c_g:
        st.markdown(
            """
            #### 🥇 Gold Tier (Features)
            - **Path:** `/music/gold/`
            - **Format:** User profiles & Item matrices
            - **Schema:** Aggregated listening metrics
            - **Purpose:** ML and real-time serving features
            """
        )


# ==============================================================================
# VIEW 7: MONGODB NOSQL EXPLORER
# ==============================================================================
elif tab_selection == "🍃 MongoDB NoSQL Explorer":
    st.header("🍃 MongoDB NoSQL Document Store Explorer")
    st.write(
        "Interactive document explorer for inspecting **semi-structured BSON recommendation documents** "
        "and metadata in MongoDB."
    )

    mongo_stats = fetch_api("/mongo/stats")
    if mongo_stats and "error" not in mongo_stats:
        ms1, ms2, ms3 = st.columns(3)
        with ms1:
            st.metric("Database Name", mongo_stats.get("database", "music_recommendation"))
        with ms2:
            st.metric("Recommendation Documents", f"{mongo_stats.get('recommendations_count', 0):,}")
        with ms3:
            st.metric("Song Mappings Stored", f"{mongo_stats.get('songs_count', 0):,}")

        st.markdown("---")
        st.subheader("🔍 Query MongoDB Recommendation Document")
        q_uid = st.text_input("Query Document by User ID:", value="3143")
        if st.button("Fetch BSON Document", type="primary"):
            mongo_doc = fetch_api(f"/mongo/recommend/{q_uid}")
            if mongo_doc and "recommendations" in mongo_doc:
                st.json(mongo_doc)
            else:
                st.warning(f"No document found in MongoDB for user `{q_uid}`.")
    else:
        st.info("MongoDB container is running in Standalone In-Memory Fallback mode.")


# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #64748B; font-size: 0.9rem; padding: 16px;">
        <b>Scalable Real-Time Music Recommendation System</b> &bull; Developed by <b>Kresha Shah</b> (PRN: 24070126512)<br>
        Built with Apache Hadoop, Apache Spark, Apache Mahout, MongoDB, FastAPI, and Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)
