"""
app.py — Streamlit UI for the carbon footprint text-input module.

Run with:
    streamlit run app.py

What it does:
1. User types a normal sentence describing an activity.
2. extractor.py pulls out structured entries.
3. validators.py checks/corrects them (calling maps_service.py for
   travel distances when an origin/destination is given).
4. calculator.py estimates kg CO2e for each valid entry.
5. Valid entries get added to a running log for the session, shown as
   a table with a running total; invalid ones show the issue instead
   so the user can rephrase.
"""

import streamlit as st
import pandas as pd

from extractor import extract_entries
from validators import validate_entries
from calculator import estimate_co2_kg

st.set_page_config(page_title="Carbon Footprint Tracker", page_icon="🌍", layout="centered")

if "log" not in st.session_state:
    st.session_state.log = []  # list of validated entries with co2_kg added

st.title("🌍 Carbon Footprint Tracker")
st.caption("Describe an activity in plain language — the app extracts and validates it automatically.")

with st.expander("Examples you can type"):
    st.markdown(
        "- I drove from Indore to Bhopal today\n"
        "- took a bus 15 km to college\n"
        "- I ate 2 eggs and a burger for lunch\n"
        "- bought 2 t-shirts and a pair of shoes\n"
        "- used 5 litre of petrol this week"
    )

user_text = st.text_area(
    "What did you do?",
    placeholder="e.g. I flew from Delhi to Mumbai and ate a chicken sandwich",
    height=100,
)

col1, col2 = st.columns([1, 1])
analyze_clicked = col1.button("Analyze", type="primary", use_container_width=True)
clear_clicked = col2.button("Clear log", use_container_width=True)

if clear_clicked:
    st.session_state.log = []
    st.rerun()

if analyze_clicked:
    if not user_text.strip():
        st.warning("Type something first.")
    else:
        with st.spinner("Extracting and validating..."):
            entries = extract_entries(user_text)
            entries = validate_entries(entries)

        if not entries:
            st.error(
                "Couldn't recognise any activity in that sentence. "
                "Try mentioning a category clearly, e.g. 'drove 10 km' or 'ate 2 eggs'."
            )
        else:
            for e in entries:
                st.markdown("---")
                title = f"**{e['category'].title()}** — {e['activity']}"
                if e.get("origin") and e.get("destination"):
                    title += f" ({e['origin']} → {e['destination']})"
                st.markdown(title)

                if e["valid"]:
                    co2 = estimate_co2_kg(e)
                    st.success(
                        f"{e.get('quantity')} {e.get('unit')} · "
                        f"~{co2} kg CO2e · confidence: {e['confidence']}"
                    )
                    e["co2_kg"] = co2
                    st.session_state.log.append(e)
                else:
                    st.error("Not added — " + " ".join(e["issues"]))
                    if e.get("debug_errors"):
                        with st.expander("Why did the map lookup fail? (debug info)"):
                            for line in e["debug_errors"]:
                                st.text(line)

                if e["issues"] and e["valid"]:
                    st.caption("⚠ " + " ".join(e["issues"]))

st.markdown("## Session log")
if st.session_state.log:
    df = pd.DataFrame([
        {
            "Category": e["category"],
            "Activity": e["activity"],
            "Quantity": e.get("quantity"),
            "Unit": e.get("unit"),
            "kg CO2e": e.get("co2_kg", 0),
            "Confidence": e.get("confidence"),
        }
        for e in st.session_state.log
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.metric("Total estimated footprint", f"{df['kg CO2e'].sum():.2f} kg CO2e")
else:
    st.info("No entries yet — analyze something above.")