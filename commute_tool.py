#!/usr/bin/env python3
"""
Commute Logger & Analyzer

A comprehensive Python tool designed to track, log, and visualize daily commute
durations using the Google Maps Directions API. 

Features:
- Automated/manual logging of commute times by pinging Google Maps
- In-script API limiting for billing control
- Logging, analysis, and data export in a single script: auto-flipping between AM/PM directions
- Interactive Altair dashboard generation with brush selection of weeks
- Advanced visualizations including density heatmaps, KDE violin plots, and dumbbell charts
- Highly effective data structure with Parquet outputs

Credits: 
- Gemini, ChatGPT used for coding, annotating
"""

import argparse
import os
import json
import requests
from datetime import datetime, timedelta, time
import pytz
import numpy as np
import pandas as pd
import altair as alt
from dotenv import load_dotenv

# ========================================================
# GLOBAL CONFIGURATION & STYLING
# ========================================================

# Load environment variables (API keys, lat/lng coordinates)
load_dotenv()

# Disable Altair's 5000 row limit since datasets will grow over time
alt.data_transformers.disable_max_rows()

# --- 1. System & API Settings ---
TZ = pytz.timezone("US/Eastern")
API_LOG_FILE = "api_daily_log.json"
DAILY_API_LIMIT = 150 
# Enforce a logical weekday sort (Altair defaults to alphabetical)
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# --- 2. Commute Time Windows & Resolution ---
# Used to classify when an automated or manual ping is an AM vs PM commute
MIDDAY_SWITCH_HOUR = 12

# Defines the broad windows for charting AM and PM commutes (24h format)
AM_WINDOW_START = 6
AM_WINDOW_END = 11
PM_WINDOW_START = 15
PM_WINDOW_END = 19

# Defines the peak rush hour periods used specifically for opportunity cost (dumbbell) charts
RUSH_AM_START = 6.5  # 6:30 AM
RUSH_AM_END = 8.5    # 8:30 AM
RUSH_PM_START = 15.5 # 3:30 PM
RUSH_PM_END = 17.0   # 5:00 PM

# Data resolution: How many minutes should each data bucket represent in the dashboard?
# A smaller number (e.g., 5) gives granular detail but requires a lot of logged data to look smooth. 
# 10 or 15 minutes is recommended for standard commuter analysis.
TIME_BIN_MINUTES = 10

# --- 3. Color Palettes ---
# Heatmap: Dark Green (Fastest) -> Light Green -> Creme (Median) -> Light Orange -> Dark Orange (Slowest)
COLOR_HEATMAP = ["#283618", "#606c38", "#fefae0", "#dda15e", "#bc6c25"]
COLOR_WEEKDAYS = "pastel1"       

COLOR_LINE_AM = "#e7ba52"
COLOR_LINE_PM = "#1f77b4"

COLOR_DUMBBELL_MIN = "#ccebc5"
COLOR_DUMBBELL_MEAN = "#fed9a6"
COLOR_DUMBBELL_MAX = "#fbb4ae"

# --- 4. Layout & Bounding Boxes ---
PLOT_BOUNDING_BOX_COLOR = "black"
PLOT_BOUNDING_BOX_WIDTH = 2
LINE_THICKNESS = 2       

# Dimensions for chart blocks
HEATMAP_WIDTH = 580       
HEATMAP_HEIGHT = 200     
VIOLIN_BLOCK_WIDTH = 580 
VIOLIN_HEIGHT = 260       
BANDS_WIDTH = 250         
DUMBBELL_WIDTH = 250    
BANDS_HEIGHT = 200       

# --- 5. Timeline (Brush) Styling ---
TIMELINE_WIDTH = 1180    
TIMELINE_HEIGHT = 60
TIMELINE_GRID_COLOR = "black"
TIMELINE_GRID_WIDTH = 2
TIMELINE_GRID_DASH = []  # Empty array for a solid line; use [4, 4] for dashed
TIMELINE_LABEL_WEIGHT = "bold"
TIMELINE_LABEL_SIZE = 13
TIMELINE_UNSELECTED_OPACITY = 0.4

