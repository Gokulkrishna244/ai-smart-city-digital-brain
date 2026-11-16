import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "Models" / "smart_city.db"


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            city_area TEXT NOT NULL,
            prediction TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("""CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
        city TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL,
        explanation TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
        source TEXT NOT NULL DEFAULT 'simulated_sensor', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status_created ON incidents(status, created_at DESC)")
    cursor.execute("""CREATE TABLE IF NOT EXISTS grievances (
        id INTEGER PRIMARY KEY AUTOINCREMENT, citizen_name TEXT NOT NULL,
        category TEXT NOT NULL, location TEXT NOT NULL, description TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'medium', status TEXT NOT NULL DEFAULT 'submitted',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_grievances_status_created ON grievances(status, created_at DESC)")
    existing_columns = {row[1] for row in cursor.execute("PRAGMA table_info(incidents)").fetchall()}
    if "assigned_team" not in existing_columns:
        cursor.execute("ALTER TABLE incidents ADD COLUMN assigned_team TEXT")
    if "response_eta" not in existing_columns:
        cursor.execute("ALTER TABLE incidents ADD COLUMN response_eta INTEGER")
    conn.commit()
    conn.close()


def save_prediction(module_name, city_area, prediction):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO predictions (module, city_area, prediction) VALUES (?, ?, ?)",
        (module_name, city_area, prediction),
    )
    conn.commit()
    conn.close()


def get_recent_predictions(limit=10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, module, city_area, prediction, created_at FROM predictions ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_prediction_count_today():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE date(created_at, 'localtime') = date('now', 'localtime')"
    ).fetchone()[0]
    conn.close()
    return int(count)


def upsert_incident(fingerprint, city, category, severity, explanation, source="simulated_sensor"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO incidents (fingerprint, city, category, severity, explanation, source)
        VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(fingerprint) DO UPDATE SET
        severity=excluded.severity, explanation=excluded.explanation, updated_at=CURRENT_TIMESTAMP""",
        (fingerprint, city, category, severity, explanation, source))
    conn.commit(); conn.close()


def get_incidents(status="open", limit=50):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    query, values = "SELECT id, city, category, severity, explanation, status, source, assigned_team, response_eta, created_at, updated_at FROM incidents", []
    if status:
        query += " WHERE status = ?"; values.append(status)
    query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'warning' THEN 3 ELSE 4 END, updated_at DESC LIMIT ?"; values.append(limit)
    rows = conn.execute(query, values).fetchall(); conn.close()
    return [dict(row) for row in rows]


def update_incident_status(incident_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("UPDATE incidents SET status=?, updated_at=? WHERE id=?", (status, datetime.utcnow().isoformat(timespec="seconds"), incident_id))
    conn.commit(); conn.close()
    return cursor.rowcount


def assign_incident(incident_id, team, response_eta, status="acknowledged"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "UPDATE incidents SET assigned_team=?, response_eta=?, status=?, updated_at=? WHERE id=?",
        (team, response_eta, status, datetime.utcnow().isoformat(timespec="seconds"), incident_id),
    )
    conn.commit(); conn.close()
    return cursor.rowcount


def save_grievance(citizen_name, category, location, description, priority="medium"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "INSERT INTO grievances (citizen_name, category, location, description, priority) VALUES (?, ?, ?, ?, ?)",
        (citizen_name, category, location, description, priority),
    )
    grievance_id = cursor.lastrowid
    conn.commit(); conn.close()
    return grievance_id


def get_grievances(limit=50):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM grievances ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_grievance_status(grievance_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("UPDATE grievances SET status=?, updated_at=? WHERE id=?", (status, datetime.utcnow().isoformat(timespec="seconds"), grievance_id))
    conn.commit(); conn.close()
    return cursor.rowcount


if __name__ == "__main__":
    init_db()
    print("Database initialized")
