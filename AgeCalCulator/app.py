import streamlit as st
from datetime import date
from age_utils import calculate_age, bmi, recommend_measurements


def main():
    st.set_page_config(page_title="Age & Health Advisor", layout="wide")
    st.markdown("""
        <style>
        body { background: #f5ecd7 !important; }
        .stApp { max-width: 900px; margin: auto; background: #f5ecd7; border-radius: 18px; box-shadow: 0 2px 16px #e0cfa0; padding: 24px 0 12px 0; }
        .block-container { margin-left: auto !important; margin-right: auto !important; }
        h1, h2, h3, h4, h5, h6 {
            color: #2a52be !important;
            font-family: 'Georgia', serif;
        }
        .classic-title {
            color: #d7263d;
            font-size: 2.5rem;
            font-family: 'Georgia', serif;
            text-shadow: 1px 1px 0 #fff, 2px 2px 0 #f5ecd7;
        }
        .classic-section {
            color: #2a9d8f;
            font-size: 1.2rem;
            font-family: 'Georgia', serif;
        }
        .classic-tips {
            color: #e9c46a;
            font-size: 1.1rem;
            font-family: 'Georgia', serif;
        }
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background: #f7f3e9 !important;
            border-radius: 16px 0 0 16px;
            box-shadow: 2px 0 12px #e0cfa0;
            padding-top: 24px;
            min-width: 280px;
            max-width: 320px;
        }
        [data-testid="stSidebarContent"] {
            padding-right: 16px;
        }
        </style>
    """, unsafe_allow_html=True)

    import os
    import base64
    brand_img_path = os.path.join(os.path.dirname(__file__), "joga_brand.png")
    if os.path.exists(brand_img_path):
        with open(brand_img_path, "rb") as img_file:
            img_bytes = img_file.read()
            img_b64 = base64.b64encode(img_bytes).decode()
        st.markdown(f"""
        <div style='position: absolute; top: 18px; right: 32px; z-index: 10;'>
            <img src='data:image/png;base64,{img_b64}' style='width:180px; border-radius:12px; box-shadow:0 2px 12px #aaa;'>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("<div class='classic-title'>Age Calculator & Healthy Living Recommendations</div>", unsafe_allow_html=True)


    with st.form("dob_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            year = st.number_input("Birth year", min_value=1900, max_value=date.today().year, value=1990)
        with col2:
            month = st.number_input("Birth month", min_value=1, max_value=12, value=1)
        with col3:
            day = st.number_input("Birth day", min_value=1, max_value=31, value=1)

        gender = st.selectbox("Gender", options=["Other", "Female", "Male"])
        submitted = st.form_submit_button("Calculate age")

    if submitted:
        try:
            y, m, d = calculate_age(int(year), int(month), int(day))
        except Exception as e:
            st.error(f"Error calculating age: {e}")
            return

        st.markdown(f"<div class='classic-section'>You are <b>{y} years, {m} months and {d} days</b> old.</div>", unsafe_allow_html=True)

        # measurements and tips
        rec = recommend_measurements(y, gender)

        st.markdown("<div class='classic-section'><b>Life stage & recommendations</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='classic-section'><b>Life stage:</b> {rec['life_stage']}</div>", unsafe_allow_html=True)
        st.markdown("<div class='classic-tips'><b>Lifestyle tips:</b></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='classic-tips'>{rec['tips']}</div>", unsafe_allow_html=True)

        with st.expander("Recommended body measurements (general)"):
            for k, v in rec["measurements"].items():
                st.markdown(f"<span style='color:#e76f51;font-family:Georgia;'>{k}: {v}</span>", unsafe_allow_html=True)

    st.sidebar.header("Quick BMI Calculator")
    with st.sidebar.form("bmi_form"):
        w = st.number_input("Weight (kg)", min_value=1.0, value=70.0)
        h = st.number_input("Height (cm)", min_value=30.0, value=170.0)
        calc = st.form_submit_button("Compute BMI")
    if calc:
        try:
            v = bmi(float(w), float(h))
            st.sidebar.markdown(f"<span style='color:#2a52be;font-size:20px;font-family:Georgia;'>BMI: <b>{v}</b></span>", unsafe_allow_html=True)
            if v < 18.5:
                st.sidebar.warning("Underweight: consider nutrient-dense foods and strength training.")
            elif v < 25:
                st.sidebar.success("Normal weight: maintain balanced diet and regular activity.")
            elif v < 30:
                st.sidebar.warning("Overweight: combine cardio and strength; watch calories.")
            else:
                st.sidebar.error("Obesity range: consult a healthcare provider for personalized plan.")
        except Exception as e:
            st.sidebar.error(f"BMI error: {e}")

    st.markdown("<hr style='margin-top:2em;margin-bottom:0.5em;'>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;color:#2a52be;font-size:16px;font-family:Georgia;'>Developed by Prakash Pujari</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
