#!/usr/bin/env python3
"""
============================================================
🚗 COMMUTE LOGGER & ANALYZER 
============================================================
A comprehensive Python tool designed to track, log, and visuaUSER2e 
daily commute durations using the Google Maps Directions API. 

Features:
- CLI support for automated cron logging.
- Native Streamlit web app for interactive Altair dashboards.
- MQTT Publishing for Home Assistant integration.
- Static PNG Dashboard generation for Home Assistant.

============================================================
🛠️ DEPLOYMENT CHEAT SHEET
============================================================
1. BUILD/RUN THE DOCKER CONTAINER
   docker-compose up -d --build
   (Ensure you map your Home Assistant www folder to the container to see the images:
    -v /path/to/homeassistant/www/commute:/app/ha_export )

2. VIEW THE APP
   Desktop: http://<your-server-ip>:8501
   Mobile:  http://<your-server-ip>:8501/?layout=mobile

3. SET UP AUTOMATED CRON (On Ubuntu Host Machine)
   Run `crontab -e` and add lines to execute inside the container:
   # AM Commute Tracking (USER1 & USER2)                                                                                
    */10 6-9 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER1 log >> /path/to/docker/container/commute_logger/data/commute_cron.log 2>&1                                                               
    */10 6-9 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER2 log >> /path/to/docker/container/commute_logger/data/commute_cron.log 2>&1                                                                 
                                                                                                                   
# PM Commute Tracking (USER1 & USER2)                                                                                
    */10 15-18 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER1 log >> /path/to/docker/container/commute_logger/data/commute_cron.log 2>&1                                                             
    */10 15-18 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py --profile USER2 log >> /path/to/docker/container/commute_logger/data/commute_cron.log 2>&1
   # Optional: Generate the HA image once a day or after peak hours
    0 10,19 * * 1-5 docker exec commute_analyzer python commute_tool_streamlit.py export-ha
============================================================
"""

import argparse
import os
import sys
import json
import requests
from datetime import datetime, timedelta, time
import pytz
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ========================================================
# GLOBAL CONFIGURATION & STYLING
# ========================================================

load_dotenv()
alt.data_transformers.disable_max_rows()

TZ = pytz.timezone("US/Eastern")
API_LOG_FILE = "data/api_daily_log.json"
DAILY_API_LIMIT = 150 
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# --- Theming Colors ---
COLOR_HEATMAP = ["#283618", "#606c38", "#fefae0", "#dda15e", "#bc6c25"]
COLOR_WEEKDAYS = "pastel1"      
COLOR_LINE_AM = "#e7ba52"
COLOR_LINE_PM = "#1f77b4"
COLOR_DUMBBELL_MIN = "#ccebc5"
COLOR_DUMBBELL_MEAN = "#fed9a6"
COLOR_DUMBBELL_MAX = "#fbb4ae"
LINE_THICKNESS = 2      

TIMELINE_WIDTH = 1000       
HEATMAP_WIDTH = 530        
VIOLIN_BLOCK_WIDTH = 600   
BANDS_WIDTH = 270          
DUMBBELL_WIDTH = 270     

HEATMAP_HEIGHT = 200     
VIOLIN_HEIGHT = 260      
BANDS_HEIGHT = 200      
TIMELINE_HEIGHT = 60

TIMELINE_LABEL_WEIGHT = "bold"
TIMELINE_LABEL_SIZE = 13
TIMELINE_UNSELECTED_OPACITY = 0.4

TITLE_HEATMAP_AM = "AM Density & Duration"
TITLE_HEATMAP_PM = "PM Density & Duration"
TITLE_DUMBBELL_AM = "AM Opp. Cost (6:30-8:30)"
TITLE_DUMBBELL_PM = "PM Opp. Cost (3:30-5:00)"

# ============================================================
# UTILITIES & DATA MANAGEMENT
# ============================================================

def now_eastern():
    return datetime.now(tz=TZ)

def get_data_file(profile):
    os.makedirs("data", exist_ok=True)
    return f"data/commute_data_{profile.lower()}.parquet"

