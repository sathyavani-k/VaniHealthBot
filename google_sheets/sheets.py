"""
Google Sheets integration for VaniHealthBot.
Logs meals, body scans, and weight data to a connected spreadsheet.
"""

import os
import json
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None
_spreadsheet = None


def _get_sheet():
    global _client, _spreadsheet
    if not GSPREAD_AVAILABLE:
        return None
    if _spreadsheet:
        return _spreadsheet

    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")

    if not os.path.exists(creds_path) or not sheet_id:
        return None

    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(sheet_id)
        return _spreadsheet
    except Exception as e:
        print(f"Google Sheets connection error: {e}")
        return None


def _get_or_create_worksheet(spreadsheet, title, headers):
    try:
        ws = spreadsheet.worksheet(title)
    except Exception:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers)
    return ws


def append_meal_to_sheet(telegram_id, description, calories, protein, carbs, fat):
    sheet = _get_sheet()
    if not sheet:
        return
    try:
        ws = _get_or_create_worksheet(sheet, "Meals", [
            "Timestamp", "UserID", "Description", "Calories", "Protein(g)", "Carbs(g)", "Fat(g)"
        ])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(telegram_id), description,
            round(calories, 1), round(protein, 1), round(carbs, 1), round(fat, 1)
        ])
    except Exception as e:
        print(f"Sheets append_meal error: {e}")


def append_body_scan_to_sheet(telegram_id, data: dict):
    sheet = _get_sheet()
    if not sheet:
        return
    try:
        ws = _get_or_create_worksheet(sheet, "Body Scans", [
            "Timestamp", "UserID", "Weight(kg)", "BodyFat(%)", "MuscleMass(kg)",
            "BodyWater(%)", "BoneMass(kg)", "SkeletalMuscle(%)",
            "VisceralFat", "BMI", "Protein(%)", "MetabolicAge", "BodyType"
        ])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(telegram_id),
            data.get("weight_kg", ""),
            data.get("body_fat_pct", ""),
            data.get("muscle_mass_kg", ""),
            data.get("body_water_pct", ""),
            data.get("bone_mass_kg", ""),
            data.get("skeletal_muscle_pct", ""),
            data.get("visceral_fat_index", ""),
            data.get("bmi", ""),
            data.get("protein_pct", ""),
            data.get("metabolic_age", ""),
            data.get("body_type", ""),
        ])
    except Exception as e:
        print(f"Sheets append_body_scan error: {e}")


def append_weight_to_sheet(telegram_id, weight_kg):
    sheet = _get_sheet()
    if not sheet:
        return
    try:
        ws = _get_or_create_worksheet(sheet, "Weight Log", [
            "Timestamp", "UserID", "Weight(kg)"
        ])
        ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), str(telegram_id), weight_kg])
    except Exception as e:
        print(f"Sheets append_weight error: {e}")


def append_fitness_test_to_sheet(telegram_id, data: dict):
    sheet = _get_sheet()
    if not sheet:
        return
    try:
        ws = _get_or_create_worksheet(sheet, "Fitness Tests", [
            "Timestamp", "UserID", "TestType", "Pushups", "Situps",
            "Run2.4km", "Plank(sec)", "Deadhang(sec)", "Score", "Band"
        ])
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(telegram_id),
            data.get("test_type", ""),
            data.get("pushups", ""),
            data.get("situps", ""),
            data.get("run_2_4km_sec", ""),
            data.get("plank_sec", ""),
            data.get("dead_hang_sec", ""),
            data.get("score", ""),
            data.get("band", ""),
        ])
    except Exception as e:
        print(f"Sheets append_fitness_test error: {e}")
