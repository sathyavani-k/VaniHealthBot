"""
VaniHealthBot — Holistic Health & Fitness Telegram Bot
Main entry point.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

from database.db import init_db
from handlers.onboarding import get_onboarding_handler
from handlers.fitness_benchmarks import get_fitness_test_handler, hr_zones
from handlers.meal_tracking import (
    log_meal_cmd, daily_summary, history, handle_food_photo, eating_out
)
from handlers.body_tracking import (
    log_weight_cmd, progress_cmd, log_measurements_cmd, handle_picooc_scan
)
from handlers.planning import (
    meal_plan, meal_prep, workout_plan, update_equipment,
    running_plan, singapore_activities, side_quests, log_victory_cmd
)
from handlers.water_cycle import (
    log_water_cmd, log_cycle, log_sleep, log_stress,
    streaks_cmd, log_workout_cmd
)
from handlers.ai_coach import (
    ai_coach_message, weekly_checkin, weekly_report,
    macro_cycle_info, supplements_cmd, add_supplement_cmd,
    refeed_day, mindset_tip, help_cmd
)
from handlers.vanihard import (
    vanihard_start, vanihard_begin, vanihard_today, vanihard_log,
    yoga_routine, calisthenics_plan, calisthenics_progressions_cmd
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def photo_router(update: Update, context):
    """Route incoming photos to the right handler (PICOOC scan vs food photo)."""
    caption = (update.message.caption or "").lower()
    is_scan = any(kw in caption for kw in ["picooc", "scan", "weight scan", "body scan", "measurement"])

    if is_scan:
        from handlers.body_tracking import handle_picooc_scan
        await handle_picooc_scan(update, context)
    else:
        await handle_food_photo(update, context)


def main():
    init_db()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN not set in .env file!")

    app = Application.builder().token(token).build()

    # ─── Conversation handlers (must be first) ────────────────────────────────
    app.add_handler(get_onboarding_handler())
    app.add_handler(get_fitness_test_handler())

    # ─── Tracking commands ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("log_meal", log_meal_cmd))
    app.add_handler(CommandHandler("daily_summary", daily_summary))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("log_weight", log_weight_cmd))
    app.add_handler(CommandHandler("measurements", log_measurements_cmd))
    app.add_handler(CommandHandler("progress", progress_cmd))
    app.add_handler(CommandHandler("log_workout", log_workout_cmd))
    app.add_handler(CommandHandler("water", log_water_cmd))
    app.add_handler(CommandHandler("sleep", log_sleep))
    app.add_handler(CommandHandler("stress", log_stress))
    app.add_handler(CommandHandler("cycle", log_cycle))

    # ─── Planning commands ────────────────────────────────────────────────────
    app.add_handler(CommandHandler("meal_plan", meal_plan))
    app.add_handler(CommandHandler("meal_prep", meal_prep))
    app.add_handler(CommandHandler("workout_plan", workout_plan))
    app.add_handler(CommandHandler("update_equipment", update_equipment))
    app.add_handler(CommandHandler("running_plan", running_plan))
    app.add_handler(CommandHandler("eating_out", eating_out))

    # ─── Fitness benchmarks ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("hr_zones", hr_zones))

    # ─── Goals & motivation ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("side_quests", side_quests))
    app.add_handler(CommandHandler("victory", log_victory_cmd))
    app.add_handler(CommandHandler("streaks", streaks_cmd))

    # ─── Reports & analysis ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("weekly_report", weekly_report))
    app.add_handler(CommandHandler("checkin", weekly_checkin))

    # ─── Smart features ───────────────────────────────────────────────────────
    app.add_handler(CommandHandler("macro_cycle", macro_cycle_info))
    app.add_handler(CommandHandler("refeed", refeed_day))
    app.add_handler(CommandHandler("supplements", supplements_cmd))
    app.add_handler(CommandHandler("add_supplement", add_supplement_cmd))
    app.add_handler(CommandHandler("mindset", mindset_tip))

    # ─── Singapore specific ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("sg_activities", singapore_activities))

    # ─── VaniHard challenge ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("vanihard", vanihard_begin))
    app.add_handler(CommandHandler("vanihard_today", vanihard_today))
    app.add_handler(CommandHandler("vanihard_log", vanihard_log))

    # ─── Yoga & Calisthenics ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("yoga", yoga_routine))
    app.add_handler(CommandHandler("calisthenics", calisthenics_plan))
    app.add_handler(CommandHandler("progressions", calisthenics_progressions_cmd))

    # ─── Help ─────────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("help", help_cmd))

    # ─── Photo handler (food or PICOOC scan) ──────────────────────────────────
    app.add_handler(MessageHandler(filters.PHOTO, photo_router))

    # ─── AI Coach — catch-all for text messages ───────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_coach_message))

    logger.info("VaniHealthBot is running! 🌸")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
