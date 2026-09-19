import streamlit as st
from datetime import date, time
import importlib.util
import os

# ================================================================
# CHART-DISPLAY HELPERS (D1 / D9 / Planets / KP Cusps)
# ------------------------------------------------------------
# These are pure-Python, additive helpers used ONLY to render the
# UI tables below. They do NOT modify, recompute, or shadow anything
# inside bhudeb_d5_engine.py — they only READ already-computed
# sidereal values off the loaded `engine` module object:
#   engine.sidereal_positions   (dict: planet -> sidereal longitude)
#   engine.sidereal_cusps       (list: 12 sidereal house-cusp longitudes)
#   engine.sidereal_lagna       (float)
#   engine.get_rashi(longitude) (existing engine function)
#   engine.get_kp_sub_lord(lon) (existing engine function)
#   engine.NAKSHATRAS           (existing engine list)
#   engine.house_from_degree(longitude, cusps) (existing engine function)
#
# IMPORTANT — read this before touching the Career/Marriage engine:
# engine.py's OWN internal `planet_kp_sub` / `house_kp_sub` (used by
# the locked Career/Marriage significator chain) are built from
# TROPICAL longitudes, not sidereal — so their star/sub lords do not
# match true KP nakshatra boundaries. That is a pre-existing issue
# inside the locked engine itself (see chat notes) and is NOT touched
# here. The helpers below always compute star/sub lord fresh from
# `sidereal_positions` / `sidereal_cusps`, so the D1/Planets/KP Cusps
# tables shown to the user are astrologically correct even though they
# may occasionally disagree with a number the locked engine derives
# internally for Career/Marriage.
# ================================================================

PLANET_ORDER = [
    "Sun", "Moon", "Mars", "Mercury",
    "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
]

D9_RASHI_NAMES = [
    "Mesha (Aries)", "Vrishabha (Taurus)", "Mithuna (Gemini)", "Karka (Cancer)",
    "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchika (Scorpio)",
    "Dhanu (Sagittarius)", "Makara (Capricorn)", "Kumbha (Aquarius)", "Meena (Pisces)",
]


def _deg_to_dms(deg: float) -> str:
    d = int(deg)
    m_full = (deg - d) * 60
    m = int(m_full)
    s = int(round((m_full - m) * 60))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d}°{m:02d}'{s:02d}\""


