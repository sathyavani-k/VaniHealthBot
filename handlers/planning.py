"""
Meal planning, workout planning (Freeletics-style), meal prep, shopping list,
running/half-marathon plan, and side quest handlers.
"""

import os
from datetime import datetime, date, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from database.db import get_user, log_victory
from utils.calculations import get_cycle_phase, cycle_phase_advice
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

FREELETICS_EXERCISES = {
    "bodyweight": [
        "Burpees", "Jump Squats", "Push-ups", "Mountain Climbers", "High Knees",
        "Jumping Lunges", "Plank Hold", "Sit-ups", "Pike Push-ups",
        "Bear Crawls", "Leg Raises", "Flutter Kicks", "Broad Jumps",
    ],
    "dumbbells": [
        "Dumbbell Romanian Deadlift", "Goblet Squat", "Dumbbell Row",
        "Dumbbell Shoulder Press", "Dumbbell Lunges", "Dumbbell Curl",
        "Dumbbell Tricep Extension", "Renegade Rows",
    ],
    "full_gym": [
        "Barbell Squat", "Deadlift", "Bench Press", "Pull-ups/Assisted Pull-ups",
        "Cable Row", "Hip Thrust", "Leg Press", "Lat Pulldown",
    ],
    "pilates": [
        "Hundreds", "Roll Up", "Single Leg Circles", "Rolling Like a Ball",
        "Single Leg Stretch", "Double Leg Stretch", "Spine Stretch",
        "Swan", "Child's Pose", "Side-lying Leg Series", "Teaser",
        "Plank to Pike", "Mermaid Stretch",
    ]
}


async def meal_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    await update.message.reply_text("🥗 Creating your personalised weekly meal plan... (this takes ~20 seconds)")

    phase_info = ""
    if user.get("cycle_start_date"):
        phase, day = get_cycle_phase(user["cycle_start_date"], user.get("cycle_length", 28))
        if phase:
            advice = cycle_phase_advice(phase)
            phase_info = f"\nNote: User is currently in {phase} phase (day {day}). {advice.get('nutrition', '')}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                f"Create a 7-day personalised meal plan for a woman with these targets:\n"
                f"• Daily calories: {user['calorie_target']:.0f} kcal\n"
                f"• Protein: {user['protein_g']:.0f}g | Carbs: {user['carbs_g']:.0f}g | Fat: {user['fat_g']:.0f}g\n"
                f"• Goal: body recomposition to 20% body fat — lean, toned physique\n"
                f"• Based in Singapore (include local foods like chicken rice variations, laksa lighter version, etc.){phase_info}\n\n"
                "Format each day as:\n"
                "**Day X:**\n"
                "• Breakfast: [meal] (~Xcal, Xg protein)\n"
                "• Lunch: [meal]\n"
                "• Dinner: [meal]\n"
                "• Snacks: [options]\n\n"
                "Focus on: high protein, whole foods, practical to prep in Singapore. "
                "Include some meal prep-friendly options that can be batch cooked."
            )
        }]
    )

    await update.message.reply_text(
        f"🥗 *Your 7-Day Meal Plan*\n\n{response.content[0].text}\n\n"
        "💡 Use /meal_prep for a full prep guide and shopping list!",
        parse_mode="Markdown"
    )


async def meal_prep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    await update.message.reply_text("🛒 Generating your meal prep guide and shopping list...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": (
                f"Create a practical weekly meal prep guide for a Singapore-based woman targeting "
                f"{user['calorie_target']:.0f} kcal/day with {user['protein_g']:.0f}g protein.\n\n"
                "Include:\n"
                "1. **Sunday Meal Prep Plan** (step-by-step, ~2 hours)\n"
                "2. **Shopping List** (organised by: Proteins / Carbs & Veg / Pantry / Snacks)\n"
                "3. **Storage Tips** (what keeps how long)\n"
                "4. **Quick Assembly Ideas** (how to mix and match for different meals)\n\n"
                "Use Singapore-accessible ingredients (NTUC FairPrice / Giant / Sheng Siong friendly). "
                "Focus on high-protein, practical prep. Keep it realistic for someone busy."
            )
        }]
    )

    await update.message.reply_text(
        f"🛒 *Weekly Meal Prep Guide*\n\n{response.content[0].text}",
        parse_mode="Markdown"
    )


