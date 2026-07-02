#!/usr/bin/env python3
"""heimdall-acs.py — ACS Graph Engine

SQLite schema with nodes and edges table for system state events,
conversation triples, and causality links.
"""

import sqlite3
import json
import time

DB_PATH = "/var/lib/aegis/heimdall-context.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            type TEXT,
            label TEXT,
            payload_human TEXT,
            payload_ai TEXT,
            timestamp REAL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS edges (
            source_id TEXT,
            target_id TEXT,
            relation TEXT,
            weight REAL,
            FOREIGN KEY(source_id) REFERENCES nodes(id),
            FOREIGN KEY(target_id) REFERENCES nodes(id)
        )
    ''')
    conn.commit()
    conn.close()

def insert_event(node_id, node_type, label, payload_human, payload_ai):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO nodes (id, type, label, payload_human, payload_ai, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (node_id, node_type, label, payload_human, payload_ai, time.time())
    )
    conn.commit()
    conn.close()

def insert_edge(source_id, target_id, relation, weight=1.0):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO edges (source_id, target_id, relation, weight) VALUES (?, ?, ?, ?)",
        (source_id, target_id, relation, weight)
    )
    conn.commit()
    conn.close()

def query_neighborhood(node_id, degrees=2):
    # Simplified neighborhood query
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT target_id FROM edges WHERE source_id=?", (node_id,))
    targets = [r[0] for r in cur.fetchall()]
    nodes = []
    for t in targets:
        cur.execute("SELECT * FROM nodes WHERE id=?", (t,))
        res = cur.fetchone()
        if res: nodes.append(res)
    conn.close()
    return nodes

def get_compressed_summary():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, label, payload_human FROM nodes ORDER BY timestamp DESC LIMIT 10")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return "\n".join([f"- {r[1]}: {r[2]}" for r in rows])

if __name__ == "__main__":
    init_db()
