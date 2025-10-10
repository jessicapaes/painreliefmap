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

# Mobile-responsive CSS
st.markdown("""
<style>
    /* Mobile-first responsive design */
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem;
        }
        
        /* Make forms more compact on mobile */
        .stForm {
            padding: 0.5rem;
        }
        
        /* Stack columns vertically on mobile */
        [data-testid="column"] {
            width: 100% !important;
            flex: 100% !important;
            min-width: 100% !important;
        }
        
        /* Make buttons full-width on mobile */
        .stButton > button {
            width: 100%;
        }
        
        /* Reduce metric font size */
        [data-testid="stMetricValue"] {
            font-size: 1.2rem;
        }
        
        /* Make multiselect more compact */
        .stMultiSelect {
            font-size: 0.9rem;
        }
        
        /* Reduce padding in containers */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] {
            gap: 0.5rem;
        }
    }
    
    /* Tablet optimization */
    @media (min-width: 769px) and (max-width: 1024px) {
        [data-testid="column"] {
            min-width: 48% !important;
        }
    }
    
    /* Improve readability on all devices */
    .stMarkdown p {
        line-height: 1.6;
    }
    
    /* Better touch targets for mobile */
    .stCheckbox, .stRadio {
        min-height: 44px;
    }
</style>
""", unsafe_allow_html=True)

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
    st.markdown("### 🏠 Navigation")
    st.markdown("""
    Welcome to Pain Relief Map! 
    
    Use the tabs above to:
    - **📊 Dashboard**: View your health trends
    - **🔬 Evidence Explorer**: Find therapies  
    - **🌱 Daily Log**: Track your health
    - **⚙️ Settings**: Manage your data
    """)

# Note: Filters are now in the Evidence Explorer tab itself
# No global filtering needed here

def _sort_df(df, how):
    df = df.copy()
    if how == "Most trials" and "clinicaltrials_n" in df.columns:
        return df.sort_values("clinicaltrials_n", ascending=False, na_position="last")
    if how == "Most PubMed" and "pubmed_n" in df.columns:
        return df.sort_values("pubmed_n", ascending=False, na_position="last")
    if how == "Newest first" and "year_max" in df.columns:
        return df.sort_values("year_max", ascending=False, na_position="last")
    return df

