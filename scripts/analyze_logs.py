"""Analyze action_log.db for statistics: send rates, latency, status distribution.

Usage: conda run -n bot python scripts/analyze_logs.py [db_path]
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from datetime import datetime


def analyze(db_path: str = "data/action_log.db") -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print(f"=== Action Log Analysis: {db_path} ===\n")

    # Total actions
    total = conn.execute("SELECT COUNT(*) as cnt FROM action_log").fetchone()["cnt"]
    print(f"Total actions: {total}")

    if total == 0:
        print("No actions recorded.")
        return

    # Status distribution
    print("\n--- Status Distribution ---")
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM action_log GROUP BY status ORDER BY cnt DESC"
    ).fetchall()
    for r in rows:
        pct = r["cnt"] / total * 100
        print(f"  {r['status']:12s}: {r['cnt']:5d} ({pct:.1f}%)")

    # Trigger type distribution
    print("\n--- Trigger Type Distribution ---")
    rows = conn.execute(
        "SELECT trigger_type, COUNT(*) as cnt FROM action_log GROUP BY trigger_type ORDER BY cnt DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['trigger_type'] or 'N/A':20s}: {r['cnt']:5d}")

    # Chat type distribution
    print("\n--- Chat Type Distribution ---")
    rows = conn.execute(
        "SELECT chat_type, COUNT(*) as cnt FROM action_log GROUP BY chat_type ORDER BY cnt DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['chat_type']:12s}: {r['cnt']:5d}")

    # Latency stats for sent messages
    print("\n--- Latency (sent messages) ---")
    lat_row = conn.execute(
        "SELECT AVG(latency_ms) as avg_lat, MIN(latency_ms) as min_lat, MAX(latency_ms) as max_lat, COUNT(*) as cnt "
        "FROM action_log WHERE status = 'sent' AND latency_ms IS NOT NULL"
    ).fetchone()
    if lat_row and lat_row["cnt"] > 0:
        print(f"  Count: {lat_row['cnt']}")
        print(f"  Avg:   {lat_row['avg_lat']:.0f}ms")
        print(f"  Min:   {lat_row['min_lat']}ms")
        print(f"  Max:   {lat_row['max_lat']}ms")
    else:
        print("  No sent messages with latency data.")

    # Cancelled/failed reasons
    print("\n--- Cancellation Reasons ---")
    rows = conn.execute(
        "SELECT cancelled_reason, COUNT(*) as cnt FROM action_log WHERE status = 'cancelled' AND cancelled_reason IS NOT NULL GROUP BY cancelled_reason"
    ).fetchall()
    for r in rows:
        print(f"  {r['cancelled_reason']:30s}: {r['cnt']}")

    print("\n--- Failure Reasons ---")
    rows = conn.execute(
        "SELECT send_error, COUNT(*) as cnt FROM action_log WHERE status = 'failed' AND send_error IS NOT NULL GROUP BY send_error"
    ).fetchall()
    for r in rows:
        print(f"  {r['send_error'][:50]:50s}: {r['cnt']}")

    # Time distribution (by hour)
    print("\n--- Hourly Distribution (created_at) ---")
    rows = conn.execute(
        "SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour, COUNT(*) as cnt "
        "FROM action_log GROUP BY hour ORDER BY hour"
    ).fetchall()
    max_cnt = max((r["cnt"] for r in rows), default=1)
    for r in rows:
        bar = "#" * int(r["cnt"] / max_cnt * 40)
        print(f"  {r['hour']:02d}:00  {r['cnt']:5d} {bar}")

    # State machine completeness
    print("\n--- State Machine Transitions ---")
    for status in ("planned", "generated", "scheduled", "sending", "sent", "cancelled", "failed"):
        cnt = conn.execute(
            "SELECT COUNT(*) as cnt FROM action_log WHERE status = ?", (status,)
        ).fetchone()["cnt"]
        print(f"  {status:12s}: {cnt}")

    conn.close()
    print("\n=== Analysis Complete ===")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/action_log.db"
    analyze(path)
