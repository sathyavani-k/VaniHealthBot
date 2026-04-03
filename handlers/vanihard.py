"""
VaniHard Challenge — personalised 75 Hard variant for body recomposition.
Also includes yoga/stretching routines and calisthenics progression.
"""

import os
from datetime import date, datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from database.db import get_user, upsert_user, log_workout, log_water, get_conn
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ─── VaniHard Rules ───────────────────────────────────────────────────────────
VANIHARD_RULES = """
🔥 *VaniHard Challenge — 75 Days*

Your personalised version of 75 Hard, built for body recomposition:

*Daily Non-Negotiables:*
1️⃣ Two workouts (45 min each) — one MUST be outdoors or pilates/yoga
2️⃣ Drink 2.5L water minimum
3️⃣ Follow your calorie + protein targets (no cheat meals, no alcohol)
4️⃣ Read 10 pages of non-fiction (health, mindset, science)
5️⃣ Take a daily progress photo
6️⃣ 10-minute post-meal walk (at least once daily)
7️⃣ Log everything in the bot

*If you miss ONE task, you restart from Day 1.*

The mental toughness IS the point. Every day you complete it, you prove to yourself that you keep promises to yourself. That's the real transformation.
"""

VANIHARD_WORKOUTS = {
    "outdoor": [
        "MacRitchie Reservoir trail run (any distance)",
        "East Coast Park run or cycle",
        "Southern Ridges walk/run",
        "Rail Corridor walk",
        "Outdoor HIIT at nearest park",
        "Bukit Timah hill repeats",
        "Coney Island loop jog",
    ],
    "indoor_1": [
        "Freeletics full-body session",
        "Pilates mat class (45 min)",
        "Calisthenics strength session",
        "Yoga flow (45 min)",
        "HIIT + core circuit",
        "Dumbbell strength session",
        "Barre/Pilates reformer",
    ]
}


def get_vanihard_status(telegram_id):
    """Get current VaniHard status from DB."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM vanihard WHERE telegram_id=?", (telegram_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def init_vanihard_table():
    """Create VaniHard table if not exists."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vanihard (
            telegram_id     INTEGER PRIMARY KEY,
            start_date      TEXT,
            current_day     INTEGER DEFAULT 0,
            active          INTEGER DEFAULT 0,
            last_completed  TEXT,
            total_restarts  INTEGER DEFAULT 0,
            best_streak     INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vanihard_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER,
            day_number      INTEGER,
            log_date        TEXT,
            workout1_done   INTEGER DEFAULT 0,
            workout2_done   INTEGER DEFAULT 0,
            water_done      INTEGER DEFAULT 0,
            diet_done       INTEGER DEFAULT 0,
            reading_done    INTEGER DEFAULT 0,
            photo_done      INTEGER DEFAULT 0,
            walk_done       INTEGER DEFAULT 0,
            notes           TEXT,
            completed       INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


async def vanihard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start or show VaniHard challenge status."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    init_vanihard_table()
    status = get_vanihard_status(update.effective_user.id)

    if not status or not status.get("active"):
        await update.message.reply_text(
            f"{VANIHARD_RULES}\n\n"
            "Ready to start? Type `/vanihard begin` to kick off Day 1!\n\n"
            "⚠️ This is serious. Only start when you're committed. "
            "Miss one task = restart from Day 1.",
            parse_mode="Markdown"
        )
        return

    day = status["current_day"]
    best = status["best_streak"]
    restarts = status["total_restarts"]

    await update.message.reply_text(
        f"🔥 *VaniHard Status*\n\n"
        f"📅 Current Day: *{day} / 75*\n"
        f"🏆 Best streak: {best} days\n"
        f"🔄 Restarts: {restarts}\n\n"
        f"{'🎉 You completed the challenge!!! 🎉' if day >= 75 else ''}"
        f"Use `/vanihard log` to check off today's tasks.\n"
        f"Use `/vanihard today` to see your daily checklist.",
        parse_mode="Markdown"
    )