def load_api_log():
    if os.path.exists(API_LOG_FILE):
        with open(API_LOG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_api_log(log):
    with open(API_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def check_daily_limit():
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
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    home_lat = os.getenv("HOME_LAT")
    home_lng = os.getenv("HOME_LNG")
    
    prefix = profile.upper()
    work_lat = os.getenv(f"{prefix}_WORK_LAT")
    work_lng = os.getenv(f"{prefix}_WORK_LNG")
    
    if not all([api_key, home_lat, home_lng, work_lat, work_lng]):
        print(f"⚠️ Missing .env config for {profile}. Falling back to fake data.")
        return fake_commute_minutes(direction)

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
            duration_sec = leg.get("duration_in_traffic", leg["duration"])["value"]
            return int(duration_sec / 60.0)
    except Exception as e:
        print(f"⚠️ Request failed: {e}.")
        
    return fake_commute_minutes(direction)

def fake_commute_minutes(direction):
    base = 35 if direction == "AM" else 42
    return max(15, int(base + np.random.normal(0, 8)))

def log_msg(message):
    """Custom print function that automatically adds a timestamp for cron logs."""
    timestamp = now_eastern().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

import os
import json
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Ensure your .env file is actually being loaded into the environment
load_dotenv() 

def publish_to_mqtt(profile, direction, duration, ts):
    """Broadcasts the commute data to an MQTT Broker."""
    
    # --- FETCH CREDENTIALS SECURELY ---
    # os.getenv pulls strings. We must cast the port to an integer!
    broker = os.getenv("MQTT_BROKER")
    port = int(os.getenv("MQTT_PORT", 1883)) 
    mqtt_user = os.getenv("MQTT_USER")
    mqtt_pass = os.getenv("MQTT_PASSWORD")
    # -----------------------------
        
    work_name = os.getenv(f"{profile.upper()}_WORK_NAME", "Work")
    dir_label = f"➔Work" if direction == "AM" else f"➔Home"
        
    payload = {
        "profile": profile,
        "route_label": dir_label,      
        "duration_min": duration,      
        "date_logged": ts.strftime("%a, %b %d"), 
        "time_logged": ts.strftime("%I:%M %p"),  
        "is_am": direction == "AM"
    }
    
    topic = f"commute/{profile.lower()}/latest"
    payload_str = json.dumps(payload)
    
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        
        # Explicitly set the username and password
        client.username_pw_set(mqtt_user, mqtt_pass)
            
        client.connect(broker, port)
        
        # Wait for actual network transmission
        client.loop_start() 
        msg_info = client.publish(topic, payload_str, retain=True)
        msg_info.wait_for_publish() # Blocks script until HA confirms receipt
        client.loop_stop()
        
        client.disconnect()
        
        log_msg(f"📡 MQTT SUCCESS | Topic: {topic} | Payload: {payload_str}")
        
    except Exception as e:
        log_msg(f"❌ MQTT FAILED | Error: {e}")

def log_commute(profile, force_manual=False):
    if not check_daily_limit(): return
    
    ts = now_eastern()
    direction = "AM" if ts.hour < 12 else "PM"
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
    
    if os.path.exists(data_file):
        df = pd.concat([pd.read_parquet(data_file), df_new], ignore_index=True)
    else:
        df = df_new

    df.to_parquet(data_file, index=False)
    
    # --- NEW: Timestamped standard logging ---
    log_msg(f"✅ LOGGED | {profile.capitaUSER2e()} | {direction} Commute | {record['duration_min']} min")
    
    # Send payload to Home Assistant!
    publish_to_mqtt(profile, direction, duration, ts)

def make_fake_row(ts):
    direction = "AM" if ts.hour < 12 else "PM"
    minute_penalty = np.random.randint(5, 20) if (7 <= ts.hour <= 9) or (16 <= ts.hour <= 18) else 0
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
    print("⚠ Generating dense synthetic demo data (every 10 minutes)...")
    start = now_eastern() - timedelta(days=365)
    rows = []
    for d in range(366):
        day = (start + timedelta(days=d)).replace(hour=0, minute=0)
        if day.weekday() >= 5: continue 
        
        t = datetime.combine(day.date(), time(6, 0), tzinfo=TZ)
        while t.time() <= time(11, 0):
            rows.append(make_fake_row(t))
            t += timedelta(minutes=10)
            
        t = datetime.combine(day.date(), time(15, 0), tzinfo=TZ)
        while t.time() <= time(19, 0):
            rows.append(make_fake_row(t))
            t += timedelta(minutes=10)
            
    return pd.DataFrame(rows)

def load_and_prep_data(profile, demo=False, days_limit=None):
    data_file = get_data_file(profile)
    if demo or not os.path.exists(data_file):
        df = generate_demo_data()
    else:
        df = pd.read_parquet(data_file)
        
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ)
    
    # Filtering for Home Assistant Export (e.g., last 14 days only)
    if days_limit:
        cutoff = now_eastern() - timedelta(days=days_limit)
        df = df[df["timestamp"] >= cutoff]
        
    if df.empty: return df
        
    df["time_val"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
    df = df[df["timestamp"].dt.weekday < 5].copy() 
    
    am_mask = (df["time_val"] >= 6) & (df["time_val"] <= 11)
    pm_mask = (df["time_val"] >= 15) & (df["time_val"] <= 19)
    df = df[am_mask | pm_mask].copy()
    df.loc[am_mask, "direction"] = "AM"
    df.loc[pm_mask, "direction"] = "PM"

    df["time_bin"] = df["timestamp"].dt.round("10min")
    dummy_date = datetime.now().date()
    df["plot_time"] = df["time_bin"].apply(lambda x: datetime.combine(dummy_date, x.time()))
    df["plot_time_end"] = df["plot_time"] + timedelta(minutes=10)
    
    return df.sort_values("timestamp")

# ============================================================
# ALTAIR PLOTTING FUNCTIONS
# ============================================================

brush = alt.selection_interval(encodings=['x'], name="TimelineBrush")

def get_timeline_brush(df_raw, w):
    return alt.Chart(df_raw).mark_bar().encode(
        x=alt.X("yearweek(timestamp):T", title=None, axis=alt.Axis(format="%b %Y", tickCount="month", grid=True, zindex=1, labelFontWeight=TIMELINE_LABEL_WEIGHT, labelFontSize=TIMELINE_LABEL_SIZE, domain=False, ticks=False)),
        y=alt.Y("median(duration_min):Q", title=None, axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False)),
        color=alt.Color("median(duration_min):Q", scale=alt.Scale(range=COLOR_HEATMAP), legend=None),
        opacity=alt.condition(brush, alt.value(1.0), alt.value(TIMELINE_UNSELECTED_OPACITY)),
        tooltip=[alt.Tooltip("yearweek(timestamp):T", title="Week"), alt.Tooltip("median(duration_min):Q", title="Weekly Median", format=".0f"), alt.Tooltip("count():Q", title="Commutes Analyzed")]
    ).properties(width=w, height=TIMELINE_HEIGHT).add_params(brush)

def get_heatmap_charts(df_raw, w, apply_brush=True):
    def calc_domain_and_median(df_subset):
        if df_subset.empty: return [0, 25, 50, 75, 100], 50 
        med = df_subset["duration_min"].median()
        mn = df_subset["duration_min"].min()
        mx = df_subset["duration_min"].max()
        return [mn, (mn + med) / 2, med, (med + mx) / 2, mx], med

    am_domain, am_median = calc_domain_and_median(df_raw[df_raw["direction"] == "AM"])
    pm_domain, pm_median = calc_domain_and_median(df_raw[df_raw["direction"] == "PM"])

    base = alt.Chart(df_raw).mark_rect().encode(
        x=alt.X("plot_time:T", title="Time", axis=alt.Axis(format="%H:%M", tickCount=10, labelAngle=-45)),
        x2="plot_time_end:T",
        tooltip=[alt.Tooltip("weekday:N", title="Weekday"), alt.Tooltip("hoursminutes(plot_time):T", title="Time Block"), alt.Tooltip("mean(duration_min):Q", format=".0f", title="Avg Duration (min)"), alt.Tooltip("count():Q", title="Commutes Analyzed")]
    )
    
    if apply_brush:
        base = base.transform_filter(brush) 
    
    am_chart = base.transform_filter(alt.datum.direction == "AM").encode(
        y=alt.Y("weekday:N", sort=WEEKDAY_ORDER, title=None),
        color=alt.Color("mean(duration_min):Q", scale=alt.Scale(domain=am_domain, range=COLOR_HEATMAP), legend=alt.Legend(title=f"AM ({int(am_median)})"))
    ).properties(title=TITLE_HEATMAP_AM, width=w, height=HEATMAP_HEIGHT)

    pm_chart = base.transform_filter(alt.datum.direction == "PM").encode(
        y=alt.Y("weekday:N", sort=WEEKDAY_ORDER, axis=None), 
        color=alt.Color("mean(duration_min):Q", scale=alt.Scale(domain=pm_domain, range=COLOR_HEATMAP), legend=alt.Legend(title=f"PM ({int(pm_median)})"))
    ).properties(title=TITLE_HEATMAP_PM, width=w, height=HEATMAP_HEIGHT)
    
    return am_chart, pm_chart


def get_violin_plots(df_raw, w, is_desktop=True):
    base = alt.Chart(df_raw).transform_calculate(
        day_offset="datum.weekday == 'Monday' ? 0 : datum.weekday == 'Tuesday' ? 1 : datum.weekday == 'Wednesday' ? 2 : datum.weekday == 'Thursday' ? 3 : 4"
    )
    
    def build_violin_side(direction_str, title_str, is_pm=False):
        side_base = base.transform_filter(alt.datum.direction == direction_str).properties(width=w, height=VIOLIN_HEIGHT, title=title_str)
        
        if is_desktop and is_pm:
            y_axis = alt.Axis(orient='right', title='Duration (min)')
        else:
            y_axis = alt.Axis(orient='left', title='Duration (min)')
            
        x_axis = alt.Axis(values=[0, 1, 2, 3, 4], labelExpr="datum.value == 0 ? 'Monday' : datum.value == 1 ? 'Tuesday' : datum.value == 2 ? 'Wednesday' : datum.value == 3 ? 'Thursday' : 'Friday'", title=None, grid=False, tickCount=5, labelAngle=0)
        
        bg_violin = side_base.transform_density(
            'duration_min', as_=['duration', 'density'], groupby=['weekday', 'day_offset'], bandwidth=3, extent=[0, 80]     
        ).transform_calculate(
            x_left="datum.day_offset - datum.density * 3", x_right="datum.day_offset + datum.density * 3"
        ).mark_area(orient='horizontal', color='grey', opacity=0.2).encode(
            y=alt.Y('duration:Q', axis=y_axis), x=alt.X('x_left:Q', axis=x_axis, scale=alt.Scale(domain=[-0.5, 4.5])), x2='x_right:Q', detail='weekday:N'
        )
        
        fg_violin = side_base.transform_filter(brush).transform_density(
            'duration_min', as_=['duration', 'density'], groupby=['weekday', 'day_offset'], bandwidth=3, extent=[0, 80]
        ).transform_calculate(
            x_left="datum.day_offset - datum.density * 3", x_right="datum.day_offset + datum.density * 3"
        ).mark_area(orient='horizontal', stroke='gray', strokeWidth=LINE_THICKNESS).encode(
            y=alt.Y('duration:Q', axis=y_axis), x=alt.X('x_left:Q'), x2='x_right:Q', color=alt.Color('weekday:N', legend=None, scale=alt.Scale(scheme=COLOR_WEEKDAYS)), detail='weekday:N'
        )
        return alt.layer(bg_violin, fg_violin)

    return build_violin_side("AM", "AM Commute Distribution"), build_violin_side("PM", "PM Commute Distribution", is_pm=True)


def get_dumbbell_plots(df_raw, w, apply_brush=True):
    base = alt.Chart(df_raw).transform_calculate(
        h="hours(datum.timestamp) + minutes(datum.timestamp)/60"
    ).transform_filter(
        ((alt.datum.direction == 'AM') & (alt.datum.h >= 6.5) & (alt.datum.h <= 8.5)) |
        ((alt.datum.direction == 'PM') & (alt.datum.h >= 15.5) & (alt.datum.h <= 17.0))
    )

    def build_dumbbell(direction_str, title_str):
        side_base = base.transform_filter(alt.datum.direction == direction_str).properties(title=title_str, width=w, height=BANDS_HEIGHT)
        bg_rule = side_base.mark_rule(color="grey", opacity=0.2, strokeWidth=LINE_THICKNESS).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER, axis=alt.Axis(orient="right", title=None)), x="min(duration_min):Q", x2="max(duration_min):Q")
        
        fg_base = side_base.transform_filter(brush) if apply_brush else side_base
            
        fg_rule = fg_base.mark_rule(color="gray", strokeWidth=LINE_THICKNESS + 1.5).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x=alt.X("min(duration_min):Q", scale=alt.Scale(zero=False), title="Duration (min)"), x2="max(duration_min):Q")
        pt_min = fg_base.mark_circle(size=150, color=COLOR_DUMBBELL_MIN, opacity=1).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x="min(duration_min):Q", tooltip=[alt.Tooltip("min(duration_min):Q", title="Best Average"), alt.Tooltip("count():Q", title="Commutes Analyzed")])
        pt_mean = fg_base.mark_circle(size=150, color=COLOR_DUMBBELL_MEAN, opacity=1).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x="mean(duration_min):Q", tooltip=[alt.Tooltip("mean(duration_min):Q", title="Overall Average"), alt.Tooltip("count():Q", title="Commutes Analyzed")])
        pt_max = fg_base.mark_circle(size=150, color=COLOR_DUMBBELL_MAX, opacity=1).encode(y=alt.Y("weekday:N", sort=WEEKDAY_ORDER), x="max(duration_min):Q", tooltip=[alt.Tooltip("max(duration_min):Q", title="Worst Average"), alt.Tooltip("count():Q", title="Commutes Analyzed")])
        return alt.layer(bg_rule, fg_rule, pt_min, pt_mean, pt_max)

    return build_dumbbell("AM", TITLE_DUMBBELL_AM), build_dumbbell("PM", TITLE_DUMBBELL_PM)


