"""
SQLite database layer for VaniHealthBot.
Handles all CRUD operations for every feature.
"""

import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vanihealth.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id     INTEGER PRIMARY KEY,
            name            TEXT,
            age             INTEGER,
            height_cm       REAL,
            weight_kg       REAL,
            body_fat_pct    REAL,
            goal_bf_pct     REAL,
            activity_level  TEXT,   -- sedentary / light / moderate / active / very_active
            tdee            REAL,
            calorie_target  REAL,
            protein_g       REAL,
            carbs_g         REAL,
            fat_g           REAL,
            equipment       TEXT DEFAULT 'full_gym',  -- full_gym / dumbbells / bodyweight
            workout_duration_min INTEGER DEFAULT 45,
            cycle_start_date TEXT,   -- ISO date of last period start
            cycle_length    INTEGER DEFAULT 28,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS meal_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            description TEXT,
            calories    REAL,
            protein_g   REAL,
            carbs_g     REAL,
            fat_g       REAL,
            meal_type   TEXT,   -- breakfast / lunch / dinner / snack
            photo_path  TEXT
        );

        CREATE TABLE IF NOT EXISTS weight_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            weight_kg   REAL
        );

        CREATE TABLE IF NOT EXISTS body_scan_logs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id         INTEGER,
            logged_at           TEXT DEFAULT (datetime('now')),
            weight_kg           REAL,
            body_fat_pct        REAL,
            muscle_mass_kg      REAL,
            body_water_pct      REAL,
            bone_mass_kg        REAL,
            skeletal_muscle_pct REAL,
            visceral_fat_index  REAL,
            bmi                 REAL,
            protein_pct         REAL,
            metabolic_age       INTEGER,
            body_type           TEXT,
            muscle_reserve      REAL,
            photo_path          TEXT
        );

        CREATE TABLE IF NOT EXISTS measurements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            waist_cm    REAL,
            hips_cm     REAL,
            chest_cm    REAL,
            left_arm_cm REAL,
            right_arm_cm REAL,
            left_thigh_cm REAL,
            right_thigh_cm REAL,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS water_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            amount_ml   REAL
        );

        CREATE TABLE IF NOT EXISTS supplement_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            supplement  TEXT,
            dose        TEXT,
            taken       INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS supplements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            name        TEXT,
            dose        TEXT,
            reminder_time TEXT
        );

        CREATE TABLE IF NOT EXISTS fitness_tests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER,
            tested_at       TEXT DEFAULT (datetime('now')),
            test_type       TEXT,   -- IPPT / ACFT / general
            pushups         INTEGER,
            situps          INTEGER,
            run_2_4km_sec   INTEGER,
            run_1_5mi_sec   INTEGER,
            run_2mi_sec     INTEGER,
            deadlift_kg     REAL,
            plank_sec       INTEGER,
            dead_hang_sec   INTEGER,
            wall_sit_sec    INTEGER,
            score           TEXT,
            band            TEXT,
            notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER,
            checked_in_at   TEXT DEFAULT (datetime('now')),
            weight_kg       REAL,
            body_fat_pct    REAL,
            workouts_done   INTEGER,
            energy_level    INTEGER,  -- 1-5
            stress_level    INTEGER,  -- 1-5
            sleep_hours     REAL,
            notes           TEXT,
            ai_feedback     TEXT
        );

        CREATE TABLE IF NOT EXISTS progress_photos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            file_id     TEXT,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS streaks (
            telegram_id         INTEGER PRIMARY KEY,
            workout_streak      INTEGER DEFAULT 0,
            logging_streak      INTEGER DEFAULT 0,
            water_streak        INTEGER DEFAULT 0,
            last_workout_date   TEXT,
            last_log_date       TEXT,
            last_water_date     TEXT
        );

        CREATE TABLE IF NOT EXISTS victories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            logged_at   TEXT DEFAULT (datetime('now')),
            victory     TEXT,
            category    TEXT  -- strength / endurance / nutrition / body / mindset
        );

        CREATE TABLE IF NOT EXISTS workout_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER,
            logged_at       TEXT DEFAULT (datetime('now')),
            workout_name    TEXT,
            duration_min    INTEGER,
            intensity       INTEGER,  -- 1-5
            notes           TEXT
        );
    """)

    conn.commit()
    conn.close()


# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(data: dict):
    conn = get_conn()
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    updates = ", ".join([f"{k}=excluded.{k}" for k in data.keys() if k != "telegram_id"])
    conn.execute(
        f"INSERT INTO users ({keys}) VALUES ({placeholders}) ON CONFLICT(telegram_id) DO UPDATE SET {updates}",
        list(data.values())
    )
    conn.commit()
    conn.close()


def get_user(telegram_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Meal Logs ────────────────────────────────────────────────────────────────

def log_meal(telegram_id, description, calories, protein, carbs, fat, meal_type="meal", photo_path=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO meal_logs (telegram_id, description, calories, protein_g, carbs_g, fat_g, meal_type, photo_path) VALUES (?,?,?,?,?,?,?,?)",
        (telegram_id, description, calories, protein, carbs, fat, meal_type, photo_path)
    )
    conn.commit()
    conn.close()


def get_today_meals(telegram_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM meal_logs WHERE telegram_id=? AND date(logged_at)=date('now') ORDER BY logged_at",
        (telegram_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_meal_history(telegram_id, days=7):
    conn = get_conn()
    rows = conn.execute(
        """SELECT date(logged_at) as day,
                  SUM(calories) as total_cal,
                  SUM(protein_g) as total_protein,
                  SUM(carbs_g) as total_carbs,
                  SUM(fat_g) as total_fat
           FROM meal_logs
           WHERE telegram_id=? AND date(logged_at) >= date('now', ?)
           GROUP BY day ORDER BY day DESC""",
        (telegram_id, f"-{days} days")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Weight Logs ──────────────────────────────────────────────────────────────

def log_weight(telegram_id, weight_kg):
    conn = get_conn()
    conn.execute("INSERT INTO weight_logs (telegram_id, weight_kg) VALUES (?,?)", (telegram_id, weight_kg))
    conn.commit()
    conn.close()


def get_weight_history(telegram_id, limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM weight_logs WHERE telegram_id=? ORDER BY logged_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Body Scans ───────────────────────────────────────────────────────────────

def log_body_scan(telegram_id, data: dict):
    data["telegram_id"] = telegram_id
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    conn = get_conn()
    conn.execute(f"INSERT INTO body_scan_logs ({keys}) VALUES ({placeholders})", list(data.values()))
    conn.commit()
    conn.close()


def get_scan_history(telegram_id, limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM body_scan_logs WHERE telegram_id=? ORDER BY logged_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Measurements ─────────────────────────────────────────────────────────────

def log_measurements(telegram_id, data: dict):
    data["telegram_id"] = telegram_id
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    conn = get_conn()
    conn.execute(f"INSERT INTO measurements ({keys}) VALUES ({placeholders})", list(data.values()))
    conn.commit()
    conn.close()


def get_measurement_history(telegram_id, limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM measurements WHERE telegram_id=? ORDER BY logged_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Water ────────────────────────────────────────────────────────────────────

def log_water(telegram_id, amount_ml):
    conn = get_conn()
    conn.execute("INSERT INTO water_logs (telegram_id, amount_ml) VALUES (?,?)", (telegram_id, amount_ml))
    conn.commit()
    conn.close()


def get_today_water(telegram_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT SUM(amount_ml) as total FROM water_logs WHERE telegram_id=? AND date(logged_at)=date('now')",
        (telegram_id,)
    ).fetchone()
    conn.close()
    return row["total"] or 0


# ─── Fitness Tests ────────────────────────────────────────────────────────────

def log_fitness_test(telegram_id, data: dict):
    data["telegram_id"] = telegram_id
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    conn = get_conn()
    conn.execute(f"INSERT INTO fitness_tests ({keys}) VALUES ({placeholders})", list(data.values()))
    conn.commit()
    conn.close()


def get_fitness_history(telegram_id, limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM fitness_tests WHERE telegram_id=? ORDER BY tested_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Check-ins ────────────────────────────────────────────────────────────────

def log_checkin(telegram_id, data: dict):
    data["telegram_id"] = telegram_id
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    conn = get_conn()
    conn.execute(f"INSERT INTO checkins ({keys}) VALUES ({placeholders})", list(data.values()))
    conn.commit()
    conn.close()


def get_checkin_history(telegram_id, limit=4):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM checkins WHERE telegram_id=? ORDER BY checked_in_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Streaks ──────────────────────────────────────────────────────────────────

def get_streaks(telegram_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM streaks WHERE telegram_id=?", (telegram_id,)).fetchone()
    if not row:
        conn.execute("INSERT INTO streaks (telegram_id) VALUES (?)", (telegram_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM streaks WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row)


def update_streak(telegram_id, streak_type: str):
    """streak_type: workout / logging / water"""
    today = str(date.today())
    streaks = get_streaks(telegram_id)
    last_key = f"last_{streak_type}_date"
    streak_key = f"{streak_type}_streak"
    last = streaks.get(last_key)

    from datetime import timedelta
    yesterday = str(date.today() - timedelta(days=1))

    if last == today:
        return  # already updated today
    elif last == yesterday:
        new_streak = streaks[streak_key] + 1
    else:
        new_streak = 1

    conn = get_conn()
    conn.execute(
        f"UPDATE streaks SET {streak_key}=?, {last_key}=? WHERE telegram_id=?",
        (new_streak, today, telegram_id)
    )
    conn.commit()
    conn.close()


# ─── Workout Logs ─────────────────────────────────────────────────────────────

def log_workout(telegram_id, name, duration_min, intensity, notes=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO workout_logs (telegram_id, workout_name, duration_min, intensity, notes) VALUES (?,?,?,?,?)",
        (telegram_id, name, duration_min, intensity, notes)
    )
    conn.commit()
    conn.close()
    update_streak(telegram_id, "workout")


# ─── Progress Photos ──────────────────────────────────────────────────────────

def save_progress_photo(telegram_id, file_id, notes=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO progress_photos (telegram_id, file_id, notes) VALUES (?,?,?)",
        (telegram_id, file_id, notes)
    )
    conn.commit()
    conn.close()


def get_progress_photos(telegram_id, limit=6):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM progress_photos WHERE telegram_id=? ORDER BY logged_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Victories ────────────────────────────────────────────────────────────────

def log_victory(telegram_id, victory, category="general"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO victories (telegram_id, victory, category) VALUES (?,?,?)",
        (telegram_id, victory, category)
    )
    conn.commit()
    conn.close()


def get_recent_victories(telegram_id, limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM victories WHERE telegram_id=? ORDER BY logged_at DESC LIMIT ?",
        (telegram_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Supplements ──────────────────────────────────────────────────────────────

def add_supplement(telegram_id, name, dose, reminder_time=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO supplements (telegram_id, name, dose, reminder_time) VALUES (?,?,?,?)",
        (telegram_id, name, dose, reminder_time)
    )
    conn.commit()
    conn.close()


def get_supplements(telegram_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM supplements WHERE telegram_id=?", (telegram_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
