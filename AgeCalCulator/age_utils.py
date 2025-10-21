from datetime import date
from typing import Dict, Tuple


def calculate_age(birth_year: int, birth_month: int, birth_day: int, today: date = None) -> Tuple[int, int, int]:
    """Calculate age in years, months, days given date of birth.

    Returns (years, months, days). Raises ValueError on invalid dates or future DOB.
    """
    if today is None:
        today = date.today()

    try:
        dob = date(birth_year, birth_month, birth_day)
    except Exception as e:
        raise ValueError(f"Invalid date of birth: {e}")

    if dob > today:
        raise ValueError("Date of birth is in the future")

    years = today.year - dob.year
    months = today.month - dob.month
    days = today.day - dob.day

    if days < 0:
        # borrow days from previous month
        from calendar import monthrange

        prev_month = (today.month - 1) or 12
        prev_year = today.year if today.month != 1 else today.year - 1
        days_in_prev = monthrange(prev_year, prev_month)[1]
        days += days_in_prev
        months -= 1

    if months < 0:
        months += 12
        years -= 1

    return years, months, days


def bmi(weight_kg: float, height_cm: float) -> float:
    """Calculate BMI given weight in kg and height in cm."""
    if height_cm <= 0:
        raise ValueError("height_cm must be > 0")
    h_m = height_cm / 100.0
    return round(weight_kg / (h_m * h_m), 1)


def recommend_measurements(age_years: int, gender: str = "other") -> Dict[str, str]:
    """Return recommended body measurements and lifestyle tips based on age and gender.

    This provides general, non-medical advice.
    """
    tips = []
    measurements = {}

    # Basic categories
    if age_years < 18:
        life_stage = "Child/Teen"
        tips.append("Focus on balanced nutrition, sleep, and regular physical activity.")
    elif age_years < 35:
        life_stage = "Young Adult"
        tips.append("Maintain regular exercise (strength + cardio) and balanced diet.")
    elif age_years < 60:
        life_stage = "Adult"
        tips.append("Include strength training to preserve muscle and bone health.")
    else:
        life_stage = "Senior"
        tips.append("Prioritize balance, low-impact cardio, strength, and mobility work.")

    # Gender/goal-based simple measurements (very approximate generic recommendations)
    g = gender.lower()
    if g in ("male", "m"):
        measurements = {
            "Chest_cm": "90-110 (varies by height)",
            "Waist_cm": "80-94",
            "Hip_cm": "90-105",
        }
    elif g in ("female", "f"):
        measurements = {
            "Chest_cm": "80-100",
            "Waist_cm": "70-88",
            "Hip_cm": "90-110",
        }
    else:
        measurements = {
            "Chest_cm": "80-110",
            "Waist_cm": "70-100",
            "Hip_cm": "85-110",
        }

    # Age-based adjustments
    if age_years >= 50:
        tips.append("Consume adequate protein and calcium; get regular health screenings.")

    if age_years >= 65:
        tips.append("Focus on fall prevention, balance exercises, and maintaining independence.")

    tips.append("Hydrate regularly and limit processed foods and excessive sugar.")

    return {
        "life_stage": life_stage,
        "measurements": measurements,
        "tips": " \n".join(tips),
    }


def recommend_measurements(age_years, gender=None):
    """
    Return a dict with keys: life_stage, measurements (dict), tips (list or str).
    This function is defensive: it accepts gender==None or unknown values.
    """
    life_stage = None
    tips = []
    measurements = {}

    # Simple life-stage buckets
    if age_years < 13:
        life_stage = "Child"
        tips.append("Focus on growth, regular pediatric checkups, and active play.")
    elif age_years < 20:
        life_stage = "Teen"
        tips.append("Ensure balanced nutrition and regular physical activity.")
    elif age_years < 40:
        life_stage = "Adult"
        tips.append("Maintain a balance of cardio and strength training.")
    elif age_years < 60:
        life_stage = "Middle-aged"
        tips.append("Prioritize strength training, flexibility, and joint care.")
    else:
        life_stage = "Senior"
        tips.append("Prioritize balance, low-impact cardio, strength, and mobility.")

    # Normalize gender safely (handle None or unexpected types)
    g = (gender or "").strip().lower()
    if g in ("male", "m"):
        measurements = {
            "Chest_cm": "90-110 (varies by height)",
            "Waist_cm": "80-100",
            "Hip_cm": "95-105",
        }
    elif g in ("female", "f"):
        measurements = {
            "Chest_cm": "80-100 (varies by height)",
            "Waist_cm": "70-95",
            "Hip_cm": "95-115",
        }
    else:
        # Generic, non-gendered guidance when gender is unknown/not provided
        measurements = {
            "Chest_cm": "80-110 (varies by height and body type)",
            "Waist_cm": "70-100",
            "Hip_cm": "90-115",
        }
        tips.append("Measurements are generic because gender was not specified.")

    return {"life_stage": life_stage, "measurements": measurements, "tips": "\n".join(tips)}