def get_trend_band(df_raw, day, w, show_am=True, show_pm=True, show_y_axis=True):
    dummy_date = datetime.now().date()
    am_domain = [datetime.combine(dummy_date, time(6, 0)).isoformat(), datetime.combine(dummy_date, time(10, 0)).isoformat()]
    pm_domain = [datetime.combine(dummy_date, time(15, 0)).isoformat(), datetime.combine(dummy_date, time(19, 0)).isoformat()]
    
    y_axis = alt.Axis() if show_y_axis else alt.Axis(labels=False, title=None, ticks=False, domain=False)
    y_title = "Duration (min)" if show_y_axis else None

    base = alt.Chart(df_raw)
    if day != "All Week":
        base = base.transform_filter(alt.datum.weekday == day)
        
    layers = []

    if show_am:
        am_base = base.transform_filter(alt.datum.direction == "AM")
        am_bg = am_base.mark_line(strokeWidth=LINE_THICKNESS, color="grey", opacity=0.3, clip=True).encode(y=alt.Y("mean(duration_min):Q", scale=alt.Scale(zero=False), title=y_title, axis=y_axis))
        am_fg_band = am_base.transform_filter(brush).mark_errorband(extent='iqr', opacity=0.2, color=COLOR_LINE_AM, clip=True).encode(y="duration_min:Q")
        am_fg_line = am_base.transform_filter(brush).mark_line(strokeWidth=LINE_THICKNESS + 1, color=COLOR_LINE_AM, clip=True).encode(y="mean(duration_min):Q")
        am_axis = alt.Axis(orient="bottom", format="%H:%M", title="AM" if show_y_axis else None, titleAnchor="start", domainColor=COLOR_LINE_AM, tickColor=COLOR_LINE_AM, titleColor=COLOR_LINE_AM, labelColor=COLOR_LINE_AM, tickCount=5)
        am_layer = alt.layer(am_bg, am_fg_band, am_fg_line).encode(x=alt.X("plot_time:T", scale=alt.Scale(domain=am_domain, nice=False, padding=0), axis=am_axis))
        layers.append(am_layer)

    if show_pm:
        pm_base = base.transform_filter(alt.datum.direction == "PM")
        pm_bg = pm_base.mark_line(strokeWidth=LINE_THICKNESS, color="grey", opacity=0.3, clip=True).encode(y=alt.Y("mean(duration_min):Q", scale=alt.Scale(zero=False), title=y_title, axis=y_axis))
        pm_fg_band = pm_base.transform_filter(brush).mark_errorband(extent='iqr', opacity=0.2, color=COLOR_LINE_PM, clip=True).encode(y="duration_min:Q")
        pm_fg_line = pm_base.transform_filter(brush).mark_line(strokeWidth=LINE_THICKNESS + 1, color=COLOR_LINE_PM, clip=True).encode(y="mean(duration_min):Q")
        pm_orient = "top" if show_am else "bottom" 
        pm_axis = alt.Axis(orient=pm_orient, format="%H:%M", title="PM" if show_y_axis else None, titleAnchor="start", domainColor=COLOR_LINE_PM, tickColor=COLOR_LINE_PM, titleColor=COLOR_LINE_PM, labelColor=COLOR_LINE_PM, tickCount=5)
        pm_layer = alt.layer(pm_bg, pm_fg_band, pm_fg_line).encode(x=alt.X("plot_time:T", scale=alt.Scale(domain=pm_domain, nice=False, padding=0), axis=pm_axis))
        layers.append(pm_layer)

    chart = alt.layer(*layers).resolve_scale(x='independent')
    return chart.properties(title=day, width=w, height=BANDS_HEIGHT)


