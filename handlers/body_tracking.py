"""
Body scan (PICOOC OCR), weight tracking, measurements, and progress handlers.
"""

import os
import base64
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database.db import (
    log_weight, log_body_scan, log_measurements,
    get_weight_history, get_scan_history, get_measurement_history, get_user
)
from google_sheets.sheets import append_body_scan_to_sheet, append_weight_to_sheet
from utils.calculations import estimate_weeks_to_goal, progress_bar
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def log_weight_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/log_weight 62.5`", parse_mode="Markdown")
        return

    try:
        weight = float(args[0])
    except ValueError:
        await update.message.reply_text("Please enter a valid number, e.g. `/log_weight 62.5`", parse_mode="Markdown")
        return

    log_weight(update.effective_user.id, weight)
    append_weight_to_sheet(update.effective_user.id, weight)

    history = get_weight_history(update.effective_user.id, limit=5)
    trend = ""
    if len(history) >= 2:
        diff = history[0]["weight_kg"] - history[1]["weight_kg"]
        if diff < 0:
            trend = f"\n📉 Down {abs(diff):.1f}kg from last entry — great progress!"
        elif diff > 0:
            trend = f"\n📈 Up {diff:.1f}kg from last entry. Remember: fluctuations are normal!"
        else:
            trend = "\n➡️ Same as last entry."

    await update.message.reply_text(
        f"⚖️ *Weight logged:* {weight}kg\n"
        f"✅ Synced to Google Sheets!{trend}",
        parse_mode="Markdown"
    )


async def handle_picooc_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Detect if a photo is a PICOOC measurement report.
    This is triggered when user sends a photo with caption containing 'picooc', 'scan', 'weight scan'
    or when the bot detects it's a PICOOC report via vision.
    """
    user = get_user(update.effective_user.id)
    if not user:
        return

    caption = (update.message.caption or "").lower()
    is_scan = any(kw in caption for kw in ["picooc", "scan", "weight scan", "body scan", "measurement"])

    if not is_scan:
        return False  # Let food photo handler deal with it

    await update.message.reply_text("📊 Reading your PICOOC body scan...")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()
    photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": photo_b64}
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is a PICOOC body composition measurement report. "
                            "Extract ALL the numeric values you can see. "
                            "Respond ONLY in this exact format (use 'N/A' if not visible):\n"
                            "WEIGHT: [kg]\n"
                            "BODY_FAT: [%]\n"
                            "MUSCLE_MASS: [kg]\n"
                            "BODY_WATER: [%]\n"
                            "BONE_MASS: [kg]\n"
                            "SKELETAL_MUSCLE: [%]\n"
                            "VISCERAL_FAT: [index number]\n"
                            "BMI: [number]\n"
                            "PROTEIN: [%]\n"
                            "METABOLIC_AGE: [years]\n"
                            "BODY_TYPE: [text description if visible]\n"
                            "MUSCLE_RESERVE: [number if visible]"
                        )
                    }
                ]
            }]
        )

        result = response.content[0].text
        lines = {}
        for line in result.strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                lines[key.strip()] = val.strip()

        def parse_float(val):
            try:
                return float(val.replace("%", "").replace("kg", "").strip())
            except Exception:
                return None

        scan_data = {
            "weight_kg": parse_float(lines.get("WEIGHT", "")),
            "body_fat_pct": parse_float(lines.get("BODY_FAT", "")),
            "muscle_mass_kg": parse_float(lines.get("MUSCLE_MASS", "")),
            "body_water_pct": parse_float(lines.get("BODY_WATER", "")),
            "bone_mass_kg": parse_float(lines.get("BONE_MASS", "")),
            "skeletal_muscle_pct": parse_float(lines.get("SKELETAL_MUSCLE", "")),
            "visceral_fat_index": parse_float(lines.get("VISCERAL_FAT", "")),
            "bmi": parse_float(lines.get("BMI", "")),
            "protein_pct": parse_float(lines.get("PROTEIN", "")),
            "metabolic_age": parse_float(lines.get("METABOLIC_AGE", "")),
            "body_type": lines.get("BODY_TYPE", ""),
        }
        scan_data = {k: v for k, v in scan_data.items() if v is not None and v != ""}

        log_body_scan(update.effective_user.id, scan_data)
        append_body_scan_to_sheet(update.effective_user.id, scan_data)

        # Build response
        bf = scan_data.get("body_fat_pct")
        goal_bf = user.get("goal_bf_pct", 20)
        weeks = None
        if bf and scan_data.get("weight_kg"):
            weeks = estimate_weeks_to_goal(bf, goal_bf, scan_data["weight_kg"])

        timeline_msg = f"\n⏳ Estimated {weeks} more weeks to {goal_bf}% body fat!" if weeks else ""

        reply = "✅ *PICOOC Scan Logged & Synced to Google Sheets!*\n\n📊 *Your body composition:*\n"
        field_map = [
            ("weight_kg", "⚖️ Weight", "kg"),
            ("body_fat_pct", "🔥 Body Fat", "%"),
            ("muscle_mass_kg", "💪 Muscle Mass", "kg"),
            ("body_water_pct", "💧 Body Water", "%"),
            ("bone_mass_kg", "🦴 Bone Mass", "kg"),
            ("skeletal_muscle_pct", "🏃 Skeletal Muscle", "%"),
            ("visceral_fat_index", "🫀 Visceral Fat Index", ""),
            ("bmi", "📏 BMI", ""),
            ("protein_pct", "🥩 Protein", "%"),
            ("metabolic_age", "🧬 Metabolic Age", " yrs"),
        ]
        for key, label, unit in field_map:
            if key in scan_data:
                reply += f"{label}: *{scan_data[key]}{unit}*\n"

        if scan_data.get("body_type"):
            reply += f"🏷️ Body Type: *{scan_data['body_type']}*\n"

        reply += timeline_msg

        await update.message.reply_text(reply, parse_mode="Markdown")
        return True

    except Exception as e:
        await update.message.reply_text(f"Couldn't read the scan. Try again with a clearer photo. Error: {e}")
        return True


async def progress_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    scans = get_scan_history(update.effective_user.id, limit=3)
    weights = get_weight_history(update.effective_user.id, limit=5)

    if not scans and not weights:
        await update.message.reply_text(
            "No progress data yet! Send me your PICOOC scan photo or use /log_weight to get started."
        )
        return

    reply = "📈 *Your Progress*\n\n"

    if scans:
        latest = scans[0]
        bf = latest.get("body_fat_pct")
        goal_bf = user.get("goal_bf_pct", 20)

        if bf:
            diff = bf - goal_bf
            reply += f"🔥 *Body Fat:* {bf}% → Goal: {goal_bf}%\n"
            reply += f"{progress_bar(goal_bf, bf, length=12)} {abs(diff):.1f}% to go\n\n"

        if latest.get("muscle_mass_kg"):
            reply += f"💪 *Muscle Mass:* {latest['muscle_mass_kg']}kg\n"
        if latest.get("visceral_fat_index"):
            reply += f"🫀 *Visceral Fat:* {latest['visceral_fat_index']}\n"

        if len(scans) >= 2:
            prev = scans[1]
            reply += "\n*Changes since last scan:*\n"
            for metric, label, unit in [
                ("body_fat_pct", "Body Fat", "%"),
                ("muscle_mass_kg", "Muscle Mass", "kg"),
                ("weight_kg", "Weight", "kg"),
                ("visceral_fat_index", "Visceral Fat", ""),
            ]:
                if latest.get(metric) and prev.get(metric):
                    diff = latest[metric] - prev[metric]
                    arrow = "📉" if diff < 0 else "📈"
                    reply += f"{arrow} {label}: {'+' if diff > 0 else ''}{diff:.1f}{unit}\n"

    if weights:
        reply += f"\n⚖️ *Latest weight:* {weights[0]['weight_kg']}kg\n"

    await update.message.reply_text(reply, parse_mode="Markdown")


async def log_measurements_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Log your body measurements! Format:\n"
            "`/measurements waist:72 hips:96 chest:88 left_arm:28 right_arm:28 left_thigh:54 right_thigh:54`\n\n"
            "You don't need all — just log what you have.",
            parse_mode="Markdown"
        )
        return

    data = {}
    field_map = {
        "waist": "waist_cm", "hips": "hips_cm", "chest": "chest_cm",
        "left_arm": "left_arm_cm", "right_arm": "right_arm_cm",
        "left_thigh": "left_thigh_cm", "right_thigh": "right_thigh_cm",
    }

    for part in text.split():
        if ":" in part:
            key, val = part.split(":")
            db_key = field_map.get(key.lower())
            if db_key:
                try:
                    data[db_key] = float(val)
                except ValueError:
                    pass

    if not data:
        await update.message.reply_text("Couldn't parse that. Try: `/measurements waist:72 hips:96`", parse_mode="Markdown")
        return

    log_measurements(update.effective_user.id, data)

    # Compare with previous
    history = get_measurement_history(update.effective_user.id, limit=2)
    reply = "📏 *Measurements logged!*\n\n"
    for key, val in data.items():
        label = key.replace("_cm", "").replace("_", " ").title()
        reply += f"• {label}: {val}cm\n"

    if len(history) >= 2:
        prev = history[1]
        reply += "\n*Changes from last time:*\n"
        for key, val in data.items():
            if prev.get(key):
                diff = val - prev[key]
                arrow = "📉" if diff < 0 else ("➡️" if diff == 0 else "📈")
                reply += f"{arrow} {key.replace('_cm','').replace('_',' ').title()}: {'+' if diff > 0 else ''}{diff:.1f}cm\n"

    await update.message.reply_text(reply, parse_mode="Markdown")