async def workout_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    equipment = user.get("equipment", "full_gym")
    duration = user.get("workout_duration_min", 45)

    equipment_label = {
        "full_gym": "Full gym access",
        "dumbbells": "Dumbbells + bodyweight",
        "bodyweight": "Bodyweight only"
    }.get(equipment, "Full gym access")

    phase_info = ""
    if user.get("cycle_start_date"):
        phase, day = get_cycle_phase(user["cycle_start_date"], user.get("cycle_length", 28))
        if phase:
            advice = cycle_phase_advice(phase)
            phase_info = f"\nNote: Currently in {phase} phase. {advice.get('workout', '')}"

    freeletics_moves = FREELETICS_EXERCISES["bodyweight"] + FREELETICS_EXERCISES.get(
        "dumbbells" if equipment == "dumbbells" else "full_gym" if equipment == "full_gym" else "bodyweight", []
    ) + FREELETICS_EXERCISES["pilates"]

    await update.message.reply_text("💪 Building your personalised Freeletics-style workout plan...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                f"Create a 7-day workout plan for body recomposition (goal: 20% body fat, lean toned physique).\n\n"
                f"Equipment: {equipment_label}\n"
                f"Session duration: {duration} minutes max\n"
                f"Style: Freeletics-inspired (use these exercises where possible): {', '.join(freeletics_moves[:20])}\n"
                f"Also include Pilates sessions for core, posture, and flexibility.\n"
                f"{phase_info}\n\n"
                "Weekly structure should include:\n"
                "• 3 Freeletics-style HIIT/strength sessions\n"
                "• 2 Pilates sessions\n"
                "• 1 active recovery (walk, light stretching)\n"
                "• 1 rest day\n\n"
                "For each workout day, provide:\n"
                "• Warm-up (5 min)\n"
                "• Main workout (sets/reps or time-based)\n"
                "• Cool-down/stretch\n"
                "• Tips for following along in the Freeletics app\n\n"
                "Make it progressive and achievable for someone working toward body recomposition."
            )
        }]
    )

    await update.message.reply_text(
        f"💪 *Your Weekly Workout Plan*\n\n{response.content[0].text}\n\n"
        "⚙️ Update your equipment anytime with /update_equipment\n"
        "🏃‍♀️ Working toward your half marathon? Use /running_plan!",
        parse_mode="Markdown"
    )