# ============================================================
# STREAMLIT UI & ASSEMBLY
# ============================================================

def build_dashboard(profile, layout_mode, mobile_view, demo=False):
    df_raw = load_and_prep_data(profile, demo)
    if df_raw.empty: return None
        
    cols_to_keep = ['timestamp', 'weekday', 'direction', 'duration_min', 'plot_time', 'plot_time_end', 'time_val']
    df_charting = df_raw[cols_to_keep].copy()
    df_charting['duration_min'] = df_charting['duration_min'].astype(int)
    work_name = os.getenv(f"{profile.upper()}_WORK_NAME", "Work")

    if layout_mode == "💻 Desktop (Wide)":
        timeline = get_timeline_brush(df_charting, w=TIMELINE_WIDTH)
        heat_am, heat_pm = get_heatmap_charts(df_charting, w=HEATMAP_WIDTH)
        viol_am, viol_pm = get_violin_plots(df_charting, w=VIOLIN_BLOCK_WIDTH, is_desktop=True)
        db_am, db_pm = get_dumbbell_plots(df_charting, w=DUMBBELL_WIDTH)
        
        row_1 = alt.hconcat(*[get_trend_band(df_charting, day, w=BANDS_WIDTH, show_y_axis=(day=="Monday")) for day in ["Monday", "Tuesday", "Wednesday"]], db_am)
        row_2 = alt.hconcat(*[get_trend_band(df_charting, day, w=BANDS_WIDTH, show_y_axis=(day=="Thursday")) for day in ["Thursday", "Friday", "All Week"]], db_pm)
        bands_block = alt.vconcat(row_1, row_2).properties(title=f"Dual-Axis Commute Volatility & Opportunity Cost (Home ↔ {work_name})")

        final_report = alt.vconcat(
            timeline,
            alt.hconcat(heat_am, heat_pm).resolve_scale(color='independent'),
            alt.hconcat(viol_am, viol_pm).resolve_scale(color='independent', y='independent'),
            bands_block
        )
    else: 
        w = "container"
        timeline = get_timeline_brush(df_charting, w=w)
        heat_am, heat_pm = get_heatmap_charts(df_charting, w=w)
        viol_am, viol_pm = get_violin_plots(df_charting, w=w, is_desktop=False)
        db_am, db_pm = get_dumbbell_plots(df_charting, w=w)
        
        is_am = (mobile_view == "☀️ AM Commute")
        
        active_heat = heat_am if is_am else heat_pm
        active_viol = viol_am if is_am else viol_pm
        active_db = db_am if is_am else db_pm
        active_trend = get_trend_band(df_charting, "All Week", w=w, show_am=is_am, show_pm=(not is_am), show_y_axis=True)
        
        bands_block = alt.vconcat(active_trend, active_db).properties(title=f"Commute Volatility & Cost (Home ↔ {work_name})")

        final_report = alt.vconcat(
            timeline,
            active_heat,
            active_viol,
            bands_block
        )

    return final_report.configure_view(
        stroke='#666666',          
        strokeWidth=1
    ).configure_axis(
        grid=False, domain=True, domainColor='#666666', tickColor='#666666'
    )


