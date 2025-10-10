# app.py
from pathlib import Path
import sys
import datetime as dt

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------------------------------------------------------
# App config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Pain Relief Map — Evidence Explorer + N-of-1",
    layout="wide",
)

# Root for relative paths
ROOT = Path(__file__).resolve().parents[1]

# Ensure local imports resolve if needed
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# -----------------------------------------------------------------------------
# Data loading (supports data/evidence_counts.csv and data/raw/evidence_counts.csv)
# -----------------------------------------------------------------------------

def _locate_evidence_csv() -> Path | None:
    here = ROOT / "data"
    candidates = [
        here / "evidence_counts.csv",
        here / "raw" / "evidence_counts.csv",
        ROOT / "evidence_counts.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

@st.cache_data
def load_evidence() -> pd.DataFrame:
    csv_path = _locate_evidence_csv()
    if csv_path is None:
        st.error(
            "I couldn’t find **evidence_counts.csv**.\n\n"
            "Looked in:\n"
            "- `data/evidence_counts.csv`\n"
            "- `data/raw/evidence_counts.csv`\n"
            "- repo root\n\n"
            "Fix by either moving your file to `data/evidence_counts.csv` "
            "or keep it in `data/raw/` — this loader now supports both."
        )
        st.stop()

    df = pd.read_csv(csv_path)

    # Standardize key columns if they exist
    if "condition" in df.columns:
        df["condition"] = df["condition"].astype(str).str.title()
    if "therapy" in df.columns:
        df["therapy"] = df["therapy"].astype(str).str.title()
    if "evidence_direction" in df.columns:
        df["evidence_direction"] = df["evidence_direction"].astype(str).str.strip().str.capitalize()

    return df

# Load once
evidence = load_evidence()

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def complete_grid(sub: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Ensure all therapies for the condition appear; fill missing counts with 0."""
    base = evidence.query("condition == @condition")
    if base.empty:
        return sub
    therapy_col = "therapy"
    required = pd.DataFrame({therapy_col: sorted(base[therapy_col].dropna().unique())})
    sub = required.merge(sub, how="left", on=therapy_col)
    for c in ("clinicaltrials_n", "pubmed_n"):
        if c in sub.columns:
            sub[c] = sub[c].fillna(0)
    # carry over urls if provided in df
    for c in ("trials_url", "articles_url"):
        if c in sub.columns and c not in base.columns:
            sub[c] = sub[c].fillna(pd.NA)
    return sub

# -----------------------------------------------------------------------------
# Heading: app Heading
# -----------------------------------------------------------------------------
st.title("💆🏻‍♀️ Pain Relief Map — Explore Evidence & Track What Works for You")


# -----------------------------------------------------------------------------
# Sidebar: filters (unified)
# -----------------------------------------------------------------------------

def _explode_unique(df, colname):
    if colname not in df.columns:
        return []
    s = df[colname].dropna().astype(str)
    s = s.str.replace(r"\s*[,;]\s*", "|", regex=True).str.split("|")
    return sorted({v.strip() for lst in s for v in (lst or []) if v.strip()})

def _contains_any(df, col, selected):
    import re
    if not selected or col not in df.columns:
        return pd.Series(True, index=df.index)
    pattern = "|".join([rf"(?i)\\b{re.escape(x)}\\b" for x in selected])
    return df[col].fillna("").astype(str).str.contains(pattern, regex=True)

_def_num = lambda s: pd.to_numeric(s, errors="coerce")

# Defaults - use comprehensive condition list
cond_options = [
    "Addiction", "Anxiety", "Burnout", "Cancer Pain", "Chronic Fatigue Syndrome", 
    "Chronic Pain", "Depression", "Eating Disorders", "Endometriosis", "Fibromyalgia", "Headache", 
    "Infertility", "Insomnia", "Irritable Bowel Syndrome", "Knee Pain", "Low Back Pain", "Menopause", 
    "Migraine", "Myofascial Pain", "Neck Pain", "Neuropathic Pain", "Obsessive-Compulsive Disorder", 
    "Osteoarthritis", "Perimenopause", "Polycystic Ovary Syndrome", "Post-Traumatic Stress Disorder", 
    "Postoperative Pain", "Rheumatoid Arthritis", "Schizophrenia", "Shoulder Pain", "Stress"
]
default_condition = "Anxiety"


# --- safer year bounds ---
if "year_min" in evidence:
    ymins = pd.to_numeric(evidence["year_min"], errors="coerce")
    year_lo = int(np.nanmin(ymins)) if not ymins.dropna().empty else 1990
else:
    year_lo = 1990

if "year_max" in evidence:
    ymaxs = pd.to_numeric(evidence["year_max"], errors="coerce")
    year_hi = int(np.nanmax(ymaxs)) if not ymaxs.dropna().empty else dt.date.today().year
else:
    year_hi = dt.date.today().year

# Default to last 15 years from current year
current_year = dt.date.today().year
default_lo = max(year_lo, current_year - 15)

# Evidence direction: provide all options with Positive selected by default
evdir_opts = ["Positive", "Mixed", "Negative", "Unclear"]
default_evdir = ["Positive"]

with st.sidebar:
    st.markdown("### Filters")

    conditions = st.multiselect("Conditions", options=cond_options, default=[default_condition] if default_condition in cond_options else [])

    # Comprehensive therapy list
    therapy_opts = [
        "Acupuncture", "Aromatherapy", "Ayurveda", "Cognitive Behavioural Therapy", 
        "Exercise Therapy", "Herbal", "Massage", "Meditation", "Qi Gong", "Tai Chi", "Yoga"
    ]
    # Default to all therapies (excluding "None")
    therapies = st.multiselect("Therapies", options=therapy_opts, default=therapy_opts)

    yr = st.slider("Year range", min_value=year_lo, max_value=year_hi, value=(default_lo, current_year))

    sel_evdir = st.multiselect("Evidence direction", options=evdir_opts, default=default_evdir)

    sort_choice = st.radio("Sort by", options=["Most trials", "Most PubMed", "Newest first"], index=0)
    
    st.markdown("### 🔠 Therapy Order")
    therapy_sort_choice = st.radio(
        "Sort bars by",
        ["Trials (desc)", "PubMed (desc)", "Alphabetical"],
        index=0,
        help="Change bar order for readability; data doesn't change."
    )

# Apply filters to build f and f_sorted
f = evidence.copy()

if "condition" in f.columns and conditions:
    f = f[f["condition"].isin(conditions)]
if therapies and "therapy" in f.columns:
    f = f[f["therapy"].isin(therapies)]

if "year_min" in f.columns: f["year_min"] = _def_num(f["year_min"])
if "year_max" in f.columns: f["year_max"] = _def_num(f["year_max"])
if "year_min" in f.columns or "year_max" in f.columns:
    ymin = f["year_min"].fillna(f["year_max"]).fillna(year_lo)
    ymax = f["year_max"].fillna(f["year_min"]).fillna(year_hi)
    f = f[(ymax >= yr[0]) & (ymin <= yr[1])]

# Filter by evidence direction if user has made a selection
if sel_evdir and "evidence_direction" in f.columns:
    f = f[f["evidence_direction"].isin(sel_evdir)]


def _sort_df(df, how):
    df = df.copy()
    if how == "Most trials" and "clinicaltrials_n" in df.columns:
        return df.sort_values("clinicaltrials_n", ascending=False, na_position="last")
    if how == "Most PubMed" and "pubmed_n" in df.columns:
        return df.sort_values("pubmed_n", ascending=False, na_position="last")
    if how == "Newest first" and "year_max" in df.columns:
        return df.sort_values("year_max", ascending=False, na_position="last")
    return df

f_sorted = _sort_df(f, sort_choice)

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tab_dash, tab_log = st.tabs([
    "📈 Evidence Explorer",
    "🌿 Daily Wellness Log (N-of-1)"
])


# -----------------------------------------------------------------------------
# Sort helper for bar charts (UI for per-chart order)
# -----------------------------------------------------------------------------

def apply_therapy_sort(df: pd.DataFrame, sort_choice: str, therapy_col: str = "therapy") -> pd.DataFrame:
    """Apply therapy sorting based on user's choice."""
    if sort_choice == "Alphabetical":
        return df.sort_values(therapy_col)
    
    # Determine which column to sort by
    sort_col = None
    if sort_choice == "Trials (desc)" and "clinicaltrials_n" in df.columns:
        sort_col = "clinicaltrials_n"
    elif sort_choice == "PubMed (desc)" and "pubmed_n" in df.columns:
        sort_col = "pubmed_n"
    elif "clinicaltrials_n" in df.columns:
        # Fallback to trials if available
        sort_col = "clinicaltrials_n"
    elif "pubmed_n" in df.columns:
        # Fallback to pubmed if available
        sort_col = "pubmed_n"
    else:
        # No numeric column to sort by, return alphabetically
        return df.sort_values(therapy_col)
    
    order = (
        df.groupby(therapy_col)[sort_col]
          .sum().sort_values(ascending=False).index.tolist()
    )

    out = df.copy()
    out[therapy_col] = pd.Categorical(out[therapy_col], categories=order, ordered=True)
    return out

# -----------------------------------------------------------------------------
# Evidence Explorer tab (now wired to f_sorted)
# -----------------------------------------------------------------------------

with tab_dash:
    # Use fully filtered dataset
    base = f_sorted.copy()
    if conditions and therapies:
        base = base[base["therapy"].isin(therapies)]

    # Use filtered data directly (respect user's therapy selection)
    plot_df = base

    # If nothing matches, show a friendly hint and stop
    if plot_df.empty:
        st.info(
            "No results match the current filters. "
            "Try clearing some filters, widening the year range, or removing Evidence direction.",
            icon="🔍"
        )
        st.stop()

    # KPIs for current selection
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Conditions selected",
        f"{len(conditions):,}"
    )
    k2.metric(
        "Therapies selected",
        f"{(len(therapies) if therapies else plot_df['therapy'].nunique() if 'therapy' in plot_df else 0):,}"
    )
    k3.metric(
        "Trials (selected)",
        f"{int(pd.to_numeric(plot_df.get('clinicaltrials_n', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()):,}"
    )
    k4.metric(
        "PubMed (selected)",
        f"{int(pd.to_numeric(plot_df.get('pubmed_n', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()):,}"
    )

    # Charts (respect sidebar sort helper)
    plot_df = apply_therapy_sort(plot_df, therapy_sort_choice)

    # Use color by condition if multiple conditions selected
    color_by_condition = "condition" if len(conditions) > 1 and "condition" in plot_df.columns else None

    c1, c2 = st.columns(2)
    with c1:
        fig1 = px.bar(plot_df, x="therapy", y="clinicaltrials_n", color=color_by_condition, 
                      title="Clinical trials by therapy")
        fig1.update_layout(barmode="stack")
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        fig2 = px.bar(plot_df, x="therapy", y="pubmed_n", color=color_by_condition,
                      title="PubMed articles by therapy")
        fig2.update_layout(barmode="stack")
        st.plotly_chart(fig2, use_container_width=True)

# --- Evidence direction summary (filtered) ---
    if "evidence_direction" in plot_df.columns:
        ed_counts = (
            plot_df["evidence_direction"]
            .dropna()
            .value_counts()
            .rename_axis("evidence_direction")
            .reset_index(name="count")
        )

        if not ed_counts.empty:
            st.subheader("Evidence direction (filtered view)")

            # 💚 color scheme for clarity
            color_map = {
                "Positive": "#2ecc71",  # green
                "Negative": "#e74c3c",  # red
                "Mixed": "#f1c40f",     # yellow
                "Unclear": "#95a5a6",   # gray
            }

            # 📊 calculate percentage column
            ed_counts["percent"] = 100 * ed_counts["count"] / ed_counts["count"].sum()

            # 📈 render the chart (percentage view)
            st.plotly_chart(
                px.bar(
                    ed_counts,
                    x="evidence_direction",
                    y="percent",
                    text_auto=".1f",
                    color="evidence_direction",
                    color_discrete_map=color_map,
                    title="Evidence direction (% of studies within current filters)",
                ).update_layout(showlegend=False),
                use_container_width=True,
            )

        else:
            st.info("No evidence_direction data found for the current filters.", icon="ℹ️")


        # Table with links
        st.markdown("### Details")
        show_cols = [c for c in ["condition","therapy","clinicaltrials_n","pubmed_n","trials_url","articles_url","last_updated"] if c in plot_df.columns]
        st.dataframe(
            plot_df[show_cols].sort_values(["therapy"]) if not plot_df.empty else plot_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "trials_url": st.column_config.LinkColumn("Trials 🔗"),
                "articles_url": st.column_config.LinkColumn("Articles 🔗"),
            },
        )

        # Data dictionary
        st.markdown("### 📚 Data dictionary")
        dd = pd.DataFrame({
            "field": [
                "condition", "therapy", "clinicaltrials_n", "pubmed_n", "year_min", "year_max",
                "study_types", "countries", "evidence_direction", "effect_size_estimate",
                "quality_rating", "sample_size_min", "source", "last_updated"
            ],
            "description": [
                "Clinical condition (e.g., Fibromyalgia)",
                "Therapy/intervention name",
                "Count of ClinicalTrials.gov matches",
                "Count of PubMed matches",
                "Earliest study year",
                "Latest study year",
                "Aggregated study designs (if present)",
                "Aggregated countries (if present)",
                "Summary of effect direction (optional)",
                "Numeric effect size summary (optional)",
                "Evidence quality band (optional)",
                "Minimum total sample size (optional)",
                "Data source tag",
                "ETL timestamp for reproducibility",
            ]
        })
        st.dataframe(dd, use_container_width=True, hide_index=True)

    st.divider()

