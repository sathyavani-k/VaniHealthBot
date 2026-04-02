"""
Water intake tracking, menstrual cycle tracking, stress/sleep logging,
and streak/habit tracking handlers.
"""

import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from database.db import (
    log_water, get_today_water, get_user, upsert_user,
    get_streaks, update_streak, log_workout
)
from utils.calculations import get_cycle_phase, cycle_phase_advice, progress_bar
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DAILY_WATER_TARGET_ML = 2500  # ~2.5L, good for active woman in Singapore


async def log_water_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    args = context.args
    if not args:
        today_total = get_today_water(update.effective_user.id)
        await update.message.reply_text(
            f"💧 Today's water: {today_total:.0f}ml / {DAILY_WATER_TARGET_ML}ml\n"
            f"{progress_bar(today_total, DAILY_WATER_TARGET_ML)}\n\n"
            "Log with: `/water 500` (in ml) or `/water 2` (in glasses = 250ml each)",
            parse_mode="Markdown"
        )
        return

    try:
        amount = float(args[0])
        # If number is small, assume glasses
        if amount <= 20:
            amount_ml = amount * 250
        else:
            amount_ml = amount
    except ValueError:
        await update.message.reply_text("Usage: `/water 500` (ml) or `/water 2` (glasses)", parse_mode="Markdown")
        return

    log_water(update.effective_user.id, amount_ml)
    update_streak(update.effective_user.id, "water")
    today_total = get_today_water(update.effective_user.id)

    status = "✅ Hydration goal hit!" if today_total >= DAILY_WATER_TARGET_ML else f"Need {DAILY_WATER_TARGET_ML - today_total:.0f}ml more"

    await update.message.reply_text(
        f"💧 +{amount_ml:.0f}ml logged!\n\n"
        f"Today's total: {today_total:.0f} / {DAILY_WATER_TARGET_ML}ml\n"
        f"{progress_bar(today_total, DAILY_WATER_TARGET_ML)} {int((today_total/DAILY_WATER_TARGET_ML)*100)}%\n"
        f"{status}\n\n"
        f"💡 *Singapore tip:* In our heat + humidity, you need 2.5–3L daily, "
        f"more on workout days. Dehydration tanks fat loss and performance!",
        parse_mode="Markdown"
    )