def run_streamlit_app():
    st.set_page_config(page_title="Commute Analyzer", layout="wide", page_icon="🚗")
    
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["📊 Commute Dashboard", "⚙️ Data Management"], label_visibility="collapsed")
    st.sidebar.divider()
    
    st.sidebar.header("Global Settings")
    selected_profile = st.sidebar.selectbox("Select Profile", ["User 1", "User 2"])
    
    st.sidebar.subheader("Device Optimization")
    query_layout = st.query_params.get("layout", "desktop")
    default_layout_index = 1 if query_layout == "mobile" else 0
    
    layout_mode = st.sidebar.radio(
        "View Layout", 
        ["💻 Desktop (Wide)", "📱 Mobile (Stacked)"], 
        index=default_layout_index
    )
    
    if layout_mode == "📱 Mobile (Stacked)":
        st.query_params["layout"] = "mobile"
    else:
        st.query_params["layout"] = "desktop"
    
    mobile_view = "☀️ AM Commute" 
    if layout_mode == "📱 Mobile (Stacked)":
        mobile_view = st.sidebar.selectbox("Commute Direction", ["☀️ AM Commute", "🌙 PM Commute"])

    use_demo = st.sidebar.checkbox("Use Fake Demo Data", value=False)

    if page == "📊 Commute Dashboard":
        st.title(f"🚗 {selected_profile}'s Commute Dashboard")
        st.markdown("Drag across the timeline below to filter the data for specific weeks or months.")
        
        chart = build_dashboard(selected_profile, layout_mode, mobile_view, use_demo)
        if chart:
            # Replaced use_container_width=True with width="stretch"
            st.altair_chart(chart, width="stretch")
        else:
            st.warning(f"No commute data found for {selected_profile}.")

    # ==========================================
    # PAGE 2: DATA MANAGEMENT
    # ==========================================
    elif page == "⚙️ Data Management":
        st.title("⚙️ Data Management")
        st.markdown("Monitor API limits, manually trigger commute logs, and export raw database files.")
        
        # Load the raw API dictionary
        api_log_data = load_api_log()
        today_str = now_eastern().strftime("%Y-%m-%d")
        api_calls_today = api_log_data.get(today_str, 0)
        
        data_file = get_data_file(selected_profile)
        total_points = 0
        csv_data = None
        
        if os.path.exists(data_file):
            df_full = pd.read_parquet(data_file)
            total_points = len(df_full)
            csv_data = df_full.to_csv(index=False).encode('utf-8')

        st.subheader("System Health")
        col1, col2 = st.columns(2) 
        col1.metric(label="Google API Calls Today", value=f"{api_calls_today} / {DAILY_API_LIMIT}")
        col2.metric(label=f"{selected_profile}'s Database Rows", value=total_points)
        
        # --- NEW: API USAGE TRACE ---
        if api_log_data:
            st.markdown("**14-Day API Usage Trend**")
            # Convert the dictionary {"2024-04-06": 42} into a Pandas DataFrame
            df_api = pd.DataFrame(list(api_log_data.items()), columns=['Date', 'Calls'])
            df_api['Date'] = pd.to_datetime(df_api['Date']).dt.date
            
            # Sort chronologically, grab the last 14 days, and set the date as the index for plotting
            df_api = df_api.sort_values('Date').tail(14)
            df_api = df_api.set_index('Date')
            
            # Draw a sleek, native Streamlit bar chart
            st.bar_chart(df_api, height=150, color="#606c38")
            
        st.divider()
        
        st.subheader("Manual Actions")
        action_col1, action_col2 = st.columns(2)
        
        with action_col1:
            st.markdown("**Force a Log Entry Now**")
            if st.button(f"Log {selected_profile}'s Commute", use_container_width=True):
                with st.spinner('Pinging Google Maps...'):
                    log_commute(selected_profile, force_manual=True)
                st.success("Successfully logged commute!")
                st.rerun() 

        with action_col2:
            st.markdown("**Download Raw Data**")
            if csv_data is not None:
                st.download_button(
                    label=f"⬇️ Export {selected_profile}'s CSV",
                    data=csv_data,
                    file_name=f"{selected_profile.lower()}_commute_data_export.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.button("⬇️ Export CSV", disabled=True, help="No data available", use_container_width=True)        

# ============================================================
# HOME ASSISTANT STATIC EXPORTER
# ============================================================

def export_ha_dashboard():
    """
    Generates a dark-mode PNG image of the last 14 days of heatmaps and dumbbells 
    for both profiles, specifically designed to drop into a Home Assistant card.
    Requires `vl-convert-python` to be installed.
    """
    print("🎨 Generating Home Assistant PNG dashboard...")
    os.makedirs("ha_export", exist_ok=True)
    
    profiles = ["USER1", "USER2"]
    profile_charts = []
    
    for p in profiles:
        df = load_and_prep_data(p, demo=False, days_limit=14)
        if df.empty:
            continue
            
        df['duration_min'] = df['duration_min'].astype(int)
        
        # Build Heatmaps and Dumbbells explicitly without the interactive timeline brush
        heat_am, heat_pm = get_heatmap_charts(df, w=250, apply_brush=False)
        db_am, db_pm = get_dumbbell_plots(df, w=250, apply_brush=False)
        
        # Combine the profile block
        p_block = alt.vconcat(
            alt.hconcat(heat_am, heat_pm).resolve_scale(color='independent'),
            alt.hconcat(db_am, db_pm)
        ).properties(title=f"Last 14 Days: {p}")
        
        profile_charts.append(p_block)
        
    if not profile_charts:
        print("⚠️ No data available to generate HA images.")
        return

    # Stack both profiles vertically
    final_ha_chart = alt.vconcat(*profile_charts).configure(
        background='#111111', # True dark mode for Home Assistant
    ).configure_title(
        color='white', fontSize=18, anchor='middle'
    ).configure_axis(
        labelColor='lightgray', titleColor='lightgray', grid=False, domainColor='gray', tickColor='gray'
    ).configure_legend(
        titleColor='lightgray', labelColor='lightgray'
    ).configure_view(
        stroke='#444444', strokeWidth=1
    )

    try:
        # vl-convert intercepts this save call to bypass the need for a browser engine
        save_path = "data/ha_commute_dashboard.png"
        final_ha_chart.save(save_path, scale_factor=2.0)
        print(f"✅ Saved Home Assistant Dashboard -> {save_path}")
    except Exception as e:
        print(f"❌ Failed to save PNG. Make sure 'vl-convert-python' is installed. Error: {e}")


# ============================================================
# CLI MANAGER
# ============================================================

def export_csv(profile):
    data_file = get_data_file(profile)
    if not os.path.exists(data_file):
        print(f"No parquet file found for {profile}.")
        return
    pd.read_parquet(data_file).to_csv(f"{profile.lower()}_commute_data_export.csv", index=False)
    print(f"✅ Exported -> {profile.lower()}_commute_data_export.csv")


def main_cli():
    parser = argparse.ArgumentParser(description="🚗 Commute Logger & Analyzer")
    parser.add_argument("--profile", choices=["USER1", "USER2"], default="USER1", help="Target user profile")
    
    sub = parser.add_subparsers(dest="cmd")
    log_p = sub.add_parser("log", help="Log commute")
    log_p.add_argument("--manual", action="store_true")
    
    sub.add_parser("export-ha", help="Generates static PNG for Home Assistant")
    sub.add_parser("export-csv", help="Convert Parquet to CSV")
    
    ana_p = sub.add_parser("analyze", help="Compile dashboard (DEPRECATED)")
    ana_p.add_argument("--demo", action="store_true")

    args = parser.parse_args()
    
    if args.cmd == "log": 
        log_commute(args.profile, args.manual)
    elif args.cmd == "export-ha":
        export_ha_dashboard()
    elif args.cmd == "export-csv": 
        export_csv(args.profile)
    elif args.cmd == "analyze": 
        print("⚠️ The standalone analyzer is deprecated. Run: streamlit run commute_tool_streamlit.py")
    else: 
        parser.print_help()

if __name__ == "__main__":
    if st.runtime.exists():
        run_streamlit_app()
    else:
        main_cli()