# --- 6. Chart Titles ---
TITLE_HEATMAP_AM = "AM Density & Duration"
TITLE_HEATMAP_PM = "PM Density & Duration"
TITLE_DUMBBELL_AM = "AM Opp. Cost (6:30-8:30)"
TITLE_DUMBBELL_PM = "PM Opp. Cost (3:30-5:00)"


# ============================================================
# Utilities & Data Management
# ============================================================

def now_eastern():
    """Returns the current timezone-aware datetime in US/Eastern."""
    return datetime.now(tz=TZ)

def ensure_dir(path):
    """Ensures a directory exists, creating it if necessary."""
    os.makedirs(path, exist_ok=True)

def get_data_file(profile):
    """Returns the standardized filename for a user's Parquet data storage."""
    return f"commute_data_{profile.lower()}.parquet"

def load_api_log():
    """Loads the local JSON log used to track daily Google Maps API calls."""
    if os.path.exists(API_LOG_FILE):
        with open(API_LOG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_api_log(log):
    """Saves the API call counts to prevent billing overruns."""
    with open(API_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def check_daily_limit():
    """Checks if the daily Google Maps API limit has been reached to protect billing."""
    today = now_eastern().strftime("%Y-%m-%d")
    log = load_api_log()
    count = log.get(today, 0)
    if count >= DAILY_API_LIMIT:
        print(f"⛔ Daily API limit reached ({DAILY_API_LIMIT}). Skipping.")
        return False
    log[today] = count + 1
    save_api_log(log)
    print(f"📊 API calls today: {log[today]} / {DAILY_API_LIMIT}")
    return True

def get_real_commute_minutes(profile, direction):
    """
    Pings the Google Maps Directions API to get current duration_in_traffic.
    Falls back to generated fake data if API keys/coords are missing or limit reached.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    home_lat = os.getenv("HOME_LAT")
    home_lng = os.getenv("HOME_LNG")
    
    prefix = profile.upper()
    work_lat = os.getenv(f"{prefix}_WORK_LAT")
    work_lng = os.getenv(f"{prefix}_WORK_LNG")
    
    # Check if we have the necessary credentials to make a real call
    if not all([api_key, home_lat, home_lng, work_lat, work_lng]):
        print(f"⚠️ Missing .env config for {profile}. Falling back to fake data.")
        return fake_commute_minutes(direction)

    # Determine origin and destination based on time of day
    home, work = f"{home_lat},{home_lng}", f"{work_lat},{work_lng}"
    origin = home if direction == "AM" else work
    dest = work if direction == "AM" else home

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": origin, "destination": dest, "departure_time": "now", "key": api_key}

    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if data.get("status") == "OK":
            leg = data["routes"][0]["legs"][0]
            # Use 'duration_in_traffic' if available, otherwise fallback to standard 'duration'
            duration_sec = leg.get("duration_in_traffic", leg["duration"])["value"]
            return int(duration_sec / 60.0)
    except Exception as e:
        print(f"⚠️ Request failed: {e}.")
        
    return fake_commute_minutes(direction)

def fake_commute_minutes(direction):
    """Generates a plausible fake commute time based on normal distribution. Use for plotting configuration, tests"""
    base = 35 if direction == "AM" else 42
    return max(15, int(base + np.random.normal(0, 8)))

def log_commute(profile, force_manual=False):
    """Main logging function: fetches current commute duration and appends to the user's parquet file."""
    if not check_daily_limit(): return
    
    ts = now_eastern()
    # Determine AM/PM based on the global MIDDAY_SWITCH_HOUR
    direction = "AM" if ts.hour < MIDDAY_SWITCH_HOUR else "PM"
    duration = get_real_commute_minutes(profile, direction)

    record = {
        "timestamp": ts.isoformat(),
        "timestamp_utc": ts.astimezone(pytz.UTC).isoformat(),
        "weekday": ts.strftime("%A"),
        "weekday_num": ts.weekday(),
        "direction": direction,
        "duration_min": duration,
        "manual": bool(force_manual),
    }

    df_new = pd.DataFrame([record])
    data_file = get_data_file(profile)
    
    # Append to existing file or create new if it doesn't exist
    if os.path.exists(data_file):
        df = pd.concat([pd.read_parquet(data_file), df_new], ignore_index=True)
    else:
        df = df_new

    df.to_parquet(data_file, index=False)
    print(f"\n✅ Logged {profile.capitalize()}'s commute: {record['duration_min']} min")

def make_fake_row(ts):
    """Helper to generate a single fake commute record for demo datasets."""
    direction = "AM" if ts.hour < MIDDAY_SWITCH_HOUR else "PM"
    # Add an artificial penalty during defined rush hours
    is_am_rush = (RUSH_AM_START <= (ts.hour + ts.minute/60.0) <= RUSH_AM_END)
    is_pm_rush = (RUSH_PM_START <= (ts.hour + ts.minute/60.0) <= RUSH_PM_END)
    minute_penalty = np.random.randint(5, 20) if (is_am_rush or is_pm_rush) else 0
    
    return {
        "timestamp": ts.isoformat(),
        "timestamp_utc": ts.astimezone(pytz.UTC).isoformat(),
        "weekday": ts.strftime("%A"),
        "weekday_num": ts.weekday(),
        "direction": direction,
        "duration_min": fake_commute_minutes(direction) + minute_penalty,
        "manual": False,
    }

def generate_demo_data():
    """Generates a dense, 1-year synthetic dataset based on the configured TIME_BIN_MINUTES."""
    print(f"⚠ Generating dense synthetic demo data (every {TIME_BIN_MINUTES} minutes)...")
    start = now_eastern() - timedelta(days=365)
    rows = []
    
    for d in range(366):
        day = (start + timedelta(days=d)).replace(hour=0, minute=0)
        if day.weekday() >= 5: continue # Skip weekends
        
        # Morning commutes (using global config variables)
        t = datetime.combine(day.date(), time(AM_WINDOW_START, 0), tzinfo=TZ)
        while t.time() <= time(AM_WINDOW_END, 0):
            rows.append(make_fake_row(t))
            t += timedelta(minutes=TIME_BIN_MINUTES)
            
        # Evening commutes (using global config variables)
        t = datetime.combine(day.date(), time(PM_WINDOW_START, 0), tzinfo=TZ)
        while t.time() <= time(PM_WINDOW_END, 0):
            rows.append(make_fake_row(t))
            t += timedelta(minutes=TIME_BIN_MINUTES)
            
    return pd.DataFrame(rows)

def load_and_prep_data(profile, demo=False):
    """
    Loads data from disk and engineers necessary features (time bins, masks) for plotting.
    Filters out weekends and cleans up timestamps.
    """
    data_file = get_data_file(profile)
    if demo or not os.path.exists(data_file):
        df = generate_demo_data()
    else:
        df = pd.read_parquet(data_file)
        
    # Ensure correct timezones
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ)
    # Create a decimal representation of time (e.g., 6:30 -> 6.5) for easier filtering
    df["time_val"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
    
    # Keep only weekdays (Monday=0, Friday=4)
    df = df[df["timestamp"].dt.weekday < 5].copy() 
    
    # Segregate AM and PM windows using global config constants
    am_mask = (df["time_val"] >= AM_WINDOW_START) & (df["time_val"] <= AM_WINDOW_END)
    pm_mask = (df["time_val"] >= PM_WINDOW_START) & (df["time_val"] <= PM_WINDOW_END)
    df = df[am_mask | pm_mask].copy()
    df.loc[am_mask, "direction"] = "AM"
    df.loc[pm_mask, "direction"] = "PM"

    # Snap timestamps to configured buckets to enforce uniform grouping in visual densities
    df["time_bin"] = df["timestamp"].dt.round(f"{TIME_BIN_MINUTES}min")
    
    # Altair plots times best when they all share a single 'dummy' date.
    # We strip the real dates here so the X-axis only cares about the hour/minute.
    dummy_date = datetime.now().date()
    df["plot_time"] = df["time_bin"].apply(lambda x: datetime.combine(dummy_date, x.time()))
    df["plot_time_end"] = df["plot_time"] + timedelta(minutes=TIME_BIN_MINUTES)
    
    return df.sort_values("timestamp")

# ============================================================
# Interactive Elements (Brush)
# ============================================================

# Global interactive selection brush linked to the X-axis of the timeline chart.
# Filtering this brush automatically updates all linked charts in the final dashboard.
brush = alt.selection_interval(encodings=['x'], name="TimelineBrush")

# ============================================================
# Plotting Functions
# ============================================================

def get_heatmap_chart(df_raw):
    """Generates the primary AM/PM heatmaps showing commute duration by time-of-day."""
    
    def calc_domain_and_median(df_subset):
        """Helper to calculate a 5-point diverging color domain anchored on the actual median."""
        if df_subset.empty: return [0, 25, 50, 75, 100], 50 # Safe fallback
        med = df_subset["duration_min"].median()
        mn = df_subset["duration_min"].min()
        mx = df_subset["duration_min"].max()
        return [mn, (mn + med) / 2, med, (med + mx) / 2, mx], med

    # Calculate truly independent domains and medians for AM and PM to prevent scale bleed
    am_domain, am_median = calc_domain_and_median(df_raw[df_raw["direction"] == "AM"])
    pm_domain, pm_median = calc_domain_and_median(df_raw[df_raw["direction"] == "PM"])

    # Base chart encoding with smart tooltips displaying data counts
    base = alt.Chart(df_raw).mark_rect().encode(
        x=alt.X("plot_time:T", title="Time", axis=alt.Axis(format="%H:%M", tickCount=10, labelAngle=-45)),
        x2="plot_time_end:T",
        tooltip=[
            alt.Tooltip("weekday:N", title="Weekday"), 
            alt.Tooltip("hoursminutes(plot_time):T", title="Time Block"), 
            alt.Tooltip("mean(duration_min):Q", format=".0f", title="Avg Duration (min)"),
            alt.Tooltip("count():Q", title="Commutes Analyzed") # Smart tooltip added here!
        ]
    ).transform_filter(brush) 
    
    am_chart = base.transform_filter(alt.datum.direction == "AM").encode(
        y=alt.Y("weekday:N", sort=WEEKDAY_ORDER, title=None),
        color=alt.Color(
            "mean(duration_min):Q", 
            scale=alt.Scale(domain=am_domain, range=COLOR_HEATMAP), 
            legend=alt.Legend(title=f"AM ({int(am_median)})") 
        )
    ).properties(title=TITLE_HEATMAP_AM, width=HEATMAP_WIDTH, height=HEATMAP_HEIGHT)

    pm_chart = base.transform_filter(alt.datum.direction == "PM").encode(
        y=alt.Y("weekday:N", sort=WEEKDAY_ORDER, axis=None), # Hide Y-axis labels on right chart
        color=alt.Color(
            "mean(duration_min):Q", 
            scale=alt.Scale(domain=pm_domain, range=COLOR_HEATMAP), 
            legend=alt.Legend(title=f"PM ({int(pm_median)})") 
        )
    ).properties(title=TITLE_HEATMAP_PM, width=HEATMAP_WIDTH, height=HEATMAP_HEIGHT)
    
    return (am_chart | pm_chart).resolve_scale(color='independent')


def get_violin_plots(df_raw):
    """Generates Kernel Density Estimation (KDE) violin plots for overall spread."""
    # Convert weekday strings to numeric offsets for manual categorical placing
    base = alt.Chart(df_raw).transform_calculate(
        day_offset="""
            datum.weekday == 'Monday' ? 0 : datum.weekday == 'Tuesday' ? 1 :
            datum.weekday == 'Wednesday' ? 2 : datum.weekday == 'Thursday' ? 3 : 4
        """
    )
    
    def build_violin_side(direction_str, title_str, is_pm=False):
        side_base = base.transform_filter(alt.datum.direction == direction_str).properties(width=VIOLIN_BLOCK_WIDTH, height=VIOLIN_HEIGHT, title=title_str)
        y_axis = alt.Axis(labels=False, ticks=False, title=None) if is_pm else alt.Axis(title='Duration (min)')
        x_axis = alt.Axis(values=[0, 1, 2, 3, 4], labelExpr="datum.value == 0 ? 'Monday' : datum.value == 1 ? 'Tuesday' : datum.value == 2 ? 'Wednesday' : datum.value == 3 ? 'Thursday' : 'Friday'", title=None, grid=False, tickCount=5, labelAngle=0)
        
        # Background violins (unfiltered, shows all-time distribution)
        bg_violin = side_base.transform_density(
            'duration_min', 
            as_=['duration', 'density'], 
            groupby=['weekday', 'day_offset'],
            bandwidth=3,       # Forces a smooth curve even when daily standard deviation is very low
            extent=[0, 80]     # Prevents math from calculating negative commute minutes
        ).transform_calculate(
            x_left="datum.day_offset - datum.density * 3",   # Multiplier keeps curve inside its lane
            x_right="datum.day_offset + datum.density * 3"
        ).mark_area(orient='horizontal', color='grey', opacity=0.2).encode(
            y=alt.Y('duration:Q', axis=y_axis), x=alt.X('x_left:Q', axis=x_axis, scale=alt.Scale(domain=[-0.5, 4.5])), x2='x_right:Q', detail='weekday:N'
        )
        
        # Foreground violins (filtered by timeline brush)
        fg_violin = side_base.transform_filter(brush).transform_density(
            'duration_min', 
            as_=['duration', 'density'], 
            groupby=['weekday', 'day_offset'],
            bandwidth=3,       
            extent=[0, 80]
        ).transform_calculate(
            x_left="datum.day_offset - datum.density * 3", 
            x_right="datum.day_offset + datum.density * 3"
        ).mark_area(orient='horizontal', stroke='black', strokeWidth=LINE_THICKNESS).encode(
            y=alt.Y('duration:Q'), x=alt.X('x_left:Q'), x2='x_right:Q',
            color=alt.Color('weekday:N', legend=None, scale=alt.Scale(scheme=COLOR_WEEKDAYS)), detail='weekday:N'
        )
        
        return alt.layer(bg_violin, fg_violin)

    return (build_violin_side("AM", "AM Commute Distribution") | build_violin_side("PM", "PM Commute Distribution", is_pm=True)).resolve_scale(color='independent')


def get_dumbbell_plots(df_raw):
    """Generates Dumbbell plots illustrating the min, mean, and max commute during peak rush hour."""
    # Filter data to just the heaviest rush hour traffic windows as defined in Global Config
    base = alt.Chart(df_raw).transform_calculate(
        h="hours(datum.timestamp) + minutes(datum.timestamp)/60"
    ).transform_filter(
        ((alt.datum.direction == 'AM') & (alt.datum.h >= RUSH_AM_START) & (alt.datum.h <= RUSH_AM_END)) |
        ((alt.datum.direction == 'PM') & (alt.datum.h >= RUSH_PM_START) & (alt.datum.h <= RUSH_PM_END))
    )

    def build_dumbbell(direction_str, title_str):
        side_base = base.transform_filter(alt.datum.direction == direction_str).properties(title=title_str, width=DUMBBELL_WIDTH, height=BANDS_HEIGHT)
        
        # Background static rule
        bg_rule = side_base.mark_rule(color="grey", opacity=0.2, strokeWidth=LINE_THICKNESS).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER, axis=alt.Axis(orient="right", title=None)), x="min(duration_min):Q", x2="max(duration_min):Q")
        
        # Foreground interactive rule
        fg_base = side_base.transform_filter(brush)
        fg_rule = fg_base.mark_rule(color="gray", strokeWidth=LINE_THICKNESS + 1.5).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x=alt.X("min(duration_min):Q", scale=alt.Scale(zero=False), title="Duration (min)"), x2="max(duration_min):Q")
        
        # Min, Mean, Max interactive dots with smart data-count tooltips
        pt_min = fg_base.mark_circle(size=150, color=COLOR_DUMBBELL_MIN, opacity=1).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x="min(duration_min):Q", tooltip=[alt.Tooltip("min(duration_min):Q", title="Best Average"), alt.Tooltip("count():Q", title="Commutes Analyzed")])
        pt_mean = fg_base.mark_circle(size=150, color=COLOR_DUMBBELL_MEAN, opacity=1).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x="mean(duration_min):Q", tooltip=[alt.Tooltip("mean(duration_min):Q", title="Overall Average"), alt.Tooltip("count():Q", title="Commutes Analyzed")])
        pt_max = fg_base.mark_circle(size=150, color=COLOR_DUMBBELL_MAX, opacity=1).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x="max(duration_min):Q", tooltip=[alt.Tooltip("max(duration_min):Q", title="Worst Average"), alt.Tooltip("count():Q", title="Commutes Analyzed")])
        
        return alt.layer(bg_rule, fg_rule, pt_min, pt_mean, pt_max)

    return build_dumbbell("AM", TITLE_DUMBBELL_AM), build_dumbbell("PM", TITLE_DUMBBELL_PM)