async def log_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log menstrual cycle start date."""
    args = context.args
    if not args:
        user = get_user(update.effective_user.id)
        if user and user.get("cycle_start_date"):
            phase, day = get_cycle_phase(user["cycle_start_date"], user.get("cycle_length", 28))
            advice = cycle_phase_advice(phase) if phase else {}
            await update.message.reply_text(
                f"🌸 *Cycle Status*\n\n"
                f"Current phase: *{phase.capitalize() if phase else 'Unknown'}* (Day {day})\n\n"
                f"💪 Workout: {advice.get('workout', '')}\n\n"
                f"🥗 Nutrition: {advice.get('nutrition', '')}\n\n"
                f"⚡ Energy: {advice.get('energy', '')}\n\n"
                "Update period start: `/cycle YYYY-MM-DD`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "Log your period start date: `/cycle 2025-04-01`\n\n"
                "This helps me tailor your workouts and nutrition to your cycle phases! 🌸",
                parse_mode="Markdown"
            )
        return

    date_str = args[0]
    cycle_length = int(args[1]) if len(args) > 1 else 28

    upsert_user({
        "telegram_id": update.effective_user.id,
        "cycle_start_date": date_str,
        "cycle_length": cycle_length,
    })

    phase, day = get_cycle_phase(date_str, cycle_length)
    advice = cycle_phase_advice(phase) if phase else {}

    await update.message.reply_text(
        f"🌸 *Cycle logged!*\n\n"
        f"Current phase: *{phase.capitalize() if phase else 'Unknown'}* (Day {day})\n\n"
        f"💪 {advice.get('workout', '')}\n\n"
        f"🥗 {advice.get('nutrition', '')}\n\n"
        f"Your workout and meal plans will now adapt to your cycle! 🌸",
        parse_mode="Markdown"
    )


async def log_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log sleep hours and get a recovery insight."""
    args = context.args
    if not args:
        await update.message.reply_text("Log your sleep: `/sleep 7.5` (hours)", parse_mode="Markdown")
        return

    try:
        hours = float(args[0])
    except ValueError:
        await update.message.reply_text("Usage: `/sleep 7.5`", parse_mode="Markdown")
        return

    if hours < 6:
        msg = (
            f"😴 *{hours}h logged* — that's below optimal.\n\n"
            "⚠️ Poor sleep increases cortisol (stress hormone), which directly causes fat retention "
            "especially around the belly. It also kills workout performance and muscle recovery.\n\n"
            "Tonight: try to get to bed 30 min earlier. No screens 1h before bed. "
            "Magnesium glycinate before sleep can help significantly!"
        )
    elif hours < 7:
        msg = (
            f"😴 *{hours}h logged* — decent, but aim for 7.5–9h for optimal body recomposition.\n\n"
            "Sleep is when your body actually builds muscle and burns fat. Don't shortchange it! 💤"
        )
    else:
        msg = (
            f"😴 *{hours}h — great sleep!* 🌟\n\n"
            "Quality sleep = lower cortisol, better insulin sensitivity, stronger workouts, and faster fat loss. "
            "This is one of your most powerful fat loss tools. Keep it up! 🌙"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def log_stress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log stress level and get personalised advice."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Log your stress level: `/stress 3` (scale 1–5)\n1 = zen calm | 5 = overwhelmed",
            parse_mode="Markdown"
        )
        return

    try:
        level = int(args[0])
        if not 1 <= level <= 5:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Enter a number 1–5.")
        return

    if level >= 4:
        msg = (
            f"😣 *Stress level {level}/5 logged.*\n\n"
            "High stress = high cortisol = your body holds onto fat, especially visceral fat around the belly. "
            "With your family history of heart disease and diabetes, managing stress is as important as your workouts.\n\n"
            "Today's prescription:\n"
            "• Lighter workout or Pilates/yoga instead of HIIT\n"
            "• Don't restrict calories on high-stress days — eat at maintenance\n"
            "• Try 5 minutes of box breathing (4-4-4-4)\n"
            "• Walk outside, even 20 minutes\n\n"
            "You've got this. Recovery is part of the plan. 🌸"
        )
    elif level == 3:
        msg = (
            f"😐 *Stress level {level}/5 logged.*\n\n"
            "Manageable — but keep an eye on it. "
            "Moderate stress can be channelled into a good workout! "
            "Freeletics HIIT releases endorphins and burns off cortisol effectively today. 💪"
        )
    else:
        msg = (
            f"😊 *Stress level {level}/5 logged — you're in a great headspace!*\n\n"
            "Low cortisol + good energy = optimal fat burning. "
            "This is a great day for a challenging workout or your long run! 🏃‍♀️"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def streaks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all current streaks."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    streaks = get_streaks(update.effective_user.id)

    def streak_emoji(n):
        if n >= 30: return "🏆"
        if n >= 14: return "🔥"
        if n >= 7: return "⭐"
        if n >= 3: return "✅"
        return "🌱"

    wo = streaks.get("workout_streak", 0)
    lg = streaks.get("logging_streak", 0)
    wa = streaks.get("water_streak", 0)

    await update.message.reply_text(
        f"🔥 *Your Streak Board*\n\n"
        f"{streak_emoji(wo)} Workout streak: *{wo} days*\n"
        f"{streak_emoji(lg)} Meal logging streak: *{lg} days*\n"
        f"{streak_emoji(wa)} Hydration streak: *{wa} days*\n\n"
        + ("🏆 You're on fire! Keep it going!" if max(wo, lg, wa) >= 7 else
           "🌱 Every streak starts with day 1. Log today to get started!"),
        parse_mode="Markdown"
    )


async def log_workout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log a completed workout."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Log your workout:\n"
            "`/log_workout Freeletics 45 4` (name, duration mins, intensity 1-5)\n"
            "`/log_workout 'Long run 12km' 75 3`",
            parse_mode="Markdown"
        )
        return

    name = args[0] if args else "Workout"
    duration = int(args[1]) if len(args) > 1 else 45
    intensity = int(args[2]) if len(args) > 2 else 3
    notes = " ".join(args[3:]) if len(args) > 3 else ""

    log_workout(update.effective_user.id, name, duration, intensity, notes)

    intensity_labels = {1: "Easy", 2: "Light", 3: "Moderate", 4: "Hard", 5: "Max effort"}
    intensity_label = intensity_labels.get(intensity, "Moderate")

    await update.message.reply_text(
        f"🏋️ *Workout logged!*\n\n"
        f"• Session: {name}\n"
        f"• Duration: {duration} min\n"
        f"• Intensity: {intensity_label} ({intensity}/5)\n\n"
        "💪 Another step toward 20%! Streak updated. 🔥\n\n"
        "Don't forget to log your meals and hydration too!",
        parse_mode="Markdown"
    )