async def vanihard_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin or restart the VaniHard challenge."""
    args = context.args
    if not args or args[0] != "begin":
        await vanihard_start(update, context)
        return

    init_vanihard_table()
    today = str(date.today())
    conn = get_conn()
    conn.execute("""
        INSERT INTO vanihard (telegram_id, start_date, current_day, active, last_completed, total_restarts, best_streak)
        VALUES (?, ?, 1, 1, ?, 0, 0)
        ON CONFLICT(telegram_id) DO UPDATE SET
            start_date=excluded.start_date,
            current_day=1,
            active=1,
            last_completed=excluded.last_completed,
            total_restarts=total_restarts+1
    """, (update.effective_user.id, today, today))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🔥 *VaniHard — Day 1 BEGINS!* 🔥\n\n"
        f"Today's mission:\n"
        f"✅ Workout 1: {VANIHARD_WORKOUTS['indoor_1'][0]}\n"
        f"✅ Workout 2 (outdoor): {VANIHARD_WORKOUTS['outdoor'][0]}\n"
        f"✅ 2.5L water\n"
        f"✅ Hit your calorie + protein targets\n"
        f"✅ Read 10 pages\n"
        f"✅ Daily progress photo\n"
        f"✅ Post-meal walk (10 min)\n\n"
        "Use `/vanihard log` at end of day to check off your tasks.\n\n"
        "_75 days from now, you will not recognise yourself._ 💪",
        parse_mode="Markdown"
    )


async def vanihard_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's VaniHard checklist with workout suggestions."""
    user = get_user(update.effective_user.id)
    init_vanihard_table()
    status = get_vanihard_status(update.effective_user.id)

    if not status or not status.get("active"):
        await update.message.reply_text("Start your challenge first with `/vanihard begin`", parse_mode="Markdown")
        return

    day = status["current_day"]
    # Rotate workout suggestions based on day
    outdoor = VANIHARD_WORKOUTS["outdoor"][day % len(VANIHARD_WORKOUTS["outdoor"])]
    indoor = VANIHARD_WORKOUTS["indoor_1"][day % len(VANIHARD_WORKOUTS["indoor_1"])]

    await update.message.reply_text(
        f"🔥 *VaniHard — Day {day}*\n\n"
        f"*Today's suggested workouts:*\n"
        f"💪 Session 1: {indoor}\n"
        f"🌳 Session 2 (outdoor): {outdoor}\n\n"
        f"*Daily checklist:*\n"
        f"☐ Workout 1 (45 min indoor)\n"
        f"☐ Workout 2 (45 min outdoor)\n"
        f"☐ 2.5L water\n"
        f"☐ On-target nutrition (no alcohol, no cheat meals)\n"
        f"☐ Read 10 pages\n"
        f"☐ Progress photo\n"
        f"☐ Post-meal walk (10 min)\n\n"
        "Check off at end of day: `/vanihard log w1 w2 water diet reading photo walk`",
        parse_mode="Markdown"
    )