async def update_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Let user update their equipment and workout duration preferences."""
    from database.db import upsert_user
    from telegram import ReplyKeyboardMarkup

    args = context.args
    if not args:
        await update.message.reply_text(
            "Update your workout setup:\n"
            "• `/update_equipment full_gym`\n"
            "• `/update_equipment dumbbells`\n"
            "• `/update_equipment bodyweight`\n\n"
            "Or update duration: `/update_equipment full_gym 30`",
            parse_mode="Markdown"
        )
        return

    equip_map = {"full_gym": "full_gym", "dumbbells": "dumbbells", "bodyweight": "bodyweight"}
    equip = equip_map.get(args[0].lower())
    if not equip:
        await update.message.reply_text("Options: full_gym, dumbbells, bodyweight")
        return

    duration = int(args[1]) if len(args) > 1 else None
    update_data = {"telegram_id": update.effective_user.id, "equipment": equip}
    if duration:
        update_data["workout_duration_min"] = duration

    upsert_user(update_data)
    label = {"full_gym": "Full gym", "dumbbells": "Dumbbells + bodyweight", "bodyweight": "Bodyweight only"}[equip]
    dur_msg = f" ({duration} min sessions)" if duration else ""
    await update.message.reply_text(
        f"✅ Updated to *{label}*{dur_msg}! Use /workout_plan to get a new plan.",
        parse_mode="Markdown"
    )


async def running_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    args = context.args
    race_date = args[0] if args else None

    await update.message.reply_text("🏃‍♀️ Building your half marathon training plan...")

    weeks_info = ""
    if race_date:
        try:
            target = datetime.strptime(race_date, "%Y-%m-%d").date()
            weeks_away = (target - date.today()).days // 7
            weeks_info = f"Race date: {race_date} ({weeks_away} weeks away).\n"
        except Exception:
            weeks_info = ""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": (
                f"Create a half marathon training plan for a woman in Singapore.\n"
                f"{weeks_info}"
                f"She also does Freeletics (HIIT/strength) 3x/week and Pilates 2x/week.\n"
                f"Running experience: beginner to intermediate.\n\n"
                "Design a 12-week progressive plan that:\n"
                "• Builds weekly mileage by max 10% per week\n"
                "• Includes easy runs, tempo runs, and a weekly long run\n"
                "• Complements (not clashes with) her Freeletics + Pilates schedule\n"
                "• References Singapore running routes where relevant (MacRitchie, East Coast Park, Rail Corridor, etc.)\n"
                "• Includes race-day tips\n\n"
                "Format as a weekly summary for each of the 12 weeks with daily breakdown.\n"
                "Include a pace guide based on a target finish time of 2:30 (adjust to her level)."
            )
        }]
    )

    await update.message.reply_text(
        f"🏃‍♀️ *Half Marathon Training Plan*\n\n{response.content[0].text}\n\n"
        "📍 Singapore races to target:\n"
        "• Great Eastern Women's Run (November)\n"
        "• Standard Chartered Singapore Marathon (December)\n"
        "• Sundown Marathon (May/June)\n\n"
        "Log your runs with /log_workout and track your progress! 🌟",
        parse_mode="Markdown"
    )


async def singapore_activities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suggest fitness activities and events in Singapore."""
    await update.message.reply_text(
        "🇸🇬 *Fitness in Singapore — Your Guide*\n\n"
        "🏃‍♀️ *Running Routes:*\n"
        "• MacRitchie Reservoir — beautiful trail runs, TreeTop Walk loop (~10km)\n"
        "• East Coast Park — flat, scenic, great for tempo runs\n"
        "• Rail Corridor — 24km green corridor, Woodlands to Tanjong Pagar\n"
        "• Southern Ridges — hilly, scenic, connects HortPark to Labrador\n"
        "• Coney Island Park loop — peaceful trail run\n"
        "• Bukit Timah Nature Reserve — hilly, best for building running strength\n"
        "• CDC Trails (Choa Chu Kang / Bukit Batok) — guided nature trails\n\n"
        "🏅 *Races to Target:*\n"
        "• Great Eastern Women's Run (Nov) — great first race!\n"
        "• Standard Chartered Singapore Marathon (Dec)\n"
        "• Sundown Marathon (May/June — night race!)\n"
        "• Shape Run\n"
        "• Spartan Race Singapore (obstacle course)\n"
        "• Park Run (free, every Saturday morning, multiple locations)\n\n"
        "🧘 *Pilates Studios:*\n"
        "• Absolute Pilates, Club Pilates, Breathe Pilates, Sante Wellness\n\n"
        "🏋️ *HIIT & Functional Fitness:*\n"
        "• F45 Training, Barry's Bootcamp, Ritual Gym\n\n"
        "Use /running_plan [YYYY-MM-DD] to plan your half marathon training! 🏃‍♀️",
        parse_mode="Markdown"
    )


async def side_quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show and manage fitness side quests / mini-goals."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    await update.message.reply_text(
        "🎯 *Your Fitness Side Quests*\n\n"
        "These are mini-goals to work toward alongside your main goal of 20% body fat!\n\n"
        "🏅 *Strength & Fitness Benchmarks:*\n"
        "□ Do 20 consecutive push-ups\n"
        "□ Hold a plank for 2 minutes\n"
        "□ Dead hang for 30 seconds\n"
        "□ Achieve IPPT Pass standard\n"
        "□ Achieve IPPT Silver standard\n\n"
        "🏃‍♀️ *Running Milestones:*\n"
        "□ Run 5km without stopping\n"
        "□ Complete a 10km race\n"
        "□ Finish a half marathon\n"
        "□ Run MacRitchie TreeTop Walk loop\n\n"
        "🧘 *Pilates Progress:*\n"
        "□ Hold a Teaser for 30 seconds\n"
        "□ Complete 100 Hundreds\n"
        "□ Touch toes in Standing Forward Fold\n\n"
        "🎯 *Nutrition & Habits:*\n"
        "□ Hit protein target 7 days in a row\n"
        "□ Log meals consistently for 30 days\n"
        "□ Meal prep Sunday for 4 weeks straight\n\n"
        "Log a victory with /victory [description] when you hit one! 🏆\n"
        "Run a fitness test with /fitness_test to benchmark yourself.",
        parse_mode="Markdown"
    )


async def log_victory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("What did you achieve? `/victory I ran 5km without stopping!`", parse_mode="Markdown")
        return

    log_victory(update.effective_user.id, text)
    await update.message.reply_text(
        f"🏆 *Non-scale victory logged!*\n\n\"{text}\"\n\n"
        "This is what it's all about! Every win counts. Keep going! 🌸",
        parse_mode="Markdown"
    )