def get_layout_row(df_raw, days_list, dumbbell_chart):
    """Generates the Line and Error Band charts, arranged into rows with the Dumbbell appended."""
    dummy_date = datetime.now().date()
    
    # Establish domains using our Global Configurations to keep axes uniform
    am_domain = [datetime.combine(dummy_date, time(AM_WINDOW_START, 0)).isoformat(), datetime.combine(dummy_date, time(AM_WINDOW_END, 0)).isoformat()]
    pm_domain = [datetime.combine(dummy_date, time(PM_WINDOW_START, 0)).isoformat(), datetime.combine(dummy_date, time(PM_WINDOW_END, 0)).isoformat()]
    
    charts = []
    
    for day in days_list:
        is_leftmost = day in ["Monday", "Thursday"]
        y_axis = alt.Axis() if is_leftmost else alt.Axis(labels=False, title=None, ticks=False, domain=False)
        y_title = "Duration (min)" if is_leftmost else None

        base = alt.Chart(df_raw)
        if day != "All Week":
            base = base.transform_filter(alt.datum.weekday == day)
        
        # Construct AM block
        am_base = base.transform_filter(alt.datum.direction == "AM")
        am_bg = am_base.mark_line(strokeWidth=LINE_THICKNESS, color="grey", opacity=0.3, clip=True).encode(y=alt.Y("mean(duration_min):Q", scale=alt.Scale(zero=False), title=y_title, axis=y_axis))
        am_fg_band = am_base.transform_filter(brush).mark_errorband(extent='iqr', opacity=0.2, color=COLOR_LINE_AM, clip=True).encode(y="duration_min:Q")
        am_fg_line = am_base.transform_filter(brush).mark_line(strokeWidth=LINE_THICKNESS + 1, color=COLOR_LINE_AM, clip=True).encode(y="mean(duration_min):Q")
        am_axis = alt.Axis(orient="bottom", format="%H:%M", title="AM" if is_leftmost else None, titleAnchor="start", domainColor=COLOR_LINE_AM, tickColor=COLOR_LINE_AM, titleColor=COLOR_LINE_AM, labelColor=COLOR_LINE_AM, tickCount=5)
        am_layer = alt.layer(am_bg, am_fg_band, am_fg_line).encode(x=alt.X("plot_time:T", scale=alt.Scale(domain=am_domain, nice=False, padding=0), axis=am_axis))

        # Construct PM block
        pm_base = base.transform_filter(alt.datum.direction == "PM")
        pm_bg = pm_base.mark_line(strokeWidth=LINE_THICKNESS, color="grey", opacity=0.3, clip=True).encode(y=alt.Y("mean(duration_min):Q", scale=alt.Scale(zero=False), title=y_title, axis=y_axis))
        pm_fg_band = pm_base.transform_filter(brush).mark_errorband(extent='iqr', opacity=0.2, color=COLOR_LINE_PM, clip=True).encode(y="duration_min:Q")
        pm_fg_line = pm_base.transform_filter(brush).mark_line(strokeWidth=LINE_THICKNESS + 1, color=COLOR_LINE_PM, clip=True).encode(y="mean(duration_min):Q")
        pm_axis = alt.Axis(orient="top", format="%H:%M", title="PM" if is_leftmost else None, titleAnchor="start", domainColor=COLOR_LINE_PM, tickColor=COLOR_LINE_PM, titleColor=COLOR_LINE_PM, labelColor=COLOR_LINE_PM, tickCount=5)
        pm_layer = alt.layer(pm_bg, pm_fg_band, pm_fg_line).encode(x=alt.X("plot_time:T", scale=alt.Scale(domain=pm_domain, nice=False, padding=0), axis=pm_axis))

        charts.append(alt.layer(am_layer, pm_layer).resolve_scale(x='independent').properties(title=day, width=BANDS_WIDTH, height=BANDS_HEIGHT))
        
    charts.append(dumbbell_chart)
    return alt.hconcat(*charts)