async def vanihard_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log completed VaniHard tasks for today."""
    init_vanihard_table()
    status = get_vanihard_status(update.effective_user.id)

    if not status or not status.get("active"):
        await update.message.reply_text("Start your challenge first with `/vanihard begin`", parse_mode="Markdown")
        return

    args = set(a.lower() for a in (context.args or []))
    today = str(date.today())

    tasks = {
        "workout1": any(k in args for k in ["w1", "workout1", "wk1"]),
        "workout2": any(k in args for k in ["w2", "workout2", "wk2"]),
        "water": "water" in args,
        "diet": "diet" in args,
        "reading": any(k in args for k in ["reading", "read"]),
        "photo": "photo" in args,
        "walk": "walk" in args,
    }

    all_done = all(tasks.values())
    day = status["current_day"]

    conn = get_conn()
    if all_done:
        new_day = day + 1
        best = max(status["best_streak"], new_day)
        conn.execute(
            "UPDATE vanihard SET current_day=?, last_completed=?, best_streak=?, active=? WHERE telegram_id=?",
            (new_day, today, best, 1 if new_day <= 75 else 0, update.effective_user.id)
        )
        msg = (
            f"🔥 *Day {day} COMPLETE!* 🔥\n\n"
            f"Every task done. You showed up for yourself today.\n\n"
            f"{'🎉 75 DAYS COMPLETE — YOU DID IT!!!' if new_day > 75 else f'Day {new_day} tomorrow. Keep going! 💪'}"
        )
    else:
        missing = [k for k, v in tasks.items() if not v]
        msg = (
            f"⚠️ *Day {day} incomplete.*\n\n"
            f"Missing: {', '.join(missing)}\n\n"
            "Complete ALL tasks to advance. Otherwise, tomorrow is Day 1 again.\n"
            "You still have time today — go finish it! 💪"
        )
    conn.commit()
    conn.close()

    await update.message.reply_text(msg, parse_mode="Markdown")


# ─── Yoga & Stretching ────────────────────────────────────────────────────────

async def yoga_routine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a yoga or stretching routine."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    args = context.args
    routine_type = args[0].lower() if args else "general"

    type_prompts = {
        "morning": "energising morning yoga flow (15–20 min) to wake up the body",
        "recovery": "deep recovery yoga and stretching (30 min) after intense Freeletics or running",
        "pilates": "pilates-inspired yoga fusion targeting core, hips, and posture",
        "evening": "calming evening yoga and breathwork for sleep quality and recovery",
        "flexibility": "flexibility and mobility routine targeting hips, hamstrings, shoulders for running",
        "general": "balanced yoga flow (30 min) combining strength, flexibility, and mindfulness",
    }

    prompt_desc = type_prompts.get(routine_type, type_prompts["general"])

    await update.message.reply_text(f"🧘‍♀️ Generating your {routine_type} yoga routine...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": (
                f"Create a {prompt_desc} for a 31-year-old Singapore-based woman who does Freeletics, Pilates, and is training for a half marathon.\n\n"
                "Include:\n"
                "• Each pose/stretch with duration (seconds or breaths)\n"
                "• Clear cues for correct form\n"
                "• Modifications for tight hips/hamstrings (common for runners)\n"
                "• Breathwork cues\n"
                "• Flow in logical order (warm → peak → cool)\n\n"
                "Format clearly with timing so it's easy to follow in real-time."
            )
        }]
    )

    await update.message.reply_text(
        f"🧘‍♀️ *{routine_type.capitalize()} Yoga Routine*\n\n{response.content[0].text}\n\n"
        "💡 Yoga types available:\n"
        "`/yoga morning` | `/yoga recovery` | `/yoga pilates` | `/yoga evening` | `/yoga flexibility`",
        parse_mode="Markdown"
    )


# ─── Calisthenics ─────────────────────────────────────────────────────────────

CALISTHENICS_PROGRESSIONS = {
    "push": ["Knee Push-ups", "Standard Push-ups", "Diamond Push-ups", "Decline Push-ups",
             "Archer Push-ups", "Pike Push-ups", "Pseudo Planche Push-ups"],
    "pull": ["Dead Hang", "Scapular Pulls", "Negative Pull-ups", "Assisted Pull-ups",
             "Pull-ups", "Chin-ups", "Commando Pull-ups"],
    "legs": ["Assisted Squat", "Bodyweight Squat", "Bulgarian Split Squat",
             "Pistol Squat Progression", "Pistol Squat", "Shrimp Squat"],
    "core": ["Dead Bug", "Plank", "Hollow Body Hold", "L-Sit Tuck", "L-Sit",
             "Dragon Flag Negatives", "Dragon Flag"],
    "skills": ["Crow Pose", "Handstand Wall Hold", "Freestanding Handstand",
               "Human Flag Progression", "Front Lever Tuck"],
}


async def calisthenics_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a calisthenics workout or progression plan."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    args = context.args
    focus = args[0].lower() if args else "full"

    await update.message.reply_text("🤸‍♀️ Building your calisthenics session...")

    progressions_info = "\n".join([f"- {k}: {' → '.join(v)}" for k, v in CALISTHENICS_PROGRESSIONS.items()])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{
            "role": "user",
            "content": (
                f"Create a calisthenics workout for a 31-year-old woman. Focus: {focus}.\n"
                f"Her goal is body recomposition (20% BF), lean toned physique.\n"
                f"She also does Freeletics, Pilates, and is training for a half marathon.\n\n"
                f"Progression framework to draw from:\n{progressions_info}\n\n"
                f"Create a structured session with:\n"
                f"• Warm-up (5 min)\n"
                f"• Skill/strength work (sets × reps or time)\n"
                f"• Supersets or circuits for efficiency\n"
                f"• Cool-down (5 min)\n\n"
                f"Include progressions (easier → harder variations) so she can scale.\n"
                f"Note: this should complement her Freeletics, not duplicate it.\n"
                f"Duration: ~45 minutes."
            )
        }]
    )

    await update.message.reply_text(
        f"🤸‍♀️ *Calisthenics Session — {focus.capitalize()}*\n\n{response.content[0].text}\n\n"
        "Focus options: `/calisthenics push` | `/calisthenics pull` | `/calisthenics core` | `/calisthenics skills` | `/calisthenics full`",
        parse_mode="Markdown"
    )


async def calisthenics_progressions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show skill progression ladders."""
    lines = ["🤸‍♀️ *Calisthenics Skill Progressions*\n"]
    labels = {
        "push": "💪 Push Strength",
        "pull": "🙌 Pull Strength",
        "legs": "🦵 Leg Strength",
        "core": "🎯 Core",
        "skills": "⭐ Skills",
    }
    for key, moves in CALISTHENICS_PROGRESSIONS.items():
        lines.append(f"*{labels[key]}:*")
        lines.append(" → ".join(moves))
        lines.append("")

    lines.append("Start where you are. Master each step before moving up.\nUse `/calisthenics [focus]` for a full session!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