# -----------------------------------------------------------------------------
# N-of-1: Daily Wellness Log 
# -----------------------------------------------------------------------------
with tab_log:
    st.subheader("🌱 Daily Wellness Log")
    st.markdown("""
    Record how you feel each day — pain, sleep, stress, movement, digestion, and therapy use — to discover what helps you most.
    """)
    st.caption("N-of-1 Tracking: this approach treats each person as their own control, tracking changes in symptoms **before vs after** starting a therapy.")
    st.write("")

    # ---- Dataframe in session_state (original columns) ----
    DEFAULT_COLS = [
        "date", "sex_at_birth", "condition_today", "therapy_used",
        "pain_score", "sleep_hours", "stress_score", "mood_score",
        "movement", "digestive_sounds", "bowel_movements_n", "stool_consistency",
        "physical_symptoms", "emotional_symptoms",
        "patience_score", "anxiety_score", "cravings",
        "menstruating_today", "cycle_day", "flow", "pms_symptoms",
        "good_day",
    ]

    if "n1_df" not in st.session_state:
        st.session_state.n1_df = pd.DataFrame(columns=DEFAULT_COLS)

    def _get_latest_row():
        if st.session_state.n1_df.empty:
            return None
        df = st.session_state.n1_df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df.sort_values("date").iloc[-1]

    def _defaults_from_yesterday():
        last = _get_latest_row()
        if last is None:
            return dict(pain_score=0, stress_score=0, sleep_hours=7, mood_score=5)
        return dict(
            pain_score=float(last.get("pain_score", 0.0)),
            stress_score=float(last.get("stress_score", 0.0)),
            sleep_hours=float(last.get("sleep_hours", 7.0)),
            mood_score=float(last.get("mood_score", 5.0)),
        )

    def _append_row(row: dict):
        rec = {
            "date": pd.to_datetime(row["date"]),
            "sex_at_birth": row.get("sex_at_birth"),
            "condition_today": ", ".join(row.get("condition_today", [])),
            "therapy_used": ", ".join(row.get("therapy_used", [])),
            "pain_score": float(row["pain_score"]),
            "sleep_hours": float(row["sleep_hours"]),
            "stress_score": float(row["stress_score"]),
            "mood_score": float(row["mood_score"]),
            "movement": ", ".join(row.get("movement", [])),
            "digestive_sounds": row.get("digestive_sounds"),
            "bowel_movements_n": int(row.get("bowel_movements_n", 0)),
            "stool_consistency": row.get("stool_consistency"),
            "physical_symptoms": ", ".join(row.get("physical_symptoms", [])),
            "emotional_symptoms": ", ".join(row.get("emotional_symptoms", [])),
            "patience_score": float(row.get("patience_score", 5)),
            "anxiety_score": float(row.get("anxiety_score", 5)),
            "cravings": ", ".join(row.get("cravings", [])),
            "menstruating_today": (row.get("menstruating_today") in ["Yes", True]),
            "cycle_day": int(row.get("cycle_day") or 0),
            "flow": row.get("flow"),
            "pms_symptoms": ", ".join(row.get("pms_symptoms", [])),
            "good_day": bool(row.get("good_day", False)),
        }
        st.session_state.n1_df = pd.concat(
            [st.session_state.n1_df, pd.DataFrame([rec])],
            ignore_index=True
        )


    # Optional: gentle nudge until we have 7 days of data
    n_days = len(st.session_state.n1_df["date"].unique()) if not st.session_state.n1_df.empty else 0
    if n_days < 7:
        st.info("Add a few days to see your 7-day trend here.", icon="💡")

    # ===== Outside-the-form Action Bar (column layout; matches screenshot) =====

    st.session_state.setdefault("good_day", False)
    st.session_state.setdefault("track_cycle", True)
    st.session_state.setdefault("quick_notes", [])

    # left cluster (3 items) + flexible spacer + right toggle
    # leave col_spacer empty

    with st.container(border=True):
        col_dup, col_note, col_good, col_spacer, col_cycle = st.columns(
            [2.2, 2.2, 2.2, 6.0, 2.6],  # tweak these until it looks right
            gap="small"
        )

        # 🌿 Duplicate yesterday
        with col_dup:
            if st.button("🌿 Duplicate yesterday", key="dup_yesterday_bar2",
                        help="Copy yesterday’s values to today"):
                last = _get_latest_row()
                if last is None:
                    st.warning("No previous day to duplicate yet. Add your first entry below.")
                else:
                    today = dt.date.today()
                    tmp = st.session_state.n1_df.copy()
                    tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce").dt.date
                    if today in set(tmp["date"]):
                        st.info("You already have an entry for today.")
                    else:
                        dup = last.to_dict()
                        dup["date"] = today
                        _append_row(dup)
                        st.success("Duplicated yesterday’s values to today!")

        # 📝 Quick note — popover if available, else expander
        with col_note:
            if hasattr(st, "popover"):
                with st.popover("📝 Quick note", use_container_width=True):
                    note = st.text_area("Note for today", key="quick_note_text2")
                    cna, cnb = st.columns(2)
                    if cna.button("Save", key="quick_note_save2"):
                        if note.strip():
                            st.session_state.quick_notes.append(
                                {"date": dt.date.today().isoformat(), "note": note.strip()}
                            )
                            st.success("Note saved.")
                    if cnb.button("Clear", key="quick_note_clear2"):
                        st.session_state["quick_note_text2"] = ""
            else:
                with st.expander("📝 Quick note", expanded=False):
                    note = st.text_area("Note for today", key="quick_note_text2")
                    cna, cnb = st.columns(2)
                    if cna.button("Save", key="quick_note_save2"):
                        if note.strip():
                            st.session_state.quick_notes.append(
                                {"date": dt.date.today().isoformat(), "note": note.strip()}
                            )
                            st.success("Note saved.")
                    if cnb.button("Clear", key="quick_note_clear2"):
                        st.session_state["quick_note_text2"] = ""

        # ☺️ Mark good day toggle
        with col_good:
            st.session_state["good_day"] = st.toggle(
                "☺️ Mark good day", value=st.session_state["good_day"], key="good_day_toggle2"
            )

        # (col_spacer is just spacing)

        # 🔴 Track menstrual cycle (right-aligned)
        with col_cycle:
            st.session_state["track_cycle"] = st.toggle(
                "Track menstrual cycle",
                value=st.session_state["track_cycle"],
                key="track_cycle_toggle2",
                help="Include cycle info in your daily entries."
            )

    # simple mapping used by the form below
    st.session_state.setdefault("sex_at_birth", "Female")
    is_female = st.session_state["track_cycle"]
    st.session_state["sex_at_birth"] = "Female" if is_female else "Male"


    # ---- Options (same as your original) ----

    condition_options = [
        "None", "Addiction", "Anxiety", "Burnout", "Cancer Pain", "Chronic Fatigue Syndrome", 
        "Chronic Pain", "Depression", "Eating Disorders", "Endometriosis", "Fibromyalgia", "Headache", 
        "Infertility", "Insomnia", "Irritable Bowel Syndrome", "Knee Pain", "Low Back Pain", "Menopause", 
        "Migraine", "Myofascial Pain", "Neck Pain", "Neuropathic Pain", "Obsessive-Compulsive Disorder", 
        "Osteoarthritis", "Perimenopause", "Polycystic Ovary Syndrome", "Post-Traumatic Stress Disorder", 
        "Postoperative Pain", "Rheumatoid Arthritis", "Schizophrenia", "Shoulder Pain", "Stress"
    ]
    therapy_options= [
        "None", "Acupuncture", "Aromatherapy", "Ayurveda", "Cognitive Behaviour Therapy", "Exercise Therapy", 
        "Herbal", "Massage", "Meditation", "Qi Gong", "Tai Chi", "Yoga"
    ]
    movement_options = [
        "None / Rest day", "Light stretching or yoga", "Walking or gentle movement",
        "Light cardio", "Moderate workout", "High-intensity training",
        "Physical therapy or rehab", "Unusually active day"
    ]
    digestive_options = [
        "Select...", "Normal occasional rumbles", "Very quiet/no sounds noticed",
        "Frequent loud rumbling", "Excessive gurgling", "Rumbling increases when anxious"
    ]
    stool_options = [
        "Select...", "Type 1: Hard lumps", "Type 2: Lumpy sausage", "Type 3: Sausage with cracks",
        "Type 4: Smooth sausage (ideal)", "Type 5: Soft blobs", "Type 6: Mushy", "Type 7: Liquid"
    ]
    physical_options = [
        "None", "Brain fog", "Digestive discomfort", "Dizziness", "Fatigue", "Headache",
        "Joint pain", "Muscle pain", "Nausea", "Sensitivity to temperature", "Tingling"
    ]
    emotional_options = [
        "None", "Anxious", "Calm", "Emotionally numb", "Felt tearful / cried",
        "Grateful", "Hopeful", "Irritable", "Lonely", "Overwhelmed", "Sad"
    ]
    craving_options = [
        "None", "Sugar", "Carbs", "Salty snacks", "Caffeine", "Alcohol", "Nicotine", "Comfort food"
    ]


    # ---- Form (cleaned) with Sex at birth + conditional menstrual tracking + cravings ----
    defs = _defaults_from_yesterday()

    # Menstrual options (kept local to this block for portability)
    pms_options = [
        "None","Cramps","Bloating","Breast tenderness","Headache","Irritability",
        "Low mood","Anxiety","Fatigue","Food cravings"
    ]
    flow_options = ["None","Light","Medium","Heavy"]

    with st.form("n1_entry_form", clear_on_submit=False):
        # Row 1: Date only (sex is outside the form)
        c1a, _ = st.columns(2)
        with c1a:
            f_date = st.date_input("Today's date:", value=dt.date.today(), format="DD/MM/YYYY")

        # Row 2: Conditions today + Therapies used
        c3, c4 = st.columns(2)
        with c3:
            f_condition_today = st.multiselect(
                "Conditions felt today",
                options=condition_options,
                default=["None"],
                help="Select all conditions experienced today."
            )
        with c4:
            f_therapy_used = st.multiselect(
                "Therapy used today",
                options=therapy_options,
                help="Select all therapies you used today."
            )

        # Row 3: Sleep + Mood
        c5, c6 = st.columns(2)
        with c5:
            f_sleep = st.slider("Sleep hours last night", 0, 14, int(round(defs["sleep_hours"])))
        with c6:
            f_mood = st.slider("Overall mood (0–10)", 0, 10, int(round(defs["mood_score"])))

        # ---- Conditional Menstrual Tracking (only if Female) ----
        if is_female:
            st.markdown("### 🩸 Hormonal Cycle")
            hc1, hc2, hc3, hc4 = st.columns(4)
            with hc1:
                f_menstruating = st.radio("Menstruating today?", ["No", "Yes"], index=0)
            with hc2:
                f_cycle_day = st.number_input("Cycle day", min_value=1, max_value=40, value=1, step=1)
            with hc3:
                f_flow = st.selectbox("Flow", ["None", "Light", "Medium", "Heavy"], index=0)
            with hc4:
                f_pms = st.multiselect(
                    "PMS symptoms",
                    ["None", "Cramps", "Bloating", "Breast tenderness", "Headache", "Irritability", "Low mood", "Anxiety", "Fatigue", "Food cravings"],
                    default=["None"]
                )
        else:
            f_menstruating = "No"
            f_cycle_day = 0
            f_flow = "None"
            f_pms = ["None"]

        # ---- Core Symptoms ----
        st.markdown("### ❤️ Core Symptoms")
        c7, c8 = st.columns(2)
        with c7:
            f_pain = st.slider("Pain (0–10)", 0, 10, int(round(defs["pain_score"])))
        with c8:
            f_stress = st.slider("Stress (0–10)", 0, 10, int(round(defs["stress_score"])))

        c9, c10 = st.columns(2)
        with c9:
            f_anxiety = st.slider("Anxiety (0–10)", 0, 10, 5)
        with c10:
            f_patience = st.slider("Patience (0–10)", 0, 10, 5)

        # ---- Emotional & Physical Symptoms + Cravings ----
        st.markdown("### 💭 Emotional and Physical Symptoms")
        c11, c12 = st.columns(2)
        with c11:
            f_emotional = st.multiselect("Emotional symptoms:", emotional_options)
        with c12:
            f_physical = st.multiselect("Physical symptoms:", physical_options)

        f_cravings = st.multiselect(
            "Cravings today:",
            craving_options,
            default=["None"]
        )

        # ---- Physical State ----
        st.markdown("### 🏃‍♀️ Physical State")
        c13, c14 = st.columns(2)
        with c13:
            f_movement = st.multiselect("Movement today:", movement_options)
        with c14:
            f_bowel = st.slider("Bowel movements (0–10)", 0, 10, 1)

        c15, c16 = st.columns(2)
        with c15:
            f_digestive = st.selectbox("Digestive sounds:", digestive_options, index=0)
        with c16:
            f_stool = st.selectbox("Stool consistency:", stool_options, index=0)

        # ---- Submit ----
        add_clicked = st.form_submit_button("Submit", type="primary")
        if add_clicked:
            _append_row({
                "date": f_date,
                "sex_at_birth": st.session_state["sex_at_birth"],  # value from toggle
                "condition_today": f_condition_today,
                "therapy_used": f_therapy_used,
                "pain_score": f_pain,
                "sleep_hours": f_sleep,
                "stress_score": f_stress,
                "mood_score": f_mood,
                "movement": f_movement,
                "digestive_sounds": f_digestive,
                "bowel_movements_n": f_bowel,
                "stool_consistency": f_stool,
                "physical_symptoms": f_physical,
                "emotional_symptoms": f_emotional,
                "patience_score": f_patience,
                "anxiety_score": f_anxiety,
                "cravings": f_cravings,
                "menstruating_today": f_menstruating,
                "cycle_day": f_cycle_day,
                "flow": f_flow,
                "pms_symptoms": f_pms,
                "good_day": st.session_state.get("good_day", False),
            })
            st.success("Row added!")


    # ==== Show data (with ☺️ badge when good_day=True) ====
    if not st.session_state.n1_df.empty:
        df_show = st.session_state.n1_df.copy()
        df_show["date"] = pd.to_datetime(df_show["date"], errors="coerce").dt.date

        # Use ☺️ instead of ⭐
        df_show["☺️"] = df_show["good_day"].fillna(False).map(lambda x: "☺️" if bool(x) else "")

        preferred = [c for c in [
            "☺️", "date", "pain_score", "stress_score", "sleep_hours", "mood_score",
            "therapy_used", "condition_today", "movement", "cravings", "menstruating_today"
        ] if c in df_show.columns]
        others = [c for c in df_show.columns if c not in preferred and c != "good_day"]  # hide raw bool

        st.dataframe(
            df_show[preferred + others],
            use_container_width=True,
            hide_index=True,
            column_config={
                "☺️": st.column_config.TextColumn("", help="Marked as a good day"),
                "menstruating_today": st.column_config.CheckboxColumn("Menstruating", disabled=True),
            },
        )
    else:
        st.info("No rows yet — add your first day above or use “Duplicate yesterday” after your first entry.")
