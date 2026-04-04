"""
Health and fitness calculations for VaniHealthBot.
"""

from datetime import date, datetime


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

CYCLE_PHASES = {
    "menstrual":    (1, 5),
    "follicular":   (6, 13),
    "ovulation":    (14, 16),
    "luteal":       (17, 28),
}


def calculate_bmr(weight_kg, height_cm, age, sex="female"):
    """Mifflin-St Jeor BMR."""
    if sex == "female":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5


def calculate_tdee(weight_kg, height_cm, age, activity_level, sex="female"):
    bmr = calculate_bmr(weight_kg, height_cm, age, sex)
  2 return bmr * ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)


def calculate_targets(tdee, goal="recomposition"):
    """
    Returns (calorie_target, protein_g, carbs_g, fat_g).
    Recomposition: slight deficit (~250 kcal), high protein.
    """
    if goal == "recomposition":
        calorie_target = tdee - 250
    elif goal == "cut":
        calorie_target = tdee - 500
    else:
        calorie_target = tdee

    # High protein for body recomp: 2g per kg body weight (set at 30% of calories)
    protein_g = (calorie_target * 0.30) / 4
    fat_g = (calorie_target * 0.28) / 9
    carbs_g = (calorie_target - protein_g * 4 - fat_g * 9) / 4
    return calorie_target, protein_g, carbs_g, fat_g


def macro_cycle_targets(tdee, is_workout_day: bool):
    """
    Macro cycling: +100 cal on workout days (mostly carbs), -100 on rest days.
    Returns (calorie_target, protein_g, carbs_g, fat_g).
    """
    base_cal = tdee - 250
    if is_workout_day:
        calorie_target = base_cal + 100
        carb_factor = 0.35
    else:
        calorie_target = base_cal - 100
        carb_factor = 0.25

    protein_g = (calorie_target * 0.32) / 4
    fat_g = (calorie_target * (1 - 0.32 - carb_factor)) / 9
    carbs_g = (calorie_target * carb_factor) / 4
  2 return calorie_target, protein_g, carbs_g, fat_g


def estimate_weeks_to_goal(current_bf, goal_bf, weight_kg, calorie_deficit_per_day=250):
    """Rough estimate of weeks to reach goal body fat %."""
    current_fat_kg = weight_kg * (current_bf / 100)
    goal_fat_kg = weight_kg * (goal_bf / 100)
    fat_to_lose_kg = max(0, current_fat_kg - goal_fat_kg)
    weekly_loss_kg = (calorie_deficit_per_day * 7) / 7700
    if weekly_loss_kg <= 0:
        return None
    return round(fat_to_lose_kg / weekly_loss_kg)


def get_cycle_phase(cycle_start_date_str, cycle_length=28):
    """Returns the current menstrual cycle phase name."""
    if not cycle_start_date_str:
        return None
    try:
        start = datetime.strptime(cycle_start_date_str, "%Y-%m-%d").date()
        day_of_cycle = ((date.today() - start).days % cycle_length) + 1
        for phase, (start_day, end_day) in CYCLE_PHASES.items():
            if start_day <= day_of_cycle <= end_day:
                return phase, day_of_cycle
    except Exception:
        return None, None
    return "luteal", day_of_cycle


def cycle_phase_advice(phase):
    """Returns workout and nutrition advice for the given cycle phase."""
    advice = {
        "menstrual": {
            "workout": "Low intensity today — gentle pilates, yoga, or walking. Your body is working hard. Rest is productive.",
            "nutrition": "Focus on iron-rich foods (spinach, lentils, red meat). Slightly higher carbs can ease fatigue.",
            "energy": "Low. Be kind to yourself."
        },
        "follicular": {
            "workout": "Your energy is rising! Great time for higher intensity Freeletics, strength work, and cardio.",
            "nutrition": "Lighter meals work well. Estrogen is rising — your body is primed for building muscle.",
            "energy": "High. Push your workouts now."
        },
   2    "ovulation": {
            "workout": "Peak strength and energy — this is your power window. Go hard on Freeletics and strength sessions.",
            "nutrition": "Keep protein high. You can handle slightly higher calories around ovulation.",
            "energy": "Peak. Best time for PBs."
        },
        "luteal": {
            "workout": "Moderate intensity. Pilates, lighter strength, longer walks. Reduce HIIT as progesterone rises.",
            "nutrition": "Increase complex carbs slightly to reduce cravings. Magnesium helps with PMS symptoms.",
            "energy": "Decreasing. Plan easier workouts in the second half of this phase."
        },
    }
    return advice.get(phase, {})


# ─── IPPT Scoring (Women, age-banded) ────────────────────────────────────────

IPPT_WOMEN_STANDARDS = {
    # (age_min, age_max): {"gold": (pushups, situps, run_sec), "silver": ..., "pass": ...}
    (20, 24): {"gold": (18, 21, 1440), "silver": (14, 17, 1560), "pass": (6, 9, 1680)},
    (25, 29): {"gold": (16, 19, 1470), "silver": (12, 15, 1590), "pass": (5, 8, 1710)},
    (30, 34): {"gold": (14, 17, 1500), "silver": (10, 13, 1620), "pass": (4, 7, 1740)},
    (35, 39): {"gold": (12, 15, 1530), "silver": (9, 12, 1650), "pass": (4, 6, 1770)},
}


def score_ippt(age, pushups, situps, run_2_4km_sec):
    """Returns IPPT band: Gold / Silver / Pass / Fail."""
    for (a_min, a_max), standards in IPPT_WOMEN_STANDARDS.items():
        if a_min <= age <= a_max:
            for band in ["gold", "silver", "pass"]:
                req = standards[band]
                if pushups >= req[0] and situps >= req[1] and run_2_4km_sec <= req[2]:
                    return band.capitalize()
            return "Fail"
    return "N/A (age out of range)"


def format_run_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def progress_bar(current, target, length=10):
    filled = int((current / target) * length) if target > 0 else 0
    filled = min(filled, length)
    return "█" * filled + "░" * (length - filled)