def _get_pada(sidereal_longitude: float) -> int:
    nak_size = 360.0 / 27.0
    within = sidereal_longitude % nak_size
    pada = int(within // (nak_size / 4)) + 1
    return min(pada, 4)


def _navamsha_sign_index(sidereal_longitude: float) -> int:
    """Classical Parashari D9 sign-mapping rule. Standalone calculation —
    the underlying engine has no D9 support (confirmed: it explicitly
    prints 'D9 NOT FABRICATED' rather than invent one), so this is
    computed independently in the app layer, not read from the engine."""
    rashi_index = int(sidereal_longitude // 30) % 12
    pos_in_rashi = sidereal_longitude % 30
    nav_num = min(int(pos_in_rashi // (30 / 9)), 8)
    modality = rashi_index % 3  # 0=movable, 1=fixed, 2=dual
    if modality == 0:
        start = rashi_index
    elif modality == 1:
        start = (rashi_index + 8) % 12
    else:
        start = (rashi_index + 4) % 12
    return (start + nav_num) % 12


def build_planet_table(engine, with_navamsha: bool = False):
    rows = []
    for planet in PLANET_ORDER:
        lon = engine.sidereal_positions[planet]
        rashi, deg_in_rashi = engine.get_rashi(lon)
        kp = engine.get_kp_sub_lord(lon)
        nak_name = engine.NAKSHATRAS[kp["nak_index"] - 1]
        house = engine.house_from_degree(lon, engine.sidereal_cusps)
        row = {
            "Planet": planet,
            "Longitude": _deg_to_dms(lon),
            "Rashi": rashi,
            "Deg in Rashi": _deg_to_dms(deg_in_rashi),
            "Nakshatra": nak_name,
            "Pada": _get_pada(lon),
            "Star Lord": kp["star_lord"],
            "Sub Lord": kp["sub_lord"],
            "House": house,
        }
        if with_navamsha:
            row["Navamsha (D9)"] = D9_RASHI_NAMES[_navamsha_sign_index(lon)]
        rows.append(row)
    return rows


def build_cusp_table(engine):
    rows = []
    for house in range(1, 13):
        lon = engine.sidereal_cusps[house - 1]
        rashi, deg_in_rashi = engine.get_rashi(lon)
        kp = engine.get_kp_sub_lord(lon)
        nak_name = engine.NAKSHATRAS[kp["nak_index"] - 1]
        rows.append({
            "House": house,
            "Cusp Longitude": _deg_to_dms(lon),
            "Rashi": rashi,
            "Deg in Rashi": _deg_to_dms(deg_in_rashi),
            "Nakshatra": nak_name,
            "Star Lord (CSL)": kp["star_lord"],
            "Sub Lord": kp["sub_lord"],
        })
    return rows

st.set_page_config(
    page_title="ASTRO-BHUDEB",
    page_icon="🔮",
    layout="wide",
)

# ================================================================
# ENGINE LOADER
# ------------------------------------------------------------
# bhudeb_d5_engine.py is a linear, top-to-bottom computation:
# Mahadasha -> Antardasha -> Pratyantardasha -> KP significators ->
# D5.17..D5.20 transit discrimination -> Career Pipeline Lock ->
# Marriage Analysis Engine V1.0 -> build_universal_final_result().
# Importing it RUNS the whole thing once.
#
# Unlike the previous version, the engine now computes BOTH the
# Career/Promotion result (via the locked V3.0-V3.4 chain) AND the
# Marriage result (via the Marriage Analysis Engine) in a single
# pass — so this only needs to be cached by birth_data, not by
# event. build_universal_final_result(event_name) then just picks
# which already-computed result to hand back.
# ================================================================

ENGINE_PATH = os.path.join(os.path.dirname(__file__), "bhudeb_d5_engine.py")


@st.cache_resource(show_spinner="Running ASTRO-BHUDEB D5 engine (Career + Marriage pipelines)...")
def load_engine(birth_data: dict):
    spec = importlib.util.spec_from_file_location("bhudeb_d5_engine", ENGINE_PATH)
    engine = importlib.util.module_from_spec(spec)
    engine.birth_data = birth_data
    spec.loader.exec_module(engine)
    return engine


ENGINE_EVENT_NAMES = [
    "Career / Promotion",
    "Marriage",
    "Finance",
    "Property / Home",
    "Foreign Travel",
]

# Career/Promotion & Finance run through the locked V3.0-V3.4 chain;
# Marriage runs through its own dedicated Marriage Analysis Engine
# V1.0. Property/Home and Foreign Travel don't have a dedicated
# engine yet, so build_universal_final_result() falls back to the
# generic (but genuinely computed, not faked) D5.18-D5.20 pipeline
# for those two.
DEDICATED_ENGINE_EVENTS = {"Career / Promotion", "Finance", "Marriage"}

DEFAULT_BIRTH = {
    "name": "BHUDEB",
    "date": date(1983, 12, 8),
    "time": time(15, 50),
    "place": "Rourkella, Orissa, India",
    "latitude": 22.22,
    "longitude": 84.87,
    "timezone": 5.5,
}

st.title("🔮 ASTRO-BHUDEB")
st.caption("Kundli & KP Astrology — App Version 1")

with st.sidebar:
    st.header("Birth Details")
    name = st.text_input("Name", DEFAULT_BIRTH["name"])
    dob = st.date_input("Date of Birth", DEFAULT_BIRTH["date"])
    birth_time = st.time_input("Birth Time", DEFAULT_BIRTH["time"])
    place = st.text_input("Birth Place", DEFAULT_BIRTH["place"])

    with st.expander("Coordinates & Timezone", expanded=False):
        st.caption(
            "The engine needs exact latitude/longitude/timezone — it cannot "
            "geocode the place name above on its own. Defaults match the "
            "place field above; edit if you change it."
        )
        latitude = st.number_input(
            "Latitude", value=float(DEFAULT_BIRTH["latitude"]),
            format="%.4f", step=0.01,
        )
        longitude = st.number_input(
            "Longitude", value=float(DEFAULT_BIRTH["longitude"]),
            format="%.4f", step=0.01,
        )
        timezone_offset = st.number_input(
            "Timezone offset (hours from UTC)",
            value=float(DEFAULT_BIRTH["timezone"]),
            format="%.2f", step=0.5,
        )

    ayanamsha = st.selectbox("Ayanamsha", ["Lahiri"])
    system = st.selectbox("System", ["KP"])

    generate = st.button("🚀 Generate Kundli", use_container_width=True)

    st.divider()
    st.header("Life Events — Already Occurred?")
    st.caption(
        "The engine has no idea whether an event already happened — it "
        "only matches houses/dasha/transit. Mark events that already "
        "occurred so the app can add an honest caveat instead of "
        "presenting a future prediction for something already in the past."
    )

    OCCURRED_DEFAULTS = {
        "Marriage": date(2013, 3, 13),
    }

    occurred_events = {}
    for _event_name in ENGINE_EVENT_NAMES:
        _default_checked = _event_name in OCCURRED_DEFAULTS
        _checked = st.checkbox(
            f"{_event_name} — already occurred",
            value=_default_checked,
            key=f"occurred_{_event_name}",
        )
        if _checked:
            _default_date = OCCURRED_DEFAULTS.get(_event_name, date.today())
            _occurred_date = st.date_input(
                f"When? ({_event_name})",
                value=_default_date,
                key=f"occurred_date_{_event_name}",
            )
            occurred_events[_event_name] = _occurred_date

# Build the exact dict shape the engine expects (date/time as strings).
birth_data = {
    "name": name or DEFAULT_BIRTH["name"],
    "date": dob.strftime("%Y-%m-%d"),
    "time": birth_time.strftime("%H:%M:%S"),
    "place": place or DEFAULT_BIRTH["place"],
    "latitude": latitude,
    "longitude": longitude,
    "timezone": timezone_offset,
}

if generate:
    st.success("Birth data accepted — engine below now runs for this chart.")

st.divider()


def show_occurred_caveat(event_name: str):
    """Shows an honest caveat when the selected event is marked as
    already occurred — the engine has no concept of 'already happened'
    and will still return a matching house/dasha/transit window, which
    is easy to misread as a future prediction."""
    if event_name in occurred_events:
        occurred_on = occurred_events[event_name]
        st.info(
            f"ℹ️ You've marked **{event_name}** as already occurred "
            f"(on {occurred_on.strftime('%d-%m-%Y')}). The engine below "
            f"doesn't know that — it will still return a best-matching "
            f"house/dasha/transit window regardless. Read the result "
            f"below as **'{event_name}'-house-related timing** (a "
            f"related development, not necessarily the event itself), "
            f"not as a prediction that {event_name.lower()} will happen "
            f"again."
        )


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
        "Dasha (MD/AD/PD), Career/Promotion (locked V3.4 chain), and "
        "Marriage (Marriage Analysis Engine V1.0) are wired to the real "
        "D5 engine and use the birth details entered in the sidebar — "
        "see the **Dasha** and **Prediction** tabs. D1, Planets, and KP "
        "Cusps are now wired to the engine's sidereal positions/cusps. "
        "D9/Navamsha is computed independently in the app (classical "
        "Parashari formula) since the engine itself does not compute one."
    )

with tabs[1]:
    st.subheader("D1 / Rashi Chart")
    try:
        engine = load_engine(birth_data)
        c1, c2, c3 = st.columns(3)
        c1.metric("Lagna (Ascendant)", engine.lagna_rashi.split(" (")[0])
        c2.metric("Lagna Degree", f"{engine.lagna_degree:.2f}°")
        c3.metric("Moon Rashi", engine.moon_rashi.split(" (")[0])

        st.markdown("##### 12 House Cusps")
        st.dataframe(
            [{k: v for k, v in row.items() if k in
              ("House", "Cusp Longitude", "Rashi", "Deg in Rashi")}
             for row in build_cusp_table(engine)],
            use_container_width=True, hide_index=True,
        )

        st.markdown("##### Planets — Sign & House")
        st.dataframe(
            [{k: v for k, v in row.items() if k in
              ("Planet", "Rashi", "Deg in Rashi", "House")}
             for row in build_planet_table(engine)],
            use_container_width=True, hide_index=True,
        )
    except Exception as e:
        st.error(f"D1 render failed: {type(e).__name__}: {e}")

with tabs[2]:
    st.subheader("D9 / Navamsha")
    st.caption(
        "The D5 engine itself has no Navamsha computation (it explicitly "
        "avoids fabricating one). This chart is computed independently "
        "here using the standard classical Parashari D9 sign-mapping "
        "rule, applied to the same sidereal positions the engine already "
        "computed — no invented data."
    )
    try:
        engine = load_engine(birth_data)
        nav_lagna_idx = _navamsha_sign_index(engine.sidereal_lagna)
        st.metric("Navamsha Lagna", D9_RASHI_NAMES[nav_lagna_idx])

        st.markdown("##### Planets in Navamsha (D9)")
        rows = build_planet_table(engine, with_navamsha=True)
        st.dataframe(
            [{k: v for k, v in row.items() if k in ("Planet", "Rashi", "Navamsha (D9)")}
             for row in rows],
            use_container_width=True, hide_index=True,
        )
    except Exception as e:
        st.error(f"D9 render failed: {type(e).__name__}: {e}")

with tabs[3]:
    st.subheader("Planetary Positions")
    try:
        engine = load_engine(birth_data)
        st.dataframe(build_planet_table(engine), use_container_width=True, hide_index=True)
        st.caption(
            "Sidereal (Lahiri) positions. Star/Sub Lord computed fresh "
            "from these sidereal longitudes for display accuracy."
        )
    except Exception as e:
        st.error(f"Planets render failed: {type(e).__name__}: {e}")

with tabs[4]:
    st.subheader("KP Cusps")
    try:
        engine = load_engine(birth_data)
        st.dataframe(build_cusp_table(engine), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"KP Cusps render failed: {type(e).__name__}: {e}")

with tabs[5]:
    st.subheader("Vimshottari Dasha — Transit-Supported Winner")
    try:
        engine = load_engine(birth_data)
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
    show_occurred_caveat(event)
    if event in DEDICATED_ENGINE_EVENTS:
        st.caption(
            f"'{event}' has a dedicated engine "
            + ("(locked V3.0-V3.4 Career chain)." if event != "Marriage"
               else "(Marriage Analysis Engine V1.0 — 12-step promise/"
                    "delay/love-vs-arranged/timing analysis).")
        )
    else:
        st.caption(
            f"'{event}' doesn't have a dedicated engine yet — the "
            f"Prediction tab uses the generic D5.18-D5.20 significator "
            f"pipeline (genuinely computed for this event's houses, "
            f"just without the extra promise/delay/love-vs-arranged "
            f"layers that Career and Marriage have)."
        )

with tabs[7]:
    st.subheader("Universal Final Result")

    event_for_prediction = st.selectbox(
        "Event for Prediction",
        ENGINE_EVENT_NAMES,
        key="prediction_event",
    )

    show_occurred_caveat(event_for_prediction)

    try:
        engine = load_engine(birth_data)
        result = engine.build_universal_final_result(event_for_prediction)

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

        audit = result.get("audit", {})
        st.caption(f"Source: {audit.get('source', '—')}")

        with st.expander("🔍 WHY THIS RESULT? (audit trail)"):
            st.json(audit)

    except Exception as e:
        st.error(f"build_universal_final_result() failed: {type(e).__name__}: {e}")
