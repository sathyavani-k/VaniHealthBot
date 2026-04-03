"""
AI Coach — handles all free-form messages as a knowledgeable, warm fitness coach.
Also handles: weekly check-ins, weekly reports, plateau detection, macro cycling,
supplement tracking, mindset tips, and refeed days.
"""

import os
from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database.db import (
    get_user, get_today_meals, get_meal_history, get_scan_history,
    get_weight_history, get_checkin_history, log_checkin, log_victory,
    get_streaks, get_supplements, add_supplement, get_recent_victories,
    get_fitness_history
)
from utils.calculations import get_cycle_phase, cycle_phase_advice, macro_cycle_targets, progress_bar
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are VaniHealthBot — a warm, knowledgeable, science-backed personal health and fitness coach.

Your client is Vani (born 1 March 1995, age 31), a Singapore-based woman with the goal of reaching 20% body fat
with a lean, toned "pilates princess" physique. She uses Freeletics for workouts, does Pilates, and is training
for a half marathon.

Your coaching style:
- Warm, encouraging, and direct
- Evidence-based (cite science when relevant, but keep it accessible)
- Practical for Singapore lifestyle (Singapore food, weather, race calendar)
- Knowledgeable about body recomposition, not just weight loss
- Understand that fat loss ≠ muscle loss — protect muscle at all costs
- Menstrual cycle-aware (adapt recommendations to her cycle phase when known)
- Heart rate zone-aware (her max HR is ~189 bpm, age 31)

