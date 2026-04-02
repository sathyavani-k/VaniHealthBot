"""
Fitness benchmark tests: IPPT, ACFT-inspired, general functional fitness.
Heart rate zone calculations and training guidance.
"""

import os
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, MessageHandler, filters
from database.db import get_user, log_fitness_test, get_fitness_history
from google_sheets.sheets import append_fitness_test_to_sheet
from utils.calculations import score_ippt, format_run_time
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

(FT_TYPE, FT_PUSHUPS, FT_SITUPS, FT_RUN, FT_PLANK, FT_HANG, FT_NOTES) = range(7)


def calculate_hr_zones(age):
    """Returns dict of HR zones based on 220-age formula."""
    max_hr = 220 - age
    return {
        "max_hr": max_hr,
        "zone1": (int(max_hr * 0.50), int(max_hr * 0.60)),
        "zone2": (int(max_hr * 0.60), int(max_hr * 0.70)),
        "zone3": (int(max_hr * 0.70), int(max_hr * 0.80)),
        "zone4": (int(max_hr * 0.80), int(max_hr * 0.90)),
        "zone5": (int(max_hr * 0.90), max_hr),
    }


async def hr_zones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    age = user.get("age", 31)
    zones = calculate_hr_zones(age)

    await update.message.reply_text(
        f"❤️ *Your Heart Rate Training Zones*\n"
        f"_(Based on max HR: {zones['max_hr']} bpm, age {age})_\n\n"
        f"🔵 *Zone 1 — Recovery:* {zones['zone1'][0]}–{zones['zone1'][1]} bpm\n"
        f"   Light walks, gentle pilates, cool-downs\n\n"
        f"🟢 *Zone 2 — Fat Burn / Aerobic Base:* {zones['zone2'][0]}–{zones['zone2'][1]} bpm\n"
        f"   Long runs, most of your half marathon training. Where fat burning peaks!\n\n"
        f"🟡 *Zone 3 — Cardio / Aerobic:* {zones['zone3'][0]}–{zones['zone3'][1]} bpm\n"
        f"   Steady-state cardio, moderate Freeletics\n\n"
        f"🟠 *Zone 4 — Threshold:* {zones['zone4'][0]}–{zones['zone4'][1]} bpm\n"
        f"   Tempo runs, hard Freeletics HIIT, interval training\n\n"
        f"🔴 *Zone 5 — Max Effort:* {zones['zone5'][0]}–{zones['zone5'][1]} bpm\n"
        f"   Sprints, final race push. Use sparingly!\n\n"
        f"💡 *Tip:* For your half marathon, aim to keep *80% of your runs in Zone 2*. "
        f"This builds aerobic base, burns fat, and prevents injury.",
        parse_mode="Markdown"
    )


async def fitness_test_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 *Fitness Benchmark Test*\n\n"
        "Let's see where you're at! We'll test:\n"
        "• Push-ups (1 min max)\n"
        "• Sit-ups (1 min max)\n"
        "• 2.4km run time\n"
        "• Plank hold (seconds)\n"
        "• Dead hang (seconds)\n\n"
        "How many push-ups can you do in 1 minute? (Enter a number)",
        parse_mode="Markdown"
    )
    return FT_PUSHUPS


async def ft_pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["ft_pushups"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number.")
        return FT_PUSHUPS
    await update.message.reply_text("💪 Now sit-ups — how many in 1 minute?")
    return FT_SITUPS


async def ft_situps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["ft_situps"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number.")
        return FT_SITUPS
    await update.message.reply_text(
        "🏃‍♀️ What was your 2.4km run time? Enter as M:SS (e.g. 18:30)"
    )
    return FT_RUN


async def ft_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        parts = text.split(":")
        run_sec = int(parts[0]) * 60 + int(parts[1])
        context.user_data["ft_run"] = run_sec
    except Exception:
        await update.message.reply_text("Enter as M:SS (e.g. 18:30)")
        return FT_RUN
    await update.message.reply_text("⏱️ How long can you hold a plank? (seconds, e.g. 45)\nType 0 if you skipped this.")
    return FT_PLANK


async def ft_plank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["ft_plank"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter seconds (e.g. 45)")
        return FT_PLANK
    await update.message.reply_text(
        "🙌 Dead hang time? (how long you can hang from a bar, in seconds)\nType 0 if you skipped."
    )
    return FT_HANG


async def ft_hang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["ft_hang"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter seconds.")
        return FT_HANG

    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Profile not found. Run /start first.")
        return ConversationHandler.END

    pushups = context.user_data.get("ft_pushups", 0)
    situps = context.user_data.get("ft_situps", 0)
    run_sec = context.user_data.get("ft_run", 9999)
    plank = context.user_data.get("ft_plank", 0)
    hang = context.user_data.get("ft_hang", 0)
    age = user.get("age", 31)

    # IPPT scoring
    band = score_ippt(age, pushups, situps, run_sec)

    test_data = {
        "test_type": "IPPT",
        "pushups": pushups,
        "situps": situps,
        "run_2_4km_sec": run_sec,
        "plank_sec": plank,
        "dead_hang_sec": hang,
        "band": band,
    }
    log_fitness_test(update.effective_user.id, test_data)
    append_fitness_test_to_sheet(update.effective_user.id, test_data)

    # Get AI feedback
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": (
                f"Fitness test results for a 31-year-old woman working toward 20% body fat:\n"
                f"• Push-ups: {pushups} (1 min)\n"
                f"• Sit-ups: {situps} (1 min)\n"
                f"• 2.4km run: {format_run_time(run_sec)}\n"
                f"• Plank: {plank}s\n"
                f"• Dead hang: {hang}s\n"
                f"• IPPT Band: {band}\n\n"
                "Give a brief, warm, encouraging 3-sentence assessment. "
                "Highlight 1 strength and 1 area to focus on improving. "
                "Suggest one specific thing to work on first."
            )
        }]
    )

    history = get_fitness_history(update.effective_user.id, limit=2)
    prev_msg = ""
    if len(history) >= 2:
        prev = history[1]
        prev_pushups = prev.get("pushups", 0)
        pu_diff = pushups - prev_pushups
        prev_msg = f"\n\n📈 Push-ups improved by {pu_diff:+d} since last test!" if pu_diff != 0 else ""

    await update.message.reply_text(
        f"🏅 *Fitness Test Results*\n\n"
        f"• Push-ups: {pushups}\n"
        f"• Sit-ups: {situps}\n"
        f"• 2.4km run: {format_run_time(run_sec)}\n"
        f"• Plank: {plank}s\n"
        f"• Dead hang: {hang}s\n\n"
        f"🎖️ *IPPT Band: {band}*\n{prev_msg}\n\n"
        f"💬 *Coach says:*\n{response.content[0].text}\n\n"
        "✅ Results logged and synced to Google Sheets!\n"
        "Test again in 4–6 weeks to track progress. 💪",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def ft_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Test cancelled. Run /fitness_test when you're ready! 💪")
    return ConversationHandler.END


def get_fitness_test_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("fitness_test", fitness_test_start)],
        states={
            FT_PUSHUPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ft_pushups)],
            FT_SITUPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ft_situps)],
            FT_RUN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ft_run)],
            FT_PLANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ft_plank)],
            FT_HANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, ft_hang)],
        },
        fallbacks=[CommandHandler("cancel", ft_cancel)],
    )
