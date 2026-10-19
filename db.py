"""
GoodLight Time-Series Historical Metrics Storage Module.
Built on lightweight standard library SQLite:
Records:
1. System performance metrics (CPU %, Memory RSS MB, Memory VMS MB)
2. Per-fixture actual/predicted brightness and color temperature history
Supports up to 30 days retention with multi-range aggregated downsampling (1h, 24h, 7d, 30d).
"""

import sqlite3
import time
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

DEFAULT_TZ = timezone(timedelta(hours=8))

class HistoryDB:
    def __init__(self, db_path: str = "history.db"):
        self.db_path = db_path
        self.init_db()

    def get_conn(self):
        """Create and return a new SQLite connection with Row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database schema and indices."""
        with self.get_conn() as conn:
            # System metrics timeline table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    cpu_percent REAL,
                    mem_rss_mb REAL,
                    mem_vms_mb REAL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sys_ts ON system_metrics(timestamp);")

            # Fixture state timeline table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS light_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    entity_id TEXT NOT NULL,
                    brightness REAL,
                    color_temp INTEGER,
                    state TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_light_ts ON light_history(timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_light_ent ON light_history(entity_id);")
            try:
                conn.execute("""
                    DELETE FROM light_history 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM light_history 
                        GROUP BY entity_id, timestamp
                    );
                """)
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_light_unique ON light_history(entity_id, timestamp);")
            except Exception:
                pass

    def record_metrics(self, cpu: float, rss_mb: float, vms_mb: float):
        """Insert a snapshot of system resource metrics."""
        now_ts = int(time.time())
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO system_metrics (timestamp, cpu_percent, mem_rss_mb, mem_vms_mb) VALUES (?, ?, ?, ?)",
                (now_ts, cpu, rss_mb, vms_mb)
            )

    def record_light_state(self, entity_id: str, brightness: float, color_temp: int, state: str, timestamp: int = None):
        """Record state of a single light entity."""
        now_ts = int(timestamp) if timestamp is not None else int(time.time())
        with self.get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO light_history (timestamp, entity_id, brightness, color_temp, state) VALUES (?, ?, ?, ?, ?)",
                (now_ts, entity_id, brightness, color_temp, state)
            )

    def cleanup_old_data(self, max_days: int = 30):
        """Prune records older than max_days to maintain a small database footprint."""
        expire_ts = int(time.time()) - (max_days * 86400)
        with self.get_conn() as conn:
            conn.execute("DELETE FROM system_metrics WHERE timestamp < ?", (expire_ts,))
            conn.execute("DELETE FROM light_history WHERE timestamp < ?", (expire_ts,))

    def query_metrics(self, hours: float = 24.0, tz=None) -> Dict[str, List[Any]]:
        """Query system performance metrics over a time window."""
        start_ts = int(time.time() - hours * 3600)
        step = 1
        if hours > 24 * 7:
            step = 120
        elif hours > 24:
            step = 30
        elif hours > 1:
            step = 5

        with self.get_conn() as conn:
            cur = conn.execute("""
                SELECT timestamp, cpu_percent, mem_rss_mb 
                FROM system_metrics 
                WHERE timestamp >= ? AND (id % ?) = 0
                ORDER BY timestamp ASC
            """, (start_ts, step))
            rows = cur.fetchall()

        effective_tz = tz or DEFAULT_TZ
        timestamps = []
        cpu_list = []
        mem_list = []
        for r in rows:
            dt = datetime.fromtimestamp(r["timestamp"], tz=effective_tz)
            dt_str = dt.strftime("%m-%d %H:%M" if hours > 24 else "%H:%M")
            timestamps.append(dt_str)
            cpu_list.append(round(r["cpu_percent"], 1))
            mem_list.append(round(r["mem_rss_mb"], 1))

        return {
            "labels": timestamps,
            "cpu": cpu_list,
            "memory": mem_list
        }

    def query_light_history(self, hours: float = 24.0, tz=None) -> Dict[str, Any]:
        """Query light history downsampled per entity for smooth chart rendering."""
        start_ts = int(time.time() - hours * 3600)
        stride = 1
        if hours > 24 * 7:
            stride = 60
        elif hours > 24:
            stride = 15
        elif hours > 1:
            stride = 2

        with self.get_conn() as conn:
            cur = conn.execute("""
                SELECT timestamp, entity_id, brightness, color_temp 
                FROM light_history 
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (start_ts,))
            rows = cur.fetchall()

        effective_tz = tz or DEFAULT_TZ
        raw_entities = {}
        for r in rows:
            ent = r["entity_id"]
            if ent not in raw_entities:
                raw_entities[ent] = []
            raw_entities[ent].append(r)

        entities = {}
        for ent, ent_rows in raw_entities.items():
            sampled = ent_rows[::stride]
            entities[ent] = {"labels": [], "brightness": [], "color_temp": []}
            for r in sampled:
                dt = datetime.fromtimestamp(r["timestamp"], tz=effective_tz)
                dt_str = dt.strftime("%m-%d %H:%M" if hours > 24 else "%H:%M")
                entities[ent]["labels"].append(dt_str)
                entities[ent]["brightness"].append(round(r["brightness"], 1) if r["brightness"] is not None else 0)
                entities[ent]["color_temp"].append(r["color_temp"] if (r["color_temp"] is not None and r["color_temp"] > 0) else None)

        return entities