Key facts about Vani:
- Goal: 20% body fat (lean recomposition)
- Training: Freeletics HIIT + Pilates + Running
- Location: Singapore
- Goal race: Half marathon (Great Eastern Women's Run or Standard Chartered)
- Tools: PICOOC smart scale, tracks in Telegram

Always be concise, warm, and actionable. Never be preachy. Celebrate wins big and small."""


async def ai_coach_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any free-form text message as a coaching query."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(
            "Welcome! Please run /start first to set up your profile and unlock all features 🌸"
        )
        return

    user_message = update.message.text

    # Build context from user's recent data
    scans = get_scan_history(update.effective_user.id, limit=1)
    weights = get_weight_history(update.effective_user.id, limit=1)
    today_meals = get_today_meals(update.effective_user.id)
    streaks = get_streaks(update.effective_user.id)

    context_info = f"\nUser profile: age {user.get('age')}, {user.get('weight_kg')}kg, {user.get('body_fat_pct')}% BF, goal {user.get('goal_bf_pct')}% BF"
    if scans:
        s = scans[0]
        context_info += f"\nLatest scan: {s.get('body_fat_pct')}% BF, {s.get('muscle_mass_kg')}kg muscle"
    if today_meals:
        total_cal = sum(m["calories"] for m in today_meals)
        context_info += f"\nToday's intake so far: {total_cal:.0f} kcal"

    cycle_info = ""
    if user.get("cycle_start_date"):
        phase, day = get_cycle_phase(user["cycle_start_date"], user.get("cycle_length", 28))
        if phase:
            cycle_info = f"\nCurrent cycle phase: {phase} (day {day})"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=SYSTEM_PROMPT + context_info + cycle_info,
        messages=[{"role": "user", "content": user_message}]
    )

    await update.message.reply_text(response.content[0].text, parse_mode="Markdown")


async def weekly_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guided weekly check-in."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    # Get recent data for context
    scans = get_scan_history(update.effective_user.id, limit=2)
    history = get_meal_history(update.effective_user.id, days=7)
    avg_cal = sum(d["total_cal"] for d in history) / len(history) if history else 0

    # Plateau detection
    plateau_warning = ""
    if len(scans) >= 2:
        bf1 = scans[0].get("body_fat_pct")
        bf2 = scans[1].get("body_fat_pct")
        if bf1 and bf2 and abs(bf1 - bf2) < 0.3:
            plateau_warning = "\n\n⚠️ *Plateau Alert:* Your body fat hasn't changed much. I'll give you some strategies!"

    context.user_data["checkin_mode"] = True
    await update.message.reply_text(
        f"📋 *Weekly Check-in Time!* 🌸\n\n"
        f"This week's snapshot:\n"
        f"• Avg calories: {avg_cal:.0f} kcal/day\n"
        f"{plateau_warning}\n\n"
        "Let's do this! First: what's your current weight? (kg)",
        parse_mode="Markdown"
    )
    return "CHECKIN_WEIGHT"


async def weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a comprehensive weekly progress report."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    await update.message.reply_text("📊 Generating your weekly report...")

    history = get_meal_history(update.effective_user.id, days=7)
    scans = get_scan_history(update.effective_user.id, limit=2)
    weights = get_weight_history(update.effective_user.id, limit=7)
    checkins = get_checkin_history(update.effective_user.id, limit=4)
    streaks = get_streaks(update.effective_user.id)
    victories = get_recent_victories(update.effective_user.id, limit=3)
    fitness_tests = get_fitness_history(update.effective_user.id, limit=1)

    # Calculate averages
    avg_cal = sum(d["total_cal"] for d in history) / len(history) if history else 0
    avg_protein = sum(d["total_protein"] for d in history) / len(history) if history else 0
    days_logged = len(history)

    # Build report
    report = f"📊 *Weekly Report — {date.today().strftime('%d %b %Y')}*\n\n"

    # Nutrition
    report += f"🍽️ *Nutrition ({days_logged}/7 days logged):*\n"
    report += f"• Avg calories: {avg_cal:.0f} / {user['calorie_target']:.0f} kcal\n"
    report += f"• Avg protein: {avg_protein:.0f} / {user['protein_g']:.0f}g\n"
    cal_adherence = int((avg_cal / user['calorie_target']) * 100) if user['calorie_target'] else 0
    report += f"• Target adherence: {cal_adherence}%\n\n"

    # Body composition
    if scans:
        s = scans[0]
        report += f"📏 *Body Composition:*\n"
        report += f"• Body fat: {s.get('body_fat_pct', 'N/A')}% (goal: {user.get('goal_bf_pct', 20)}%)\n"
        report += f"• Muscle mass: {s.get('muscle_mass_kg', 'N/A')}kg\n"
        if len(scans) >= 2:
            prev_bf = scans[1].get("body_fat_pct")
            curr_bf = s.get("body_fat_pct")
            if prev_bf and curr_bf:
                diff = curr_bf - prev_bf
                arrow = "📉" if diff < 0 else "📈"
                report += f"• Change: {arrow} {diff:+.1f}%\n"
        report += "\n"

    # Streaks
    report += f"🔥 *Streaks:*\n"
    report += f"• Workout streak: {streaks.get('workout_streak', 0)} days\n"
    report += f"• Meal logging streak: {streaks.get('logging_streak', 0)} days\n\n"

    # Victories
    if victories:
        report += f"🏆 *Recent Wins:*\n"
        for v in victories:
            report += f"• {v['victory']}\n"
        report += "\n"

    # Plateau check
    if len(scans) >= 2:
        bf1 = scans[0].get("body_fat_pct")
        bf2 = scans[1].get("body_fat_pct")
        if bf1 and bf2 and abs(bf1 - bf2) < 0.3:
            report += "⚠️ *Plateau Detected!* Strategies:\n"
            report += "• Try macro cycling (higher carbs on workout days)\n"
            report += "• Add a refeed day this week\n"
            report += "• Change your workout split\n"
            report += "• Check sleep and stress levels\n\n"

    # AI weekly summary
    ai_response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Weekly check-in summary for Vani:\n"
                f"- Avg calories: {avg_cal:.0f} kcal (target: {user['calorie_target']:.0f})\n"
                f"- Avg protein: {avg_protein:.0f}g\n"
                f"- Days logged: {days_logged}/7\n"
                f"- Current BF: {scans[0].get('body_fat_pct', 'unknown') if scans else 'unknown'}%\n\n"
                "Give a 2-3 sentence encouraging weekly summary with one specific focus for next week."
            )
        }]
    )

    report += f"💬 *Your Coach Says:*\n{ai_response.content[0].text}"

    await update.message.reply_text(report, parse_mode="Markdown")


async def macro_cycle_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain and show macro cycling targets."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    tdee = user.get("tdee", 1800)
    wk_cal, wk_p, wk_c, wk_f = macro_cycle_targets(tdee, is_workout_day=True)
    rest_cal, rest_p, rest_c, rest_f = macro_cycle_targets(tdee, is_workout_day=False)

    await update.message.reply_text(
        f"🔄 *Macro Cycling Guide*\n\n"
        f"Macro cycling means eating more on workout days and less on rest days. "
        f"This optimises fat burning AND muscle building. Science-backed for body recomposition!\n\n"
        f"💪 *Workout Day Targets:*\n"
        f"• Calories: {wk_cal:.0f} kcal\n"
        f"• Protein: {wk_p:.0f}g | Carbs: {wk_c:.0f}g | Fat: {wk_f:.0f}g\n\n"
        f"😴 *Rest Day Targets:*\n"
        f"• Calories: {rest_cal:.0f} kcal\n"
        f"• Protein: {rest_p:.0f}g | Carbs: {rest_c:.0f}g | Fat: {rest_f:.0f}g\n\n"
        f"💡 *Tips:*\n"
        f"• Eat your carbs around your workout (before + after)\n"
        f"• Keep protein high every day\n"
        f"• On rest days, fill calories with healthy fats and veggies",
        parse_mode="Markdown"
    )


async def supplements_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show supplement recommendations and let user track theirs."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    user_supps = get_supplements(update.effective_user.id)

    await update.message.reply_text(
        f"💊 *Supplement Guide for Body Recomposition*\n\n"
        f"*Essential (backed by strong evidence):*\n"
        f"• Creatine monohydrate — 5g/day. Best supplement for strength + muscle. Safe for women!\n"
        f"• Protein powder — top up if you're struggling to hit {user.get('protein_g', 120):.0f}g/day\n"
        f"• Vitamin D3 — especially important in Singapore if you're mostly indoors\n\n"
        f"*Highly recommended:*\n"
        f"• Magnesium glycinate — better sleep, reduces PMS symptoms, muscle recovery\n"
        f"• Omega-3 (fish oil) — reduces inflammation, supports fat loss\n"
        f"• Iron — especially important if your periods are heavy\n\n"
        f"*Nice to have:*\n"
        f"• Collagen peptides — joint health, skin (especially with Pilates)\n"
        f"• Zinc — immune function and hormonal health\n\n"
        + (f"*Your tracked supplements:*\n" + "\n".join([f"• {s['name']} — {s['dose']}" for s in user_supps]) if user_supps else "") +
        f"\n\nAdd a supplement: `/add_supplement Creatine 5g`",
        parse_mode="Markdown"
    )


async def add_supplement_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/add_supplement Creatine 5g`", parse_mode="Markdown")
        return

    name = args[0]
    dose = " ".join(args[1:])
    add_supplement(update.effective_user.id, name, dose)
    await update.message.reply_text(f"✅ Added *{name} {dose}* to your supplement tracker!", parse_mode="Markdown")


async def refeed_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain and plan a refeed day."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    tdee = user.get("tdee", 1800)
    refeed_cal = int(tdee * 1.0)  # eat at maintenance on refeed

    await update.message.reply_text(
        f"🍚 *Refeed Day Guide*\n\n"
        f"A refeed is a planned day of eating at maintenance calories — *not* a cheat day!\n\n"
        f"*Why refeed?*\n"
        f"When you're in a deficit, leptin (your hunger hormone) drops. A refeed day resets it, "
        f"which actually helps fat loss continue. It also replenishes muscle glycogen so you perform "
        f"better in workouts afterward.\n\n"
        f"*Your refeed targets:*\n"
        f"• Calories: {refeed_cal:.0f} kcal (your maintenance)\n"
        f"• Keep protein high: {user.get('protein_g', 120):.0f}g+\n"
        f"• Increase carbs (rice, pasta, sweet potato, oats)\n"
        f"• Keep fat moderate\n\n"
        f"*When to refeed:*\n"
        f"• Every 2 weeks, or when energy crashes and cravings are intense\n"
        f"• Best on a heavy workout day (your body will use the carbs!)\n"
        f"• During your follicular phase (post-period) for best results\n\n"
        f"💡 This is not a diet break — it's a strategic tool. Enjoy it guilt-free! 🌸",
        parse_mode="Markdown"
    )


async def mindset_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deliver a science-backed mindset or motivation tip."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": "Give me one short, powerful, science-backed mindset tip for body recomposition and fat loss. Make it specific, warm, and actionable. Max 3 sentences."
        }]
    )
    await update.message.reply_text(
        f"💭 *Today's Mindset Tip*\n\n{response.content[0].text}",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌸 *VaniHealthBot — Command Guide*\n\n"
        "*📊 Tracking:*\n"
        "/log_meal [description] — log a meal\n"
        "/daily_summary — today's calories & macros\n"
        "/history — last 7 days\n"
        "/log_weight [kg] — log weight\n"
        "/measurements — log body measurements\n"
        "/progress — see your progress\n"
        "/log_workout [name] [mins] [1-5] — log a workout\n\n"
        "*📸 Photo Logging:*\n"
        "Send a food photo → auto calorie estimate + log\n"
        "Send PICOOC scan (caption: 'scan') → auto OCR + log\n\n"
        "*🗓️ Planning:*\n"
        "/meal_plan — 7-day meal plan\n"
        "/meal_prep — prep guide + shopping list\n"
        "/workout_plan — weekly Freeletics + Pilates plan\n"
        "/running_plan [date] — half marathon plan\n"
        "/update_equipment — change equipment/duration\n"
        "/eating_out [place] — healthy menu picks\n\n"
        "*🏅 Fitness:*\n"
        "/fitness_test — IPPT + functional benchmark\n"
        "/hr_zones — your heart rate training zones\n"
        "/side_quests — fitness mini-goals\n"
        "/victory [win] — log a non-scale victory\n\n"
        "*🔬 Smart Features:*\n"
        "/macro_cycle — workout vs rest day targets\n"
        "/refeed — plan a refeed day\n"
        "/supplements — supplement guide + tracker\n"
        "/add_supplement [name] [dose]\n"
        "/weekly_report — full weekly summary\n"
        "/checkin — weekly check-in\n"
        "/mindset — science-backed tip\n"
        "/sg_activities — Singapore fitness guide\n\n"
        "*💬 Just chat with me anytime!* I'm your AI coach 🌸",
        parse_mode="Markdown"
    )
