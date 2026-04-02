"""
Onboarding conversation handler.
Collects user profile and calculates TDEE + macro targets.
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
)
from database.db import upsert_user, get_user
from utils.calculations import calculate_tdee, calculate_targets, estimate_weeks_to_goal

(NAME, AGE, HEIGHT, WEIGHT, BODY_FAT, GOAL_BF, ACTIVITY, EQUIPMENT, DURATION) = range(9)

ACTIVITY_OPTIONS = [["Sedentary", "Lightly Active"], ["Moderately Active", "Very Active"]]
EQUIPMENT_OPTIONS = [["Full Gym", "Dumbbells + Bodyweight", "Bodyweight Only"]]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"Welcome back, {user['name']}! 🌸\n\n"
            "Use /help to see all commands, or just chat with me about your fitness journey!\n\n"
            "Type /setup to update your profile."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Hey there! 🌸 I'm VaniHealthBot — your personal holistic health companion.\n\n"
        "I'm here to help you crush your body recomposition goal and get that lean, strong, "
        "pilates-princess physique you're working toward!\n\n"
        "Let's start by setting up your profile. What's your name?"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(f"Love that name! How old are you, {context.user_data['name']}? 🎂")
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["age"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 28)")
        return AGE
    await update.message.reply_text("What's your height in cm? (e.g. 165)")
    return HEIGHT


async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["height_cm"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number in cm (e.g. 165)")
        return HEIGHT
    await update.message.reply_text("And your current weight in kg? (e.g. 62.5)")
    return WEIGHT


async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["weight_kg"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number in kg (e.g. 62.5)")
        return WEIGHT
    await update.message.reply_text(
        "Do you know your current body fat %? (e.g. 37)\n\n"
        "If you're not sure, type 'skip' and we'll estimate from your stats."
    )
    return BODY_FAT


async def get_body_fat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text == "skip":
        context.user_data["body_fat_pct"] = None
    else:
        try:
            context.user_data["body_fat_pct"] = float(text)
        except ValueError:
            await update.message.reply_text("Enter a number (e.g. 37) or type 'skip'")
            return BODY_FAT
    await update.message.reply_text(
        "What's your goal body fat %? Your target is 20% — want to go with that? (type 20 or enter a different number)"
    )
    return GOAL_BF


async def get_goal_bf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["goal_bf_pct"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 20)")
        return GOAL_BF

    await update.message.reply_text(
        "How active are you on a typical week? 🏃‍♀️",
        reply_markup=ReplyKeyboardMarkup(ACTIVITY_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
    )
    return ACTIVITY


async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mapping = {
        "sedentary": "sedentary",
        "lightly active": "light",
        "moderately active": "moderate",
        "very active": "very_active",
    }
    level = mapping.get(update.message.text.strip().lower(), "moderate")
    context.user_data["activity_level"] = level

    await update.message.reply_text(
        "What equipment do you have access to? 💪",
        reply_markup=ReplyKeyboardMarkup(EQUIPMENT_OPTIONS, one_time_keyboard=True, resize_keyboard=True)
    )
    return EQUIPMENT


async def get_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mapping = {
        "full gym": "full_gym",
        "dumbbells + bodyweight": "dumbbells",
        "bodyweight only": "bodyweight",
    }
    equip = mapping.get(update.message.text.strip().lower(), "full_gym")
    context.user_data["equipment"] = equip

    await update.message.reply_text(
        "How long can you dedicate to each workout? (in minutes, e.g. 45)",
        reply_markup=ReplyKeyboardRemove()
    )
    return DURATION


async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a number in minutes (e.g. 45)")
        return DURATION

    context.user_data["workout_duration_min"] = duration

    # Calculate TDEE and targets
    ud = context.user_data
    tdee = calculate_tdee(ud["weight_kg"], ud["height_cm"], ud["age"], ud["activity_level"])
    calorie_target, protein_g, carbs_g, fat_g = calculate_targets(tdee)

    # Save to DB
    upsert_user({
        "telegram_id": update.effective_user.id,
        "name": ud["name"],
        "age": ud["age"],
        "height_cm": ud["height_cm"],
        "weight_kg": ud["weight_kg"],
        "body_fat_pct": ud.get("body_fat_pct"),
        "goal_bf_pct": ud["goal_bf_pct"],
        "activity_level": ud["activity_level"],
        "tdee": tdee,
        "calorie_target": calorie_target,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "equipment": ud["equipment"],
        "workout_duration_min": duration,
    })

    weeks = None
    if ud.get("body_fat_pct"):
        weeks = estimate_weeks_to_goal(ud["body_fat_pct"], ud["goal_bf_pct"], ud["weight_kg"])

    timeline = f"\n\n⏳ *Estimated timeline to {ud['goal_bf_pct']}% body fat: ~{weeks} weeks* (with consistency!)" if weeks else ""

    await update.message.reply_text(
        f"You're all set, {ud['name']}! 🎉🌸\n\n"
        f"Here's your personalised plan:\n\n"
        f"🔥 *Daily calorie target:* {calorie_target:.0f} kcal\n"
        f"🥩 *Protein:* {protein_g:.0f}g\n"
        f"🌾 *Carbs:* {carbs_g:.0f}g\n"
        f"🥑 *Fat:* {fat_g:.0f}g\n"
        f"📊 *Your TDEE:* {tdee:.0f} kcal{timeline}\n\n"
        "These targets are set for a gentle deficit — perfect for body recomposition (losing fat while maintaining muscle). "
        "I'll adjust as you progress! 💪\n\n"
        "Type /help to see everything I can do for you!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("No worries! Come back when you're ready 🌸", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def get_onboarding_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("setup", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            BODY_FAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_body_fat)],
            GOAL_BF: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal_bf)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity)],
            EQUIPMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_equipment)],
            DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
