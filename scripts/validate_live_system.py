#!/usr/bin/env python3
"""
Live System Health & Endpoint Validation Script
Tests all live endpoints on FastAPI and Streamlit.
"""
from __future__ import annotations

import json
import urllib.request


def check_get(url: str, description: str):
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = resp.read().decode("utf-8")
            status = resp.status
            try:
                json_data = json.loads(data)
                keys = list(json_data.keys()) if isinstance(json_data, dict) else f"list({len(json_data)})"
                print(f"[PASS] {status} {description} -> {keys}")
            except Exception:
                print(f"[PASS] {status} {description} -> HTML Content ({len(data)} bytes)")
    except Exception as exc:
        print(f"[FAIL] {description} -> {exc}")


def check_post(url: str, payload: dict, description: str):
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            status = resp.status
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[PASS] {status} {description} -> Status: {data.get('status')}")
    except Exception as exc:
        print(f"[FAIL] {description} -> {exc}")


def main():
    print("================================================================")
    print("       LIVE END-TO-END VALIDATION: FASTAPI + STREAMLIT          ")
    print("================================================================")
    base_api = "http://127.0.0.1:8000"
    base_st = "http://localhost:8501"

    check_get(f"{base_api}/", "GET / (Root Welcome)")
    check_get(f"{base_api}/health", "GET /health (Cluster Health)")
    check_get(f"{base_api}/api/info", "GET /api/info (Architecture Info)")
    check_get(f"{base_api}/recommend/1?n=5&strategy=hybrid", "GET /recommend/1 (User 1 Hybrid Recs)")
    check_get(f"{base_api}/recommend/2?n=5&strategy=hybrid", "GET /recommend/2 (User 2 Hybrid Recs)")
    check_get(f"{base_api}/recommend/999999?n=5&strategy=hybrid", "GET /recommend/999999 (Cold-Start Recs)")
    check_get(f"{base_api}/similar/103?n=5", "GET /similar/103 (Similar Songs)")
    check_get(f"{base_api}/songs/103", "GET /songs/103 (Song Info)")
    check_get(f"{base_api}/user/1/history?limit=5", "GET /user/1/history (Listening History)")
    check_get(f"{base_api}/evaluation/metrics", "GET /evaluation/metrics (Holdout Evaluation)")
    check_get(f"{base_api}/live/stats", "GET /live/stats (Streaming Stats)")
    check_get(f"{base_api}/mongo/stats", "GET /mongo/stats (MongoDB Stats)")

    check_post(
        f"{base_api}/events",
        {"user_id": "1", "song_id": "103", "event_type": "like"},
        "POST /events (Live Event Ingestion)",
    )

    check_get(f"{base_st}/", "GET http://localhost:8501 (Streamlit Dashboard UI)")
    print("================================================================\n")


if __name__ == "__main__":
    main()