def get_timeline_brush(df_raw):
    """Generates the master interactive timeline bar chart used to filter all other graphs."""
    return alt.Chart(df_raw).mark_bar().encode(
        x=alt.X(
            "yearweek(timestamp):T", 
            title=None, 
            axis=alt.Axis(
                format="%b %Y", 
                tickCount="month",
                grid=True,
                gridColor=TIMELINE_GRID_COLOR,
                gridWidth=TIMELINE_GRID_WIDTH,
                gridDash=TIMELINE_GRID_DASH,
                zindex=1,                        
                labelFontWeight=TIMELINE_LABEL_WEIGHT,
                labelFontSize=TIMELINE_LABEL_SIZE,
                domain=False,
                ticks=False
            )
        ),
        y=alt.Y(
            "median(duration_min):Q", 
            title=None,
            axis=alt.Axis(
                labels=False,
                ticks=False,
                domain=False,
                grid=False
            )
        ),
        color=alt.Color("median(duration_min):Q", scale=alt.Scale(range=COLOR_HEATMAP), legend=None),
        opacity=alt.condition(brush, alt.value(1.0), alt.value(TIMELINE_UNSELECTED_OPACITY)),
        tooltip=[
            alt.Tooltip("yearweek(timestamp):T", title="Week"), 
            alt.Tooltip("median(duration_min):Q", title="Weekly Median", format=".0f"),
            alt.Tooltip("count():Q", title="Commutes Analyzed") # Smart tooltip added here!
        ]
    ).properties(
        width=TIMELINE_WIDTH, 
        height=TIMELINE_HEIGHT
    ).add_params(brush)

