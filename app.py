import streamlit as st
from datetime import date, time
import importlib.util
import os

st.set_page_config(
    page_title="ASTRO-BHUDEB",
    page_icon="🔮",
    layout="wide",
)

# ================================================================
# ENGINE LOADER
# ------------------------------------------------------------
# bhudeb_d5_engine.py is not a set of importable functions only —
# most of it is a linear, top-to-bottom computation (Mahadasha ->
# Antardasha -> Pratyantardasha -> KP significators -> D5.17..D5.20
# transit discrimination). Importing it RUNS that whole pipeline
# once. build_universal_event_v1() (added at the bottom of the
# engine) then reads the final D520_RANKED winner out of it.
#
# st.cache_resource makes sure this heavy computation runs only
# ONCE per server process, not on every Streamlit rerun/click.
# ================================================================

ENGINE_PATH = os.path.join(os.path.dirname(__file__), "bhudeb_d5_engine.py")


@st.cache_resource(show_spinner="Running ASTRO-BHUDEB D5 engine (MD → AD → PD → transit discrimination)...")
def load_engine():
    spec = importlib.util.spec_from_file_location("bhudeb_d5_engine", ENGINE_PATH)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


# The engine's own EVENT_RULES keys (kept as-is, not renamed, so the
# bridge function's nested lookups still match what the engine module
# actually defines).
ENGINE_EVENT_NAMES = [
    "Career / Promotion",
    "Marriage",
    "Finance",
    "Property / Home",
    "Foreign Travel",
]

# Hardcoded birth data actually used by the engine right now (see
# `birth_data` near the top of bhudeb_d5_engine.py). The engine is
# NOT yet parameterized to accept a different chart from the sidebar
# below — that is a separate, larger integration task. Until that's
# done, the sidebar inputs are for display only unless they match
# this exact chart.
ENGINE_LOCKED_BIRTH = {
    "name": "BHUDEB",
    "date": date(1983, 12, 8),
    "time": time(15, 50),
    "place": "Rourkella, Orissa, India",
}

st.title("🔮 ASTRO-BHUDEB")
st.caption("Kundli & KP Astrology — App Version 1")

with st.sidebar:
    st.header("Birth Details")
    name = st.text_input("Name", ENGINE_LOCKED_BIRTH["name"])
    dob = st.date_input("Date of Birth", ENGINE_LOCKED_BIRTH["date"])
    birth_time = st.time_input("Birth Time", ENGINE_LOCKED_BIRTH["time"])
    place = st.text_input("Birth Place", ENGINE_LOCKED_BIRTH["place"])
    ayanamsha = st.selectbox("Ayanamsha", ["Lahiri"])
    system = st.selectbox("System", ["KP"])

    generate = st.button("🚀 Generate Kundli", use_container_width=True)

    chart_matches_engine = (
        dob == ENGINE_LOCKED_BIRTH["date"]
        and birth_time == ENGINE_LOCKED_BIRTH["time"]
    )

if not chart_matches_engine:
    st.warning(
        "⚠️ **Engine is currently locked to one birth chart** "
        f"({ENGINE_LOCKED_BIRTH['name']}, "
        f"{ENGINE_LOCKED_BIRTH['date'].strftime('%d-%m-%Y')} "
        f"{ENGINE_LOCKED_BIRTH['time'].strftime('%I:%M %p')}, "
        f"{ENGINE_LOCKED_BIRTH['place']}). "
        "The Date/Time you entered in the sidebar does not match — results "
        "below still reflect the locked chart, NOT your entered values. "
        "Making the engine accept arbitrary birth data is a separate, larger "
        "integration task (birth_data is currently a hardcoded dict inside "
        "bhudeb_d5_engine.py)."
    )

if generate:
    st.success("Birth data accepted. Running engine below...")

st.divider()

tabs = st.tabs([
    "Overview", "D1", "D9", "Planets", "KP Cusps",
    "Dasha", "Events", "Prediction"
])