# Note: Sorting now happens within the Evidence Explorer tab

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tab_dashboard, tab_evidence, tab_analysis, tab_settings = st.tabs([
    "🏠 Dashboard",
    "🔬 Evidence Explorer",
    "🌱 Daily Log",
    "⚙️ Settings"
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
# First-Time User Onboarding Modal
# -----------------------------------------------------------------------------

def show_onboarding_modal():
    """Show welcome modal for first-time users"""
    if "onboarding_seen" not in st.session_state:
        st.session_state.onboarding_seen = False
    
    if not st.session_state.onboarding_seen:
        with st.container():
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 2rem; border-radius: 10px; color: white; margin-bottom: 2rem;">
                <h1 style="color: white; margin: 0;">👋 Welcome to Pain Relief Map!</h1>
                <p style="font-size: 1.2rem; margin-top: 0.5rem;">
                    Your personal health insights platform
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 🎯 What You'll Discover")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                #### 📊 Track Daily
                Log symptoms in 30 seconds:
                - Pain, stress, sleep, mood
                - Therapies used
                - Physical & emotional state
                """)
            
            with col2:
                st.markdown("""
                #### 🔬 Analyze Effects
                Statistical therapy analysis:
                - Before/after comparison
                - Bootstrap confidence intervals
                - Correlation discovery
                """)
            
            with col3:
                st.markdown("""
                #### 🎯 Validate Results
                Compare with research:
                - Clinical trials data
                - PubMed articles
                - Evidence direction
                """)
            
            st.markdown("---")
            st.markdown("### 🗺️ Quick Tour")
            
            tour_col1, tour_col2 = st.columns(2)
            
            with tour_col1:
                st.markdown("""
                **🏠 Dashboard** (You are here!)
                - See your trends and insights
                - Demo data shows what's possible
                - Daily reminder to log
                
                **🔬 Evidence Explorer**
                - Browse clinical trials
                - Filter by condition & therapy
                - See research evidence
                """)
            
            with tour_col2:
                st.markdown("""
                **🌱 Daily Log**
                - Daily wellness log
                - Calculate therapy effects
                - View correlation matrix
                - Timeline visualization
                
                **⚙️ Settings**
                - Export/import your data
                - Demo data management
                - Privacy: data stays local
                """)
            
            st.markdown("---")
            
            start_col1, start_col2, start_col3 = st.columns([1, 1, 1])
            
            with start_col1:
                if st.button("👁️ View Demo First", type="secondary", use_container_width=True):
                    st.session_state.onboarding_seen = True
                    # Demo toggle will be on by default
                    st.rerun()
            
            with start_col2:
                if st.button("🌱 Start Logging Now", type="primary", use_container_width=True):
                    st.session_state.onboarding_seen = True
                    st.session_state.skip_to_log = True
                    st.rerun()
            
            with start_col3:
                if st.button("❌ Skip Tour", use_container_width=True):
                    st.session_state.onboarding_seen = True
                    st.rerun()
            
            st.caption("💡 **Tip:** Your data stays on your device. No account needed. Export anytime!")
            
            st.stop()  # Stop rendering rest of dashboard until user dismisses modal

# -----------------------------------------------------------------------------
# Dashboard Tab (Personal insights and quick log)
# -----------------------------------------------------------------------------

with tab_dashboard:
    # Show onboarding for first-time users
    # show_onboarding_modal()  # Temporarily disabled - was blocking other tabs
    st.subheader("🏠 Your Personal Health Dashboard")
    
    # Check if user has any data
    has_data = not st.session_state.n1_df.empty if "n1_df" in st.session_state else False
    
    # Demo data toggle and date filter
    col_demo, col_date_filter, col_space = st.columns([1, 2, 1])
    with col_demo:
        show_demo = st.toggle(
            "👁️ Preview with demo data",
            value=not has_data,
            help="See what your dashboard will look like with sample data"
        )
    
    with col_date_filter:
        if has_data or show_demo:
            # Date range filter
            use_date_filter = st.toggle(
                "📅 Custom date range",
                value=False,
                help="Filter dashboard to specific date range"
            )
    
    # Determine which data to show
    if show_demo:
        # Load demo data
        demo_path = ROOT / "data" / "templates" / "n_of_1_demo.csv"
        if demo_path.exists():
            display_df = pd.read_csv(demo_path)
            display_df["date"] = pd.to_datetime(display_df["date"])
            st.info("📊 You're viewing demo data. Toggle off to see your own data (or start logging below).", icon="ℹ️")
        else:
            st.warning("Demo data file not found. Please add your own data below.")
            display_df = pd.DataFrame()
    elif has_data:
        display_df = st.session_state.n1_df.copy()
        display_df["date"] = pd.to_datetime(display_df["date"], errors="coerce")
    else:
        display_df = pd.DataFrame()
    
    # Apply date filter if enabled
    if not display_df.empty and (has_data or show_demo):
        if "use_date_filter" in locals() and use_date_filter:
            col_start, col_end = st.columns(2)
            with col_start:
                min_date = display_df["date"].min().date()
                start_date = st.date_input(
                    "From date:",
                    value=min_date,
                    min_value=min_date,
                    max_value=display_df["date"].max().date(),
                    format="DD/MM/YYYY"
                )
            with col_end:
                max_date = display_df["date"].max().date()
                end_date = st.date_input(
                    "To date:",
                    value=max_date,
                    min_value=min_date,
                    max_value=max_date,
                    format="DD/MM/YYYY"
                )
            
            # Filter dataframe by date range
            display_df = display_df[
                (display_df["date"].dt.date >= start_date) & 
                (display_df["date"].dt.date <= end_date)
            ]
            
            if display_df.empty:
                st.warning("No data in selected date range. Try different dates.")
            else:
                st.caption(f"Showing {len(display_df)} entries from {start_date} to {end_date}")
    
    # If we have data to display (demo or real)
    if not display_df.empty:
        # Yesterday's snapshot
        latest_row = display_df.sort_values("date").iloc[-1]
        latest_date = latest_row["date"].strftime("%d/%m/%Y") if pd.notna(latest_row["date"]) else "Latest"
        
        st.markdown(f"### 📸 Latest Entry ({latest_date})")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Pain", f"{int(latest_row.get('pain_score', 0))}/10")
        kpi2.metric("Sleep", f"{latest_row.get('sleep_hours', 0):.1f}h")
        kpi3.metric("Mood", f"{int(latest_row.get('mood_score', 0))}/10")
        
        # Show therapy if tracked
        if "therapy_name" in latest_row and pd.notna(latest_row["therapy_name"]) and str(latest_row["therapy_name"]).strip():
            st.caption(f"🌿 Current therapy: **{latest_row['therapy_name']}**")
        
        # Key insight banner (if therapy_on exists and has both 0 and 1 values)
        if "therapy_on" in display_df.columns and display_df["therapy_on"].nunique() > 1:
            try:
                from src.causal import compute_pre_post_effect
                effect_result = compute_pre_post_effect(
                    display_df,
                    date_col="date",
                    on_col="therapy_on",
                    y_col="pain_score"
                )
                
                # Convert date format if needed (handle cached module issue)
                start_date_str = effect_result['start_date']
                if '-' in start_date_str:  # Format is YYYY-MM-DD
                    try:
                        from datetime import datetime
                        date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
                        effect_result['start_date'] = date_obj.strftime("%d/%m/%Y")
                    except:
                        pass
                
                # Show insight banner
                effect_mean = effect_result["effect_mean"]
                ci_low = effect_result["ci_low"]
                ci_high = effect_result["ci_high"]
                pre_mean = effect_result["pre_mean"]
                post_mean = effect_result["post_mean"]
                therapy_name = str(latest_row.get("therapy_name", "therapy"))
                
                # Calculate percentage reduction
                if pre_mean > 0:
                    pct_reduction = abs((effect_mean / pre_mean) * 100)
                else:
                    pct_reduction = 0
                
                # Calculate sleep and mood improvements
                pre_therapy_df = display_df[display_df["therapy_on"] == 0]
                post_therapy_df = display_df[display_df["therapy_on"] == 1]
                
                sleep_improvement = ""
                mood_improvement = ""
                
                if not pre_therapy_df.empty and not post_therapy_df.empty:
                    pre_sleep = pre_therapy_df["sleep_hours"].mean()
                    post_sleep = post_therapy_df["sleep_hours"].mean()
                    sleep_diff = post_sleep - pre_sleep
                    
                    pre_mood = pre_therapy_df["mood_score"].mean()
                    post_mood = post_therapy_df["mood_score"].mean()
                    mood_diff = post_mood - pre_mood
                    
                    if sleep_diff > 0.5:
                        sleep_improvement = f"improved sleep by {sleep_diff:.1f}h"
                    if mood_diff > 0.5 and pre_mood > 0:
                        mood_pct = (mood_diff / pre_mood) * 100
                        mood_improvement = f"boosted mood by {mood_pct:.0f}%"
                    
                    # Combine improvements
                    improvements = [imp for imp in [sleep_improvement, mood_improvement] if imp]
                    if improvements:
                        improvement_text = " It also " + " and ".join(improvements) + "."
                    else:
                        improvement_text = ""
                else:
                    improvement_text = ""
                
                if effect_mean < 0:
                    st.success(
                        f"💡 **Key Insight:** {therapy_name.title()} reduced your pain by "
                        f"**{pct_reduction:.0f}%** since {effect_result['start_date']}.{improvement_text} Keep it up! 🎉",
                        icon="✅"
                    )
                elif effect_mean > 0:
                    st.warning(
                        f"⚠️ Pain increased since starting {therapy_name}. "
                        f"Consider discussing with your healthcare provider.",
                        icon="⚠️"
                    )
            except (ValueError, KeyError, ImportError) as e:
                # Not enough data yet or causal.py not available
                pass
        
        # Progress Summary (Before vs After) - Moved here above the chart
        if len(display_df) >= 3:
            # Check if we have therapy tracking data
            if "therapy_on" in display_df.columns and display_df["therapy_on"].nunique() > 1:
                pre_df = display_df[display_df["therapy_on"] == 0]
                post_df = display_df[display_df["therapy_on"] == 1]
                
                if not pre_df.empty and not post_df.empty:
                    st.markdown("### 📊 Progress Summary")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    # Pain comparison
                    with col1:
                        pre_pain = pre_df["pain_score"].mean()
                        post_pain = post_df["pain_score"].mean()
                        pain_change = post_pain - pre_pain
                        st.metric(
                            "Pain", 
                            f"{post_pain:.1f}/10",
                            delta=f"{pain_change:.1f}",
                            delta_color="inverse",
                            help=f"Before: {pre_pain:.1f}/10 → After: {post_pain:.1f}/10"
                        )
                    
                    # Sleep comparison
                    with col2:
                        pre_sleep = pre_df["sleep_hours"].mean()
                        post_sleep = post_df["sleep_hours"].mean()
                        sleep_change = post_sleep - pre_sleep
                        st.metric(
                            "Sleep", 
                            f"{post_sleep:.1f}h",
                            delta=f"{sleep_change:.1f}h",
                            delta_color="normal",
                            help=f"Before: {pre_sleep:.1f}h → After: {post_sleep:.1f}h"
                        )
                    
                    # Mood comparison
                    with col3:
                        pre_mood = pre_df["mood_score"].mean()
                        post_mood = post_df["mood_score"].mean()
                        mood_change = post_mood - pre_mood
                        st.metric(
                            "Mood", 
                            f"{post_mood:.1f}/10",
                            delta=f"{mood_change:.1f}",
                            delta_color="normal",
                            help=f"Before: {pre_mood:.1f}/10 → After: {post_mood:.1f}/10"
                        )
                    
                    st.caption("💡 Showing averages before vs after starting therapy. Green/red arrows show improvement/decline.")
                    st.markdown("")  # Spacing
            else:
                # No therapy tracking, show overall averages
                avg_pain = display_df["pain_score"].mean()
                avg_sleep = display_df["sleep_hours"].mean()
                avg_mood = display_df["mood_score"].mean()
                
                st.markdown("### 📊 Overall Averages")
                col1, col2, col3 = st.columns(3)
                col1.metric("Avg Pain", f"{avg_pain:.1f}/10")
                col2.metric("Avg Sleep", f"{avg_sleep:.1f}h")
                col3.metric("Avg Mood", f"{avg_mood:.1f}/10")
                st.markdown("")  # Spacing
        
        # 14-day trend chart with therapy start line
        st.markdown("### 📈 Last 14 Days Trend")
        recent_df = display_df.sort_values("date").tail(14)
        
        if len(recent_df) > 0:
            # Prepare data for plotting - show Pain, Sleep, and Mood
            plot_recent = recent_df[["date", "pain_score", "sleep_hours", "mood_score"]].copy()
            
            # Add therapy_on if it exists
            if "therapy_on" in recent_df.columns:
                plot_recent["therapy_on"] = recent_df["therapy_on"]
            
            plot_recent = plot_recent.melt(
                id_vars=["date"] + (["therapy_on"] if "therapy_on" in plot_recent else []),
                var_name="Metric",
                value_name="Score"
            )
            plot_recent["Metric"] = plot_recent["Metric"].replace({
                "pain_score": "Pain",
                "sleep_hours": "Sleep (hours)",
                "mood_score": "Mood"
            })
            
            fig = px.line(
                plot_recent,
                x="date",
                y="Score",
                color="Metric",
                markers=True,
                title="Pain, Sleep & Mood (Last 14 Days)",
                color_discrete_map={"Pain": "#e74c3c", "Sleep (hours)": "#3498db", "Mood": "#2ecc71"}
            )
            
            # Add vertical line showing therapy start date
            if "therapy_on" in recent_df.columns and recent_df["therapy_on"].nunique() > 1:
                therapy_start = recent_df[recent_df["therapy_on"] == 1]["date"].min()
                if pd.notna(therapy_start):
                    # Use add_shape instead of add_vline to avoid timestamp issues
                    fig.add_shape(
                        type="line",
                        x0=therapy_start,
                        x1=therapy_start,
                        y0=0,
                        y1=1,
                        yref="paper",
                        line=dict(color="purple", width=2, dash="dash")
                    )
                    
                    # Add annotation manually
                    fig.add_annotation(
                        x=therapy_start,
                        y=1,
                        yref="paper",
                        text="🌟 Therapy Started",
                        showarrow=False,
                        yshift=10,
                        font=dict(color="purple", size=12)
                    )
                    
                    # Optional: Add light shading for therapy period
                    fig.add_vrect(
                        x0=therapy_start,
                        x1=recent_df["date"].max(),
                        fillcolor="lavender",
                        opacity=0.15,
                        layer="below",
                        line_width=0
                    )
            
            fig.update_layout(
                yaxis_title="Score (0-10)",
                xaxis_title="Date",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        # New user welcome card
        st.markdown("""
        ### 👋 Welcome to Pain Relief Map!
        
        **Here's what you'll discover:**
        
        ✅ Track daily symptoms (takes 30 seconds/day)  
        ✅ Analyze therapy effects with statistical rigor  
        ✅ Compare your results with published research  
        
        **Get started:**
        1. Toggle "Preview with demo data" above to see what your dashboard will look like
        2. Go to **🌿 Daily Wellness Log** tab below to add your first entry
        3. Come back here to see your trends!
        """)
    
    # Daily log reminder
    st.divider()
    if has_data and not show_demo:
        # Check if today's date already logged
        today = dt.date.today()
        dates_logged = pd.to_datetime(st.session_state.n1_df["date"], errors="coerce").dt.date
        if today not in dates_logged.values:
            st.info("📅 You haven't logged today's data yet. Scroll down to the Daily Wellness Log tab!", icon="💡")
    

# -----------------------------------------------------------------------------
# Evidence Explorer tab (now wired to f_sorted)
# -----------------------------------------------------------------------------

with tab_evidence:
    # =========================================================================
    # FILTERS AT TOP OF TAB
    # =========================================================================
    st.markdown("## 🔬 Evidence Explorer")
    st.markdown("Find therapies backed by clinical research for your condition")
    
    with st.expander("🔍 **Search Filters** (Select your condition to get started)", expanded=True):
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            # Comprehensive therapy list
            therapy_opts = [
                "Acupuncture", "Aromatherapy", "Ayurveda", "Cognitive Behavioural Therapy", 
                "Exercise Therapy", "Herbal", "Massage", "Meditation", "Qi Gong", "Tai Chi", "Yoga"
            ]
            # Set default to Anxiety if available, otherwise first option
            default_conds = [default_condition] if default_condition in cond_options else (cond_options[:1] if cond_options else [])
            
            tab_conditions = st.multiselect(
                "🏥 Your Condition(s)",
                options=cond_options,
                default=default_conds,
                help="Select one or more conditions to see relevant therapies"
            )
            
            tab_therapies = st.multiselect(
                "💊 Therapies to Compare",
                options=therapy_opts,
                default=therapy_opts,
                help="Choose specific therapies to compare, or leave all selected"
            )
        
        with filter_col2:
            tab_yr = st.slider(
                "📅 Study Years",
                min_value=year_lo,
                max_value=year_hi,
                value=(default_lo, current_year),
                help="Filter studies by publication year range"
            )
            
            tab_sel_evdir = st.multiselect(
                "📊 Evidence Direction",
                options=evdir_opts,
                default=default_evdir,
                help="Filter by type of evidence"
            )
    
    # Apply filters specific to this tab
    base = evidence.copy()
    
    if "condition" in base.columns and tab_conditions:
        base = base[base["condition"].isin(tab_conditions)]
    if tab_therapies and "therapy" in base.columns:
        base = base[base["therapy"].isin(tab_therapies)]
    
    if "year_min" in base.columns: base["year_min"] = _def_num(base["year_min"])
    if "year_max" in base.columns: base["year_max"] = _def_num(base["year_max"])
    if "year_min" in base.columns or "year_max" in base.columns:
        ymin = base["year_min"].fillna(base["year_max"]).fillna(year_lo)
        ymax = base["year_max"].fillna(base["year_min"]).fillna(year_hi)
        base = base[(ymax >= tab_yr[0]) & (ymin <= tab_yr[1])]
    
    if tab_sel_evdir and "evidence_direction" in base.columns:
        base = base[base["evidence_direction"].isin(tab_sel_evdir)]
    
    plot_df = base.copy()

    # Show helpful message if no condition selected
    if not tab_conditions:
        st.info(
            "👆 **Please select at least one condition** from the filters above to see therapy recommendations.",
            icon="💡"
        )
        # Show a preview of what they can explore
        st.markdown("### 🔬 What you can discover:")
        st.markdown("""
        - **Clinical trials** for your specific condition
        - **Evidence-based therapies** with positive research backing
        - **PubMed articles** supporting each therapy
        - **Direct links** to research sources
        
        **Get started:** Select your condition(s) in the filters above! 👆
        """)
        st.stop()
    
    # If nothing matches filters, show friendly hint
    if plot_df.empty:
        st.warning(
            "No therapies found matching your filters. Try selecting a different condition or broadening your criteria.",
            icon="🔍"
        )
        st.stop()

    # =========================================================================
    # SUMMARY BAR CHART - Visual Overview
    # =========================================================================
    st.markdown("### 📊 Summary: Top Therapies at a Glance")
    
    # Prepare data for bar chart
    chart_df = plot_df.copy()
    chart_df["trials_num"] = pd.to_numeric(chart_df.get("clinicaltrials_n", 0), errors="coerce").fillna(0)
    chart_df["pubmed_num"] = pd.to_numeric(chart_df.get("pubmed_n", 0), errors="coerce").fillna(0)
    chart_df["evidence_score"] = (chart_df["trials_num"] * 10) + chart_df["pubmed_num"]
    
    # Sort and take top 10 for readability
    chart_df_top = chart_df.nlargest(10, "evidence_score")
    
    # Decide what to color by: condition if multiple selected, otherwise evidence direction
    if len(tab_conditions) > 1 and "condition" in chart_df_top.columns:
        color_by = "condition"
        color_map = None  # Let plotly auto-assign colors
        chart_title = f"Top 10 Therapies by Clinical Trial Count (All Conditions)"
    elif "evidence_direction" in chart_df_top.columns:
        color_by = "evidence_direction"
        color_map = {
            "Positive": "#2ecc71",
            "Negative": "#e74c3c",
            "Mixed": "#f1c40f",
            "Unclear": "#95a5a6",
        }
        chart_title = f"Top 10 Therapies by Clinical Trial Count ({', '.join(tab_conditions)})"
    else:
        color_by = None
        color_map = None
        chart_title = f"Top 10 Therapies by Clinical Trial Count"
    
    fig_summary = px.bar(
        chart_df_top.sort_values("evidence_score", ascending=True),  # Ascending for horizontal bar
        y="therapy",
        x="trials_num",
        color=color_by,
        color_discrete_map=color_map if color_map else None,
        orientation='h',
        title=chart_title,
        labels={"trials_num": "Number of Clinical Trials", "therapy": "Therapy", "condition": "Condition"},
        height=400
    )
    fig_summary.update_layout(
        showlegend=True if color_by else False,
        yaxis={'categoryorder':'total ascending'},
        barmode='stack'  # Stack bars when coloring by condition
    )
    st.plotly_chart(fig_summary, use_container_width=True)
    
    st.markdown("---")

    # =========================================================================
    # MAIN HEADER - What works for your condition
    # =========================================================================
    st.markdown("### 💊 Top Therapies for Your Condition(s)")
    
    # Calculate evidence score for sorting (trials worth more)
    plot_df_sorted = plot_df.copy()
    plot_df_sorted["trials_num"] = pd.to_numeric(plot_df_sorted.get("clinicaltrials_n", 0), errors="coerce").fillna(0)
    plot_df_sorted["pubmed_num"] = pd.to_numeric(plot_df_sorted.get("pubmed_n", 0), errors="coerce").fillna(0)
    plot_df_sorted["evidence_score"] = (plot_df_sorted["trials_num"] * 10) + plot_df_sorted["pubmed_num"]  # Weight trials 10x
    
    # Sort by evidence score (high to low)
    plot_df_sorted = plot_df_sorted.sort_values("evidence_score", ascending=False)
    
    # Show count summary
    total_therapies = len(plot_df_sorted)
    positive_count = len(plot_df_sorted[plot_df_sorted.get("evidence_direction") == "Positive"]) if "evidence_direction" in plot_df_sorted.columns else 0
    
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
        📊 Found <strong>{total_therapies} therapies</strong> for your condition(s)
        {f" • <strong style='color: #2ecc71;'>{positive_count} with positive evidence</strong>" if positive_count > 0 else ""}
    </div>
    """, unsafe_allow_html=True)
    
    # =========================================================================
    # SIMPLE THERAPY TABLE - Ordered by Evidence Strength
    # =========================================================================
    
    for idx, (_, row) in enumerate(plot_df_sorted.iterrows()):
        therapy_name = row.get("therapy", "Unknown")
        condition_name = row.get("condition", "")
        category = row.get("therapy_group", "Unknown")
        evidence_dir = row.get("evidence_direction", "Unclear")
        trials_n = int(row.get("trials_num", 0))
        pubmed_n = int(row.get("pubmed_num", 0))
        trials_url = row.get("trials_url", "")
        articles_url = row.get("articles_url", "")
        
        # Evidence badge styling
        if evidence_dir == "Positive":
            badge_html = '<span style="background: #2ecc71; color: white; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; margin-left: 0.5rem;">✓ Positive Evidence</span>'
        elif evidence_dir == "Negative":
            badge_html = '<span style="background: #e74c3c; color: white; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; margin-left: 0.5rem;">✗ Negative</span>'
        elif evidence_dir == "Mixed":
            badge_html = '<span style="background: #f1c40f; color: white; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; margin-left: 0.5rem;">~ Mixed</span>'
        else:
            badge_html = '<span style="background: #95a5a6; color: white; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; margin-left: 0.5rem;">? Unclear</span>'
        
        # Rank number (1st, 2nd, 3rd...)
        rank = idx + 1
        rank_color = "#2ecc71" if rank <= 3 else "#3498db" if rank <= 10 else "#7f8c8d"
        
        # Create therapy card with inline links
        st.markdown(f"""
        <div style="background: white; border: 2px solid #e0e0e0; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; 
                    transition: all 0.2s ease; {'border-left: 5px solid #2ecc71;' if evidence_dir == 'Positive' else ''}">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div style="background: {rank_color}; color: white; width: 36px; height: 36px; border-radius: 50%; 
                                display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.1rem;">
                        {rank}
                    </div>
                    <div>
                        <h3 style="margin: 0; color: #2c3e50; font-size: 1.3rem;">{therapy_name}</h3>
                        <p style="margin: 0.25rem 0 0 0; color: #7f8c8d; font-size: 0.9rem;">
                            {badge_html} {category} • {condition_name if condition_name else 'General'}
                        </p>
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 2rem; margin-top: 0.75rem; padding-left: 52px;">
                <div>
                    📊 <a href="{trials_url}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 600;">{trials_n:,} Clinical Trials</a>
                </div>
                <div>
                    📚 <a href="{articles_url}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: 600;">{pubmed_n:,} PubMed Articles</a>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # =========================================================================
    # OPTIONAL: Show interpretation guide
    # =========================================================================
    st.markdown("---")
    with st.expander("📖 How to Interpret This Data"):
        st.markdown("""
        **How therapies are ranked:**
        - Ranked by total evidence strength (clinical trials weighted 10x more than articles)
        - Therapies at the top have the most research backing
        
        **Evidence Direction:**
        - 🟢 **✓ Positive Evidence**: Studies show beneficial effects for the condition
        - 🔴 **✗ Negative**: Studies show little to no benefit  
        - 🟡 **~ Mixed**: Studies show conflicting results
        - ⚪ **? Unclear**: Insufficient or inconclusive evidence
        
        **Study Types:**
        - **Clinical Trials**: High-quality, controlled studies from ClinicalTrials.gov
        - **PubMed Articles**: Published research (various study types and quality levels)
        
        **💡 What to do with this information:**
        1. Focus on therapies with positive evidence and high trial counts
        2. Click "View Trials" or "View Articles" to read the research
        3. Discuss promising options with your healthcare provider
        4. Consider starting with top-ranked therapies that fit your lifestyle
        
        **⚠️ Important**: This is for informational purposes only. Always consult your healthcare provider before starting any new therapy.
        """)
    
    # =========================================================================
    # EXPORT OPTION
    # =========================================================================
    st.markdown("---")
    st.markdown("### 💾 Save This List")
    csv_data = plot_df_sorted[["therapy", "therapy_group", "condition", "evidence_direction", 
                                 "clinicaltrials_n", "pubmed_n", "trials_url", "articles_url"]].to_csv(index=False).encode('utf-8')
    condition_name = '-'.join(tab_conditions[:2]) if tab_conditions else 'selected-conditions'
    st.download_button(
        label="📥 Download as CSV to share with your doctor",
        data=csv_data,
        file_name=f"therapies_for_{condition_name}_{dt.date.today()}.csv",
        mime="text/csv",
        use_container_width=True
    )

# -----------------------------------------------------------------------------
# Analysis Tab: Daily Wellness Log + Therapy Effect Calculator
# -----------------------------------------------------------------------------
with tab_analysis:
    # First, show therapy effect calculator if user has data with therapy tracking
    if "n1_df" in st.session_state and not st.session_state.n1_df.empty:
        df_analysis = st.session_state.n1_df.copy()
        df_analysis["date"] = pd.to_datetime(df_analysis["date"], errors="coerce")
        
        # Check if therapy tracking data exists
        if "therapy_on" in df_analysis.columns and df_analysis["therapy_on"].nunique() > 1:
            st.subheader("📊 Therapy Effect Calculator")
            st.markdown("""
            Calculate the statistical effect of your therapy on pain using bootstrap confidence intervals.
            This analysis compares your symptoms **before** vs **after** starting a therapy.
            
            💡 **Note:** You can analyze single therapies (e.g., "Acupuncture") or combinations (e.g., "Acupuncture + Yoga").
            """)
            
            # Get unique therapy names
            therapy_names = df_analysis[df_analysis["therapy_name"].notna()]["therapy_name"].unique()
            
            if len(therapy_names) > 0:
                selected_therapy = st.selectbox(
                    "Select therapy to analyze:",
                    options=therapy_names,
                    help="Choose which therapy period to analyze"
                )
                
                calc_col1, calc_col2 = st.columns([1, 3])
                with calc_col1:
                    if st.button("🔬 Calculate Effect", type="primary"):
                        try:
                            from src.causal import compute_pre_post_effect
                            
                            # Filter to the specific therapy period
                            therapy_df = df_analysis.copy()
                            
                            # Run analysis
                            result = compute_pre_post_effect(
                                therapy_df,
                                date_col="date",
                                on_col="therapy_on",
                                y_col="pain_score"
                            )
                            
                            # Convert date format if needed (handle cached module issue)
                            start_date_str = result['start_date']
                            if '-' in start_date_str:  # Format is YYYY-MM-DD
                                try:
                                    from datetime import datetime
                                    date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
                                    result['start_date'] = date_obj.strftime("%d/%m/%Y")
                                except:
                                    pass
                            
                            # Display results
                            st.markdown("### ✅ Results")
                            
                            # Effect summary card
                            effect = result["effect_mean"]
                            ci_low = result["ci_low"]
                            ci_high = result["ci_high"]
                            
                            if effect < 0:
                                st.success(
                                    f"🎉 **Pain decreased by {abs(effect):.2f} points** "
                                    f"(95% CI: {abs(ci_high):.2f}–{abs(ci_low):.2f})\n\n"
                                    f"Since starting {selected_therapy} on {result['start_date']}"
                                )
                            elif effect > 0:
                                st.warning(
                                    f"⚠️ **Pain increased by {effect:.2f} points** "
                                    f"(95% CI: {ci_low:.2f}–{ci_high:.2f})\n\n"
                                    f"Since starting {selected_therapy} on {result['start_date']}"
                                )
                            else:
                                st.info(
                                    f"➡️ **No significant change** in pain "
                                    f"(95% CI: {ci_low:.2f}–{ci_high:.2f})"
                                )
                            
                            # Detailed stats
                            st.markdown("### 📈 Detailed Statistics")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Pre-therapy pain", f"{result['pre_mean']:.2f}/10", 
                                       help=f"Average pain before therapy (n={result['n_pre']} days)")
                            col2.metric("Post-therapy pain", f"{result['post_mean']:.2f}/10",
                                       help=f"Average pain after therapy (n={result['n_post']} days)")
                            col3.metric("Effect size", f"{result['effect_mean']:.2f}",
                                       delta=f"{result['effect_mean']:.2f}",
                                       delta_color="inverse",
                                       help="Mean difference (post - pre)")
                            
                            # Visualization: Before/After comparison
                            pre_post_df = pd.DataFrame({
                                "Period": ["Before", "After"],
                                "Pain Score": [result["pre_mean"], result["post_mean"]],
                                "CI_lower": [result["pre_mean"], result["ci_low"]],
                                "CI_upper": [result["pre_mean"], result["ci_high"]]
                            })
                            
                            fig_effect = px.bar(
                                pre_post_df,
                                x="Period",
                                y="Pain Score",
                                title=f"Pain Before vs After {selected_therapy}",
                                color="Period",
                                color_discrete_map={"Before": "#95a5a6", "After": "#3498db"}
                            )
                            fig_effect.update_layout(showlegend=False, yaxis_range=[0, 10])
                            st.plotly_chart(fig_effect, use_container_width=True)
                            
                            # Interpretation guidance
                            st.markdown("### 💡 What does this mean?")
                            if abs(effect) < 0.5:
                                st.info("The effect is very small and may not be clinically meaningful.")
                            elif abs(effect) < 1.5:
                                st.info("The effect is small to moderate. You might notice some difference.")
                            elif abs(effect) < 3.0:
                                st.success("The effect is moderate to large. This is a clinically meaningful change!")
                            else:
                                st.success("The effect is very large! This is a substantial improvement.")
                            
                            st.caption("""
                            **Note:** These results are based on your personal N-of-1 data. 
                            Confidence intervals were calculated using bootstrap resampling (2000 iterations).
                            Always consult with healthcare providers about treatment decisions.
                            """)
                            
                            # --- "Your Results vs Evidence" Comparison ---
                            st.markdown("---")
                            st.markdown("### 🔬 Your Results vs Published Research")
                            
                            # Get user's condition (most recent entry)
                            latest = df_analysis.sort_values("date").iloc[-1]
                            user_conditions = str(latest.get("condition_today", "")).split(",")
                            user_conditions = [c.strip().title() for c in user_conditions if c.strip() and c.strip().lower() != "none"]
                            
                            if user_conditions:
                                # Try to match with evidence data
                                try:
                                    # Normalize therapy name for matching
                                    therapy_normalized = selected_therapy.strip().title()
                                    
                                    # Query evidence database
                                    evidence_match = evidence[
                                        (evidence["condition"].isin(user_conditions)) &
                                        (evidence["therapy"].str.contains(therapy_normalized, case=False, na=False))
                                    ]
                                    
                                    if not evidence_match.empty:
                                        # Take first match
                                        ev_row = evidence_match.iloc[0]
                                        
                                        st.success("✅ Found matching research for your therapy!", icon="🎯")
                                        
                                        col_you, col_research = st.columns(2)
                                        
                                        with col_you:
                                            st.markdown("#### 👤 Your Results")
                                            st.metric(
                                                "Pain Change",
                                                f"{result['effect_mean']:.2f} points",
                                                delta=f"{result['effect_mean']:.2f}",
                                                delta_color="inverse"
                                            )
                                            
                                            # Calculate percentage change
                                            if result['pre_mean'] > 0:
                                                pct_change = (result['effect_mean'] / result['pre_mean']) * 100
                                                st.metric("Percentage Change", f"{pct_change:.1f}%")
                                            
                                            st.caption(f"Based on {result['n_pre'] + result['n_post']} days of tracking")
                                        
                                        with col_research:
                                            st.markdown("#### 📚 Published Research")
                                            
                                            trials = int(ev_row.get("clinicaltrials_n", 0))
                                            pubmed = int(ev_row.get("pubmed_n", 0))
                                            
                                            st.metric("Clinical Trials", f"{trials:,}")
                                            st.metric("PubMed Articles", f"{pubmed:,}")
                                            
                                            if "evidence_direction" in ev_row and pd.notna(ev_row["evidence_direction"]):
                                                direction = str(ev_row["evidence_direction"]).capitalize()
                                                if direction == "Positive":
                                                    st.success(f"Evidence Direction: **{direction}**", icon="✅")
                                                elif direction == "Mixed":
                                                    st.warning(f"Evidence Direction: **{direction}**", icon="⚠️")
                                                else:
                                                    st.info(f"Evidence Direction: **{direction}**")
                                        
                                        # Interpretation
                                        st.markdown("#### 💡 Interpretation")
                                        
                                        if effect < 0:
                                            if trials > 20:
                                                st.success(
                                                    f"🎉 **Great news!** Your pain reduction aligns with {trials} clinical trials studying "
                                                    f"{therapy_normalized} for {user_conditions[0]}. "
                                                    f"This suggests the therapy is working well for you, consistent with scientific evidence."
                                                )
                                            elif trials > 5:
                                                st.info(
                                                    f"✅ Your improvement matches findings from {trials} clinical trials. "
                                                    f"There's moderate research support for this therapy."
                                                )
                                            else:
                                                st.info(
                                                    f"📊 You're seeing improvement! Note: Only {trials} trials exist for this combo. "
                                                    f"Your N-of-1 data is valuable personal evidence."
                                                )
                                        else:
                                            st.info(
                                                f"🔍 Your results differ from typical outcomes. This could mean:\n"
                                                f"- The therapy may not be effective for you specifically\n"
                                                f"- It may need more time (you have {result['n_post']} days post-therapy)\n"
                                                f"- Other factors may be influencing your symptoms\n\n"
                                                f"Consider discussing with your healthcare provider."
                                            )
                                        
                                        # Link to Evidence Explorer
                                        st.markdown(f"""
                                        **Want to explore the research?**  
                                        → Go to the **Evidence Explorer** tab and filter for:
                                        - Condition: {user_conditions[0]}
                                        - Therapy: {therapy_normalized}
                                        """)
                                        
                                        if "trials_url" in ev_row and pd.notna(ev_row["trials_url"]):
                                            st.markdown(f"[🔗 View Clinical Trials]({ev_row['trials_url']})")
                                        if "articles_url" in ev_row and pd.notna(ev_row["articles_url"]):
                                            st.markdown(f"[🔗 View PubMed Articles]({ev_row['articles_url']})")
                                    
                                    else:
                                        st.info(
                                            f"📊 No published research found for **{therapy_normalized}** + **{user_conditions[0]}** in our database.\n\n"
                                            f"This doesn't mean the therapy doesn't work—it may simply be under-researched for this specific combination. "
                                            f"Your N-of-1 data is still valuable for your personal treatment decisions!"
                                        )
                                
                                except Exception as e:
                                    st.warning(f"⚠️ Could not load research comparison: {str(e)}")
                            else:
                                st.info("💡 Log your condition in the Daily Wellness Log to compare with research.")
                            
                        except ValueError as e:
                            st.error(f"❌ Cannot calculate effect: {str(e)}")
                        except ImportError:
                            st.error("❌ Causal analysis module not found. Check src/causal.py exists.")
                        except Exception as e:
                            st.error(f"❌ Error calculating effect: {str(e)}")
            else:
                st.info("💡 No therapy data found. Use the 'Started new therapy' checkbox in the log below to track therapy periods.")
            
            st.divider()
        
        # Timeline Visualization (if therapy tracked)
        if "therapy_on" in df_analysis.columns and df_analysis["therapy_on"].nunique() > 1:
            st.subheader("📅 Therapy Timeline")
            st.markdown("Visualize your pain journey with therapy periods marked.")
            
            # Prepare timeline data
            timeline_df = df_analysis.sort_values("date").copy()
            
            # Create therapy period labels
            timeline_df["Period"] = timeline_df["therapy_on"].map({0: "Pre-therapy", 1: "Post-therapy"})
            
            # Create combined timeline chart
            fig_timeline = px.scatter(
                timeline_df,
                x="date",
                y="pain_score",
                color="Period",
                size=[5] * len(timeline_df),
                title="Pain Score Over Time (with Therapy Periods)",
                color_discrete_map={"Pre-therapy": "#95a5a6", "Post-therapy": "#3498db"},
                hover_data={"stress_score": True, "sleep_hours": True, "mood_score": True}
            )
            
            # Add line connecting points
            fig_timeline.add_scatter(
                x=timeline_df["date"],
                y=timeline_df["pain_score"],
                mode="lines",
                line=dict(color="lightgray", width=1),
                showlegend=False,
                hoverinfo="skip"
            )
            
            # Mark therapy start date
            therapy_start_date = timeline_df[timeline_df["therapy_on"] == 1]["date"].min()
            if pd.notna(therapy_start_date):
                fig_timeline.add_vline(
                    x=therapy_start_date,
                    line_dash="dash",
                    line_color="green",
                    annotation_text="Therapy Started",
                    annotation_position="top"
                )
            
            fig_timeline.update_layout(
                yaxis_title="Pain Score (0-10)",
                xaxis_title="Date",
                yaxis_range=[0, 10],
                height=400,
                hovermode="x unified"
            )
            
            st.plotly_chart(fig_timeline, use_container_width=True)
            
            # Show therapy summary
            pre_days = (timeline_df["therapy_on"] == 0).sum()
            post_days = (timeline_df["therapy_on"] == 1).sum()
            
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.metric("Pre-therapy Days", f"{pre_days}")
            col_t2.metric("Post-therapy Days", f"{post_days}")
            col_t3.metric("Total Tracked", f"{len(timeline_df)}")
            
            st.divider()
        
        # Correlation Matrix (if enough data)
        if len(df_analysis) >= 10:
            st.subheader("🔗 Correlation Analysis")
            st.markdown("""
            Discover relationships between pain and other factors like sleep, stress, and mood.
            Values closer to +1 or -1 indicate stronger relationships.
            """)
            
            # Select relevant columns for correlation
            corr_cols = ["pain_score", "stress_score", "sleep_hours", "mood_score"]
            if "anxiety_score" in df_analysis.columns:
                corr_cols.append("anxiety_score")
            if "patience_score" in df_analysis.columns:
                corr_cols.append("patience_score")
            
            # Calculate correlations
            corr_df = df_analysis[corr_cols].corr()
            
            # Create heatmap
            fig_corr = px.imshow(
                corr_df,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdBu_r",
                color_continuous_midpoint=0,
                title="Correlation Matrix (How factors relate to each other)",
                labels=dict(color="Correlation")
            )
            fig_corr.update_xaxes(side="bottom")
            fig_corr.update_layout(
                xaxis_title="",
                yaxis_title="",
                height=500
            )
            
            # Rename labels for better readability
            rename_map = {
                "pain_score": "Pain",
                "stress_score": "Stress",
                "sleep_hours": "Sleep",
                "mood_score": "Mood",
                "anxiety_score": "Anxiety",
                "patience_score": "Patience"
            }
            fig_corr.update_xaxes(ticktext=[rename_map.get(x, x) for x in corr_cols])
            fig_corr.update_yaxes(ticktext=[rename_map.get(x, x) for x in corr_cols])
            
            st.plotly_chart(fig_corr, use_container_width=True)
            
            # Key insights
            st.markdown("#### 💡 Key Findings")
            
            # Find strongest correlations with pain (excluding pain itself)
            pain_corrs = corr_df["pain_score"].drop("pain_score").sort_values(ascending=False)
            
            insights = []
            for metric, corr_val in pain_corrs.items():
                metric_name = rename_map.get(metric, metric)
                if abs(corr_val) > 0.5:
                    if corr_val > 0:
                        insights.append(f"• **Strong positive relationship** between Pain and {metric_name} ({corr_val:.2f}): When one increases, the other tends to increase too.")
                    else:
                        insights.append(f"• **Strong inverse relationship** between Pain and {metric_name} ({corr_val:.2f}): When one increases, the other tends to decrease.")
                elif abs(corr_val) > 0.3:
                    if corr_val > 0:
                        insights.append(f"• **Moderate positive relationship** between Pain and {metric_name} ({corr_val:.2f}).")
                    else:
                        insights.append(f"• **Moderate inverse relationship** between Pain and {metric_name} ({corr_val:.2f}).")
            
            if insights:
                for insight in insights:
                    st.markdown(insight)
            else:
                st.info("No strong correlations found yet. Keep tracking to reveal patterns!")
            
            st.caption("""
            **Understanding correlations:**
            - Values near +1: Strong positive relationship (both move together)
            - Values near -1: Strong inverse relationship (one up, other down)
            - Values near 0: Little to no relationship
            - Correlation doesn't imply causation
            """)
            
            st.divider()
    
    # Daily Wellness Log section
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
        "good_day", "therapy_on", "therapy_name",
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
            "therapy_on": int(row.get("therapy_on", 0)),
            "therapy_name": row.get("therapy_name", ""),
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
                        help="Copy yesterday's values to today"):
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
                        # Ensure therapy tracking data is copied
                        if "therapy_on" not in dup:
                            dup["therapy_on"] = 0
                        if "therapy_name" not in dup:
                            dup["therapy_name"] = ""
                        _append_row(dup)
                        st.success("Duplicated yesterday's values to today!")

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
        
        # Therapy tracking: started new therapy today?
        st.markdown("---")
        st.markdown("#### 🌟 Therapy Tracking")
        st.caption("💡 **Tip:** You can track multiple therapies simultaneously in 'Therapy used today' above. Use the checkbox below only when starting a NEW therapy for before/after analysis.")
        
        t1, t2 = st.columns(2)
        with t1:
            f_started_therapy = st.checkbox(
                "Started a new primary therapy today",
                help="Check this box on the first day you begin a new PRIMARY therapy for before/after analysis."
            )
        with t2:
            f_therapy_name = st.text_input(
                "Which therapy?",
                placeholder="e.g., Acupuncture or Acupuncture + Yoga",
                disabled=not f_started_therapy,
                help="Name the primary therapy you're analyzing (can include multiple: 'Acupuncture + Yoga')"
            ) if f_started_therapy else ""

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
            # Therapy tracking logic: inherit from last row unless starting new therapy
            last_row = _get_latest_row()
            if f_started_therapy:
                therapy_on_val = 1
                therapy_name_val = f_therapy_name.strip() if f_therapy_name else ""
            elif last_row is not None and "therapy_on" in last_row:
                therapy_on_val = int(last_row.get("therapy_on", 0))
                therapy_name_val = str(last_row.get("therapy_name", ""))
            else:
                therapy_on_val = 0
                therapy_name_val = ""
            
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
                "therapy_on": therapy_on_val,
                "therapy_name": therapy_name_val,
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
        st.info("No rows yet — add your first day above or use 'Duplicate yesterday' after your first entry.")

# -----------------------------------------------------------------------------
# Settings Tab: Data Management & Export/Import
# -----------------------------------------------------------------------------
with tab_settings:
    st.subheader("⚙️ Settings & Data Management")
    
    st.markdown("### 💾 Data Export & Import")
    st.markdown("""
    Your health data belongs to you. Export it to keep a backup, or import previously saved data.
    
    **Privacy:** All data stays on your device unless you choose to export it.
    """)
    
    # Export section
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.markdown("####📥 Export Your Data")
        if "n1_df" in st.session_state and not st.session_state.n1_df.empty:
            # CSV Export
            csv_data = st.session_state.n1_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"pain_relief_map_data_{dt.date.today().isoformat()}.csv",
                mime="text/csv",
                help="Download all your logged data as a CSV file"
            )
            
            # PDF Report Export
            if st.button("📄 Generate PDF Report", help="Create a printable report for your healthcare provider"):
                # Generate HTML report
                df_export = st.session_state.n1_df.copy()
                df_export["date"] = pd.to_datetime(df_export["date"]).dt.strftime("%d/%m/%Y")
                
                # Calculate summary stats
                avg_pain = df_export["pain_score"].mean()
                avg_stress = df_export["stress_score"].mean()
                avg_sleep = df_export["sleep_hours"].mean()
                
                # Check for therapy tracking
                has_therapy = "therapy_on" in df_export.columns and df_export["therapy_on"].nunique() > 1
                
                therapy_effect_html = ""
                if has_therapy:
                    try:
                        from src.causal import compute_pre_post_effect
                        result = compute_pre_post_effect(
                            df_export,
                            date_col="date",
                            on_col="therapy_on",
                            y_col="pain_score"
                        )
                        
                        # Convert date format if needed (handle cached module issue)
                        start_date_str = result['start_date']
                        if '-' in start_date_str:  # Format is YYYY-MM-DD
                            try:
                                from datetime import datetime
                                date_obj = datetime.strptime(start_date_str, "%Y-%m-%d")
                                result['start_date'] = date_obj.strftime("%d/%m/%Y")
                            except:
                                pass
                        
                        therapy_effect_html = f"""
                        <div style="background: #e8f5e9; padding: 1rem; border-radius: 5px; margin: 1rem 0;">
                            <h3 style="color: #2e7d32;">Therapy Effect Analysis</h3>
                            <p><strong>Therapy:</strong> {df_export[df_export["therapy_name"].notna()]["therapy_name"].iloc[-1] if "therapy_name" in df_export else "Unknown"}</p>
                            <p><strong>Start Date:</strong> {result['start_date']}</p>
                            <p><strong>Effect:</strong> {result['effect_mean']:.2f} points (95% CI: {result['ci_low']:.2f}, {result['ci_high']:.2f})</p>
                            <p><strong>Pre-therapy Pain:</strong> {result['pre_mean']:.2f}/10 (n={result['n_pre']} days)</p>
                            <p><strong>Post-therapy Pain:</strong> {result['post_mean']:.2f}/10 (n={result['n_post']} days)</p>
                        </div>
                        """
                    except:
                        pass
                
                # Generate HTML report
                html_report = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Pain Relief Map - Health Report</title>
                    <style>
                        @media print {{
                            @page {{ margin: 1cm; }}
                        }}
                        body {{
                            font-family: Arial, sans-serif;
                            max-width: 800px;
                            margin: 0 auto;
                            padding: 20px;
                            line-height: 1.6;
                        }}
                        h1 {{ color: #667eea; }}
                        h2 {{ color: #764ba2; border-bottom: 2px solid #764ba2; padding-bottom: 5px; }}
                        .summary-box {{
                            background: #f5f7fa;
                            padding: 1rem;
                            border-radius: 5px;
                            margin: 1rem 0;
                        }}
                        table {{
                            width: 100%;
                            border-collapse: collapse;
                            margin: 1rem 0;
                        }}
                        th, td {{
                            border: 1px solid #ddd;
                            padding: 8px;
                            text-align: left;
                        }}
                        th {{
                            background: #667eea;
                            color: white;
                        }}
                        tr:nth-child(even) {{
                            background: #f9f9f9;
                        }}
                        .footer {{
                            margin-top: 2rem;
                            padding-top: 1rem;
                            border-top: 1px solid #ddd;
                            font-size: 0.9rem;
                            color: #666;
                        }}
                    </style>
                </head>
                <body>
                    <h1>💆🏻‍♀️ Pain Relief Map - Health Report</h1>
                    <p><strong>Generated:</strong> {dt.date.today().strftime("%d/%m/%Y")}</p>
                    <p><strong>Total Days Tracked:</strong> {len(df_export)}</p>
                    <p><strong>Date Range:</strong> {df_export['date'].min()} to {df_export['date'].max()}</p>
                    
                    <h2>📊 Summary Statistics</h2>
                    <div class="summary-box">
                        <p><strong>Average Pain Score:</strong> {avg_pain:.1f}/10</p>
                        <p><strong>Average Stress Score:</strong> {avg_stress:.1f}/10</p>
                        <p><strong>Average Sleep:</strong> {avg_sleep:.1f} hours</p>
                    </div>
                    
                    {therapy_effect_html}
                    
                    <h2>📋 Detailed Log</h2>
                    {df_export[['date', 'pain_score', 'stress_score', 'sleep_hours', 'mood_score', 'therapy_used', 'condition_today']].head(30).to_html(index=False, classes='data-table')}
                    
                    <div class="footer">
                        <p><em>This report was generated by Pain Relief Map, a personal health tracking application.</em></p>
                        <p><em>Data is self-reported and should be discussed with healthcare providers.</em></p>
                    </div>
                </body>
                </html>
                """
                
                st.download_button(
                    label="📄 Download HTML Report",
                    data=html_report,
                    file_name=f"pain_relief_report_{dt.date.today().isoformat()}.html",
                    mime="text/html"
                )
                st.success("✅ Report generated! Open the HTML file and print to PDF from your browser.")
            
            st.caption(f"💡 {len(st.session_state.n1_df)} entries ready to export")
        else:
            st.info("No data to export yet. Start logging in the Daily Log tab!")
    
    with col_exp2:
        st.markdown("#### 📤 Import Previous Data")
        uploaded_file = st.file_uploader(
            "Upload a CSV file",
            type=["csv"],
            help="Restore data from a previously exported CSV file"
        )
        
        if uploaded_file is not None:
            try:
                imported_df = pd.read_csv(uploaded_file)
                
                # Validate required columns
                required_cols = ["date", "pain_score", "sleep_hours", "stress_score", "mood_score"]
                missing_cols = [c for c in required_cols if c not in imported_df.columns]
                
                if missing_cols:
                    st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                else:
                    # Show preview
                    st.success(f"✅ Found {len(imported_df)} entries in uploaded file")
                    st.dataframe(imported_df.head(3), use_container_width=True)
                    
                    if st.button("Import Data", type="primary"):
                        st.session_state.n1_df = imported_df
                        st.success("✅ Data imported successfully! Go to Dashboard to see your trends.")
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
    
    st.divider()
    
    # Demo data management
    st.markdown("### 🎭 Demo Data")
    col_demo1, col_demo2 = st.columns(2)
    
    with col_demo1:
        st.markdown("#### Load Demo Dataset")
        st.caption("Preview the app with 14 days of sample data (Chronic Pain + Acupuncture)")
        
        if st.button("Load Demo Data"):
            demo_path = ROOT / "data" / "templates" / "n_of_1_demo.csv"
            if demo_path.exists():
                demo_df = pd.read_csv(demo_path)
                st.session_state.n1_df = demo_df
                st.success("✅ Demo data loaded! Go to Dashboard to explore.")
                st.rerun()
            else:
                st.error("❌ Demo data file not found.")
    
    with col_demo2:
        st.markdown("#### Clear All Data")
        st.caption("⚠️ This will delete all your logged entries")
        
        if st.button("Clear All Data", type="secondary"):
            if st.checkbox("I understand this will delete all my data"):
                st.session_state.n1_df = pd.DataFrame(columns=[
                    "date", "sex_at_birth", "condition_today", "therapy_used",
                    "pain_score", "sleep_hours", "stress_score", "mood_score",
                    "movement", "digestive_sounds", "bowel_movements_n", "stool_consistency",
                    "physical_symptoms", "emotional_symptoms",
                    "patience_score", "anxiety_score", "cravings",
                    "menstruating_today", "cycle_day", "flow", "pms_symptoms",
                    "good_day", "therapy_on", "therapy_name",
                ])
                st.success("✅ All data cleared.")
                st.rerun()
    
    st.divider()
    
    # About section
    st.markdown("### ℹ️ About Pain Relief Map")
    st.markdown("""
    **Version:** 2.0  
    **Purpose:** Help people with health conditions discover which therapies work for them through scientific evidence and personal tracking.
    
    **Features:**
    - 📊 Track daily symptoms (pain, sleep, stress, mood, etc.)
    - 🔬 Explore clinical trials and research evidence
    - 📈 Analyze therapy effects with bootstrap confidence intervals
    - 💾 Export/import your data (you own it!)
    
    **Data Privacy:**
    - All data stays on your device (local-first)
    - No account required, no data sent to servers
    - You control exports and backups
    
    **Methodology:**
    - N-of-1 trials: You are your own control
    - Pre/post comparison with bootstrap resampling
    - 95% confidence intervals for statistical rigor
    
    **Support:** For questions or issues, see the README.md file in the project repository.
    """)
