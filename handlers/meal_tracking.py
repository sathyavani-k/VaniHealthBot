"""
Meal tracking handlers including food photo analysis.
"""

import os
import base64
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database.db import log_meal, get_today_meals, get_meal_history, get_user, update_streak
from utils.calculations import progress_bar
from google_sheets.sheets import append_meal_to_sheet
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


async def log_meal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first to set up your profile!")
        return

    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text(
            "Tell me what you ate! Examples:\n"
            "• `/log_meal 200g chicken breast with rice and broccoli`\n"
            "• `/log_meal protein shake, banana, peanut butter`\n"
            "Or just send me a photo of your food! 📸",
            parse_mode="Markdown"
        )
        return

    await _parse_and_log_meal(update, context, text, user)


async def handle_food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages — analyse food and log calories."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    await update.message.reply_text("📸 Analysing your food... one moment!")

    # Download photo
    photo = update.message.photo[-1]  # highest resolution
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()
    photo_b64 = base64.b64encode(photo_bytes).decode("utf-8")

    caption = update.message.caption or ""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
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
                            f"You are a nutrition expert. Analyse this food photo and estimate the nutritional content. "
                            f"Additional context from user: '{caption}'\n\n"
                            "Respond ONLY in this exact format:\n"
                            "FOOD: [what you see]\n"
                            "CALORIES: [number]\n"
                            "PROTEIN: [number in grams]\n"
                            "CARBS: [number in grams]\n"
                            "FAT: [number in grams]\n"
                            "CONFIDENCE: [high/medium/low]\n"
                            "NOTE: [any helpful note about the estimate]"
                        )
                    }
                ]
            }]
        )

        result = response.content[0].text
        lines = {line.split(":")[0].strip(): ":".join(line.split(":")[1:]).strip()
                 for line in result.strip().split("\n") if ":" in line}

        food = lines.get("FOOD", "Food from photo")
        calories = float(lines.get("CALORIES", 0))
        protein = float(lines.get("PROTEIN", 0))
        carbs = float(lines.get("CARBS", 0))
        fat = float(lines.get("FAT", 0))
        confidence = lines.get("CONFIDENCE", "medium")
        note = lines.get("NOTE", "")

        log_meal(update.effective_user.id, food, calories, protein, carbs, fat, "photo")
        update_streak(update.effective_user.id, "logging")
        append_meal_to_sheet(update.effective_user.id, food, calories, protein, carbs, fat)

        today = get_today_meals(update.effective_user.id)
        total_cal = sum(m["calories"] for m in today)
        target = user["calorie_target"]

        await update.message.reply_text(
            f"🍽️ *Food identified:* {food}\n\n"
            f"📊 *Estimated nutrition:*\n"
            f"• Calories: {calories:.0f} kcal\n"
            f"• Protein: {protein:.0f}g\n"
            f"• Carbs: {carbs:.0f}g\n"
            f"• Fat: {fat:.0f}g\n"
            f"• Confidence: {confidence.capitalize()}\n\n"
            f"📈 *Today's total:* {total_cal:.0f} / {target:.0f} kcal\n"
            f"{progress_bar(total_cal, target)} {int((total_cal/target)*100)}%\n\n"
            + (f"💡 {note}\n\n" if note else "") +
            "✅ Logged and synced to Google Sheets!",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(
            f"Sorry, I had trouble analysing that photo. Try `/log_meal [description]` instead.\nError: {str(e)}"
        )


async def _parse_and_log_meal(update, context, text, user):
    """Use Claude to parse natural language meal description into macros."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"Estimate nutritional content for: '{text}'\n\n"
                    "Respond ONLY in this format:\n"
                    "CALORIES: [number]\nPROTEIN: [grams]\nCARBS: [grams]\nFAT: [grams]"
                )
            }]
        )
        lines = {l.split(":")[0].strip(): l.split(":")[1].strip()
                 for l in response.content[0].text.strip().split("\n") if ":" in l}

        calories = float(lines.get("CALORIES", 0))
        protein = float(lines.get("PROTEIN", 0))
        carbs = float(lines.get("CARBS", 0))
        fat = float(lines.get("FAT", 0))

    except Exception:
        calories, protein, carbs, fat = 0, 0, 0, 0

    log_meal(update.effective_user.id, text, calories, protein, carbs, fat)
    update_streak(update.effective_user.id, "logging")
    append_meal_to_sheet(update.effective_user.id, text, calories, protein, carbs, fat)

    today = get_today_meals(update.effective_user.id)
    total_cal = sum(m["calories"] for m in today)
    total_protein = sum(m["protein_g"] for m in today)
    target_cal = user["calorie_target"]
    target_protein = user["protein_g"]

    remaining = max(0, target_cal - total_cal)

    await update.message.reply_text(
        f"✅ *Logged:* {text}\n\n"
        f"• Calories: ~{calories:.0f} kcal\n"
        f"• Protein: ~{protein:.0f}g | Carbs: ~{carbs:.0f}g | Fat: ~{fat:.0f}g\n\n"
        f"📊 *Today so far:*\n"
        f"Calories: {total_cal:.0f} / {target_cal:.0f} kcal\n"
        f"{progress_bar(total_cal, target_cal)} {int((total_cal/target_cal)*100)}%\n"
        f"Protein: {total_protein:.0f} / {target_protein:.0f}g\n"
        f"{progress_bar(total_protein, target_protein)}\n\n"
        f"{'✅ On track!' if total_cal <= target_cal else '⚠️ Over target — adjust your next meal.'}\n"
        f"{'🥩 Hit your protein target!' if total_protein >= target_protein else f'Still need {target_protein - total_protein:.0f}g protein today.'}",
        parse_mode="Markdown"
    )


async def daily_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    meals = get_today_meals(update.effective_user.id)
    if not meals:
        await update.message.reply_text("No meals logged today yet! Use /log_meal or send a food photo 📸")
        return

    total_cal = sum(m["calories"] for m in meals)
    total_protein = sum(m["protein_g"] for m in meals)
    total_carbs = sum(m["carbs_g"] for m in meals)
    total_fat = sum(m["fat_g"] for m in meals)

    target_cal = user["calorie_target"]
    target_protein = user["protein_g"]
    target_carbs = user["carbs_g"]
    target_fat = user["fat_g"]

    meal_list = "\n".join([f"• {m['description']} — {m['calories']:.0f} kcal" for m in meals])

    await update.message.reply_text(
        f"📊 *Today's Summary*\n\n"
        f"🍽️ *Meals logged:*\n{meal_list}\n\n"
        f"*Calories:* {total_cal:.0f} / {target_cal:.0f} kcal\n"
        f"{progress_bar(total_cal, target_cal)} {int((total_cal/target_cal)*100)}%\n\n"
        f"*Protein:* {total_protein:.0f} / {target_protein:.0f}g\n"
        f"{progress_bar(total_protein, target_protein)}\n\n"
        f"*Carbs:* {total_carbs:.0f} / {target_carbs:.0f}g\n"
        f"{progress_bar(total_carbs, target_carbs)}\n\n"
        f"*Fat:* {total_fat:.0f} / {target_fat:.0f}g\n"
        f"{progress_bar(total_fat, target_fat)}",
        parse_mode="Markdown"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    days = get_meal_history(update.effective_user.id, days=7)
    if not days:
        await update.message.reply_text("No meal history yet. Start logging with /log_meal!")
        return

    target = user["calorie_target"]
    lines = ["📅 *Last 7 Days*\n"]
    for d in days:
        bar = progress_bar(d["total_cal"] or 0, target, length=8)
        status = "✅" if (d["total_cal"] or 0) <= target else "⚠️"
        lines.append(f"{status} *{d['day']}* — {d['total_cal']:.0f} kcal\n{bar}")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def eating_out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get healthy recommendations for a restaurant or cuisine."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            "Tell me where you're eating! Examples:\n"
            "• `/eating_out Thai food`\n"
            "• `/eating_out Nobu Singapore`\n"
            "• `/eating_out hawker centre`",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text("🍽️ Looking up healthy options for you...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                f"I'm eating at/ordering from: {query}\n"
                f"My daily calorie target is {user['calorie_target']:.0f} kcal, "
                f"protein target {user['protein_g']:.0f}g. "
                f"My goal is body recomposition to 20% body fat — lean, toned physique.\n\n"
                "Give me the top 3 best menu choices or dish recommendations for this cuisine/restaurant. "
                "Focus on: high protein, moderate carbs, not too heavy. "
                "Include approximate calories and protein for each option. Be concise and practical."
            )
        }]
    )

    await update.message.reply_text(
        f"🍽️ *Healthy picks for {query}:*\n\n{response.content[0].text}",
        parse_mode="Markdown"
    )