with tabs[0]:
    st.subheader("Birth Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("DOB", dob.strftime("%d-%m-%Y"))
    c2.metric("Time", birth_time.strftime("%I:%M %p"))
    c3.metric("Place", place)
    c4.metric("System", system)

    st.info(
        "App shell is ready. Dasha (MD/AD/PD) and the Universal Event Final "
        "Result are now wired to the real D5 engine — see the **Dasha** and "
        "**Prediction** tabs. D1/D9/Planets/KP Cusps renderers are still "
        "pending engine integration."
    )

with tabs[1]:
    st.subheader("D1 / Rashi Chart")
    st.warning("D1 renderer: pending engine integration.")

with tabs[2]:
    st.subheader("D9 / Navamsha")
    st.warning("D9 renderer: pending engine integration.")

with tabs[3]:
    st.subheader("Planetary Positions")
    st.warning("Planet calculation table: pending engine integration.")

with tabs[4]:
    st.subheader("KP Cusps")
    st.warning("12 Cusp / CSL / Star Lord / Sub Lord table: pending engine integration.")

with tabs[5]:
    st.subheader("Vimshottari Dasha — Transit-Supported Winner")
    try:
        engine = load_engine()
        ranked = getattr(engine, "D520_RANKED", None)
        if ranked:
            winner = ranked[0]
            cand = winner.get("source_candidate", {}) or {}
            c1, c2, c3 = st.columns(3)
            c1.metric("Mahadasha (MD)", cand.get("MD", "—"))
            c2.metric("Antardasha (AD)", cand.get("AD", "—"))
            c3.metric("Pratyantardasha (PD)", cand.get("PD", "—"))
            st.write(f"**Best-supported date:** {winner['date'].strftime('%d-%m-%Y')}")
            st.write(f"**Transit score:** {winner.get('transit_score')} | **Core houses:** {winner.get('core_houses')}")

            st.markdown("##### Next-ranked candidates")
            rows = []
            for row in ranked[1:11]:
                c = row.get("source_candidate", {}) or {}
                rows.append({
                    "Date": row["date"].strftime("%d-%m-%Y"),
                    "MD": c.get("MD", "—"),
                    "AD": c.get("AD", "—"),
                    "PD": c.get("PD", "—"),
                    "Transit Score": row.get("transit_score"),
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.error("D520_RANKED not available from engine — pipeline did not produce results.")
    except Exception as e:
        st.error(f"Engine load/read failed: {type(e).__name__}: {e}")

with tabs[6]:
    st.subheader("Events")
    event = st.selectbox(
        "Select Event",
        ENGINE_EVENT_NAMES,
    )
    st.write(f"Selected event: **{event}**")
    st.caption(
        "Note: the underlying D5.20 transit/dasha computation currently uses "
        "one fixed target-house set (career/promotion houses 6, 10, 11) "
        "regardless of which event is picked here. Making the target houses "
        "swap per-event is a follow-up fix, not yet done."
    )

with tabs[7]:
    st.subheader("Universal Event — Final Result v1")

    event_for_prediction = st.selectbox(
        "Event for Prediction",
        ENGINE_EVENT_NAMES,
        key="prediction_event",
    )

    try:
        engine = load_engine()
        result = engine.build_universal_event_v1(event_for_prediction)

        st.markdown(f"""
### 🔮 FINAL RESULT

**Event:** {result['event']}
**Promise:** {result['promise']}
**Best Period:** {result['best_period']}
**Secondary:** {result['secondary']}
**Key Planet:** {result['key_planet']}
**Trigger:** {result['trigger']}
**Main Reason:** {result['main_reason']}
**Risk:** {result['risk']}
**Remedy:** {result['remedy']}
**Confidence:** {result['confidence']}
""")

        with st.expander("🔍 WHY THIS RESULT? (audit trail)"):
            st.write("`Cusp → CSL → Star Lord → Signification → Dasha → Transit → D9 → Final Score`")
            st.json(result.get("audit", {}))

    except Exception as e:
        st.error(f"build_universal_event_v1() failed: {type(e).__name__}: {e}")