# ============================================================
# Core Logic & HTML Assembly
# ============================================================

def analyze(profile, demo=False):
    """Orchestrates data loading, chart building, and final HTML file assembly."""
    df_raw = load_and_prep_data(profile, demo)
    if df_raw.empty:
        print(f"❌ No data found for {profile}.")
        return
        
    cols_to_keep = [
        'timestamp', 'weekday', 'direction', 'duration_min', 
        'plot_time', 'plot_time_end', 'time_val'
    ]
    df_charting = df_raw[cols_to_keep].copy()
    df_charting['duration_min'] = df_charting['duration_min'].astype(int)

    work_name = os.getenv(f"{profile.upper()}_WORK_NAME", "Work")
    print(f"📊 Generating highly-interactive dynamic dashboard for {profile}...")
    
    # Generate distinct chart components
    chart_heatmaps = get_heatmap_chart(df_charting)
    chart_violins = get_violin_plots(df_charting)
    am_dumbbell, pm_dumbbell = get_dumbbell_plots(df_charting)
    
    # Layout assembly
    row_1_bands = get_layout_row(df_charting, ["Monday", "Tuesday", "Wednesday"], am_dumbbell)
    row_2_bands = get_layout_row(df_charting, ["Thursday", "Friday", "All Week"], pm_dumbbell)
    timeline_chart = get_timeline_brush(df_charting)
    
    bands_block = alt.vconcat(row_1_bands, row_2_bands).properties(title=f"Dual-Axis Commute Volatility & Opportunity Cost (Home ↔ {work_name})")

    # Final Vertical Concat of all layers
    final_report = alt.vconcat(
        timeline_chart,
        chart_heatmaps,
        chart_violins,
        bands_block
    ).resolve_scale(
        color='independent'
    ).configure_view(
        stroke=PLOT_BOUNDING_BOX_COLOR,          
        strokeWidth=PLOT_BOUNDING_BOX_WIDTH
    ).configure_axis(
        grid=False, domain=True, domainColor='black', domainWidth=LINE_THICKNESS, tickColor='black', tickWidth=LINE_THICKNESS
    )

    mode = "Demo" if demo else "Real"
    summary_path = f"{profile}_Analysis_Report_{mode}.html"
    final_report.save(summary_path)
    
    # Inject custom CSS to make the final HTML file look clean and centered
    with open(summary_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    css_injection = """
    <style>
        body { font-family: sans-serif; padding-top: 10px; display: flex; flex-direction: column; align-items: center; background: #f8f9fa;}
        .title-text { color: #555; font-size: 14px; margin-bottom: 10px; }
        .vega-embed { display: flex; justify-content: center; width: 100%; box-shadow: 0px 4px 15px rgba(0,0,0,0.1); padding: 20px; background: white; border-radius: 8px;}
    </style>
    """
    
    html_content = html_content.replace('<head>', f'<head>\n{css_injection}')
    html_content = html_content.replace('<body>', f'<body>\n<div class="title-text">{profile.capitalize()}\'s Commute: Home ↔ {work_name}</div>')
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Analysis saved to: {summary_path}")

# ============================================================
# CLI Command Implementations
# ============================================================

def export_csv(profile):
    """Utility to export Parquet dataframe to raw CSV for external use."""
    data_file = get_data_file(profile)
    if not os.path.exists(data_file):
        print(f"No parquet file found for {profile}.")
        return
    pd.read_parquet(data_file).to_csv(f"{profile.lower()}_commute_data_export.csv", index=False)
    print(f"✅ Exported -> {profile.lower()}_commute_data_export.csv")
    
def main():
    """CLI Argument parser and entry point."""
    
    # Expanded description for better CLI documentation
    parser = argparse.ArgumentParser(
        description="🚗 Commute Logger & Analyzer\n\nTrack, log, and visualize your daily commute duration.",
        epilog="Examples:\n  python script.py log --profile USER1\n  python script.py analyze --demo",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "--profile", 
        choices=["USER1", "USER2"], 
        default="USER1", 
        help="Target user profile to pull .env configs and save data under (default: USER1)."
    )
    
    sub = parser.add_subparsers(dest="cmd", required=True, help="Available commands")
    
    # Command: LOG
    log_p = sub.add_parser("log", help="Ping Google Maps API and save the current commute time.")
    log_p.add_argument(
        "--manual", 
        action="store_true", 
        help="Flag the entry as manually triggered rather than via an automated cron job."
    )
    
    # Command: ANALYZE
    ana_p = sub.add_parser("analyze", help="Compile an interactive Altair HTML dashboard.")
    ana_p.add_argument(
        "--demo", 
        action="store_true", 
        help="Generate and visualize a year's worth of synthetic data instead of loading saved Parquet data (useful for testing UI)."
    )
    
    # Command: EXPORT-CSV
    sub.add_parser("export-csv", help="Convert the logged Parquet data to a human-readable CSV file.")

    args = parser.parse_args()
    
    if args.cmd == "log": 
        log_commute(args.profile, args.manual)
    elif args.cmd == "analyze": 
        analyze(args.profile, args.demo)
    elif args.cmd == "export-csv": 
        export_csv(args.profile)

if __name__ == "__main__":
    main()