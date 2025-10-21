import os
import base64
import calendar
from datetime import date

import streamlit as st

from age_utils import calculate_age, bmi, recommend_measurements


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def main():
    st.set_page_config(page_title="Age & Health Advisor", layout="wide")

    # Neutral background, no watermark/logo — responsive + footer styles added
    css = """
    <style>
      .stApp { background-color: #f6f9fc; }
      .stApp > main {
        position: relative;
        z-index: 2;
        background: rgba(255,255,255,0.98) !important;
        border-radius: 12px;
        padding: 1.25rem;
        margin: 2rem auto;
        max-width: 980px;
        box-shadow: 0 12px 40px rgba(3,18,37,0.08);
      }
      .stApp h1, .stApp h2, .stApp h3 {
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
        background: linear-gradient(90deg, #00e0ff, #7b61ff, #ff7ab6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .stApp, .stApp .stText, .stApp p, label { color: #042034 !important; font-size: 16px; }
      section[data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(255,255,255,0.94)) !important;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 6px 18px rgba(0,0,0,0.06);
        position: relative;
        z-index: 3;
      }
      section[data-testid="stSidebar"] .bmi-box {
        border: 1px solid rgba(11,37,69,0.12);
        padding: 10px 12px;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff, #fbfbff);
        color: #042034;
        box-shadow: 0 4px 10px rgba(3,18,37,0.04);
        margin-top: 10px;
      }

      /* Company logo fixed position (desktop) */
      .company-logo-fixed {
        position: fixed;
        right: 18px;
        top: 12px;
        width: 140px;
        height: auto;
        z-index: 9999;
        pointer-events: none;
        opacity: 0.98;
      }
      @media (max-width: 600px) {
        .company-logo-fixed { width: 90px; top: 8px; right: 8px; opacity: 0.95; }
      }

      /* Footer (author) */
      .app-footer {
        position: fixed;
        right: 12px;
        bottom: 10px;
        z-index: 9999;
        font-size: 12px;
        color: #6b7280;
        background: rgba(255,255,255,0.85);
        padding: 6px 10px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(3,18,37,0.06);
      }

      /* Responsive: mobile adjustments */
      @media (max-width: 900px) {
        .stApp > main { margin: 1rem auto; padding: 0.75rem; max-width: 92vw; }
        section[data-testid="stSidebar"] > div:first-child { padding: 0.75rem; margin: 0.25rem; }
        .bmi-box { padding: 8px 10px; font-size: 0.95rem; }
        .company-logo-fixed { width: 72px !important; right: 8px; top: 8px; }
        .app-footer { left: 50%; transform: translateX(-50%); right: auto; bottom: 8px; font-size: 12px; }
      }

      @media (max-width: 420px) {
        .stApp > main { margin: 0.6rem auto; padding: 0.6rem; }
        .stApp, .stApp .stText, .stApp p, label { font-size: 14px !important; }
      }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    # Add company logo (embedded, fixed top-right)
    logo_path = r"C:\pp\GitHub\AgenticAI-Usecases\AgenticAI-Usecases\AgeCalCulator\Abrandingimage.png"
    if os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as _f:
                logo_b64 = base64.b64encode(_f.read()).decode("utf-8")
            logo_html = f"""
            <img class="company-logo-fixed" src="data:image/png;base64,{logo_b64}" alt="Company Logo"/>
            """
            st.markdown(logo_html, unsafe_allow_html=True)
        except Exception:
            st.warning("Unable to load company logo. File may be corrupted.")
    else:
        st.info("Company logo not found at the provided path.")

    st.title("Age & Health Advisor")

    # show author footer (fixed)
    st.markdown('<div class="app-footer">Developed by "Prakash Pujari"</div>', unsafe_allow_html=True)

    # Sidebar: gender + weight/height as dropdowns (support child -> adult)
    with st.sidebar:
        gender = st.selectbox("Gender", ["Prefer not to say", "Male", "Female", "Other"])

        # Weight: 2.0 kg -> 200.0 kg (0.1 kg steps)
        weight_options = [round(x / 10.0, 1) for x in range(20, 2001)]
        default_weight = 70.0
        default_w_idx = next((i for i, v in enumerate(weight_options) if v == default_weight), 0)
        weight_kg = st.selectbox("Weight (kg)", weight_options, index=default_w_idx)

        # Height: 40 cm -> 220 cm
        height_options = list(range(40, 221))
        default_height = 170
        default_h_idx = next((i for i, v in enumerate(height_options) if v == default_height), 0)
        height_cm = st.selectbox("Height (cm)", height_options, index=default_h_idx)

    # Centered column for DOB inputs
    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        today = date.today()
        year_options = list(range(today.year, 1899, -1))
        selected_year = st.selectbox("Birth Year", year_options, index=0)

        month_options = list(range(1, 13))
        selected_month = st.selectbox(
            "Birth Month",
            month_options,
            format_func=lambda m: calendar.month_name[m],
            index=today.month - 1,
        )

        max_day = days_in_month(selected_year, selected_month)
        day_options = list(range(1, max_day + 1))
        default_day_index = min(today.day - 1, len(day_options) - 1)
        selected_day = st.selectbox("Birth Day", day_options, index=default_day_index)

        if st.button("Calculate Age"):
            try:
                years_old, months_old, days_old = calculate_age(selected_year, selected_month, selected_day)
                st.markdown(f"**Age: {years_old} years, {months_old} months, {days_old} days**")
            except ValueError as e:
                st.error(f"Error: {e}")
                return

            # BMI quick check and sidebar BMI box
            try:
                user_bmi = bmi(float(weight_kg), float(height_cm))
                st.metric("BMI", f"{user_bmi:.1f}")
                st.sidebar.markdown(
                    f'<div class="bmi-box"><strong>BMI:</strong> {user_bmi:.1f}<br/><small>Height: {int(height_cm)} cm • Weight: {weight_kg} kg</small></div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.info("Enter valid height and weight for BMI calculation.")

            # Recommendations
            rec = recommend_measurements(years_old, gender if gender != "Prefer not to say" else None)
            st.subheader("Recommendations")
            if isinstance(rec, dict):
                if rec.get("life_stage"):
                    st.write("Life stage:", rec["life_stage"])
                if rec.get("measurements"):
                    st.write("Suggested measurements:")
                    st.json(rec["measurements"])
                if rec.get("tips"):
                    st.write("Tips:")
                    st.write(rec["tips"])
            else:
                st.write(rec)


if __name__ == "__main__":
    main()
