import streamlit as st

st.set_page_config(page_title="Fitness Tracker 💪", page_icon="🏋️", layout="wide", initial_sidebar_state="expanded")

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from sqlalchemy import text

try:
    from gymbros import (engine, DatabaseError, start_session, get_active_session, end_session,
                         insert_cardio_db, add_weightlift_db, get_personal_records, log_weight_db, get_weight_history)
except ImportError as e:
    st.error(f"❌ Cannot import from gymbros.py: {e}")
    st.stop()

# Authentication
def authenticate_user(username: str, password: str):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT discord_id, username FROM user_credentials WHERE username = :u AND password = :p"),
                                {"u": username, "p": password}).fetchone()
            return result
    except Exception as e:
        st.error(f"Auth error: {e}")
        return None

# Helper functions
def get_history(discord_id: int, limit: int = 5):
    try:
        with engine.connect() as conn:
            return conn.execute(text("""SELECT session_id, date, start_time, end_time, total_calories 
                                       FROM gym_sessions WHERE discord_id = :uid AND end_time IS NOT NULL 
                                       ORDER BY session_id DESC LIMIT :limit"""), 
                              {"uid": discord_id, "limit": limit}).fetchall()
    except Exception as e:
        raise DatabaseError(f"Could not retrieve history: {e}")

def log_food_intake_db(discord_id, entry_date, meal_name, protein, carbs, fats):
    try:
        calories = (protein * 4) + (carbs * 4) + (fats * 9)
        with engine.connect() as conn:
            conn.execute(text("""INSERT INTO food_intake (discord_id, date, meal_name, calories, protein_g, carbs_g, fats_g)
                                VALUES (:uid, :date, :meal, :cal, :prot, :carb, :fat)"""),
                       {"uid": discord_id, "date": entry_date, "meal": meal_name, 
                        "cal": calories, "prot": protein, "carb": carbs, "fat": fats})
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# Exercise database
MUSCLE_GROUPS = {
    "💪 Chest": ["Bench Press", "Incline Bench Press", "Dumbbell Flyes", "Cable Flyes", "Push-Ups"],
    "🦾 Back": ["Pull-Ups", "Lat Pulldown", "Barbell Row", "Dumbbell Row", "Deadlift"],
    "🏋️ Shoulders": ["Overhead Press", "Lateral Raises", "Front Raises", "Rear Delt Flyes"],
    "💪 Biceps": ["Barbell Curl", "Dumbbell Curl", "Hammer Curl", "Preacher Curl"],
    "🔥 Triceps": ["Tricep Dips", "Skull Crushers", "Cable Pushdown", "Close Grip Bench"],
    "🦵 Legs": ["Squat", "Leg Press", "Lunges", "Romanian Deadlift", "Calf Raises"],
    "🎯 Core": ["Plank", "Crunches", "Leg Raises", "Russian Twists", "Ab Wheel"]
}

CARDIO_MACHINES = ["🏃 Treadmill", "🚴 Bike", "🚣 Rowing", "🎿 Elliptical", "🪜 Stair Climber", "🏊 Swimming"]

# Compact CSS
st.markdown("""<style>
div[data-testid="stForm"] p {display: none !important;}
.stButton>button {width: 100%; background: linear-gradient(90deg, #00C9FF, #92FE9D); color: white; 
                  font-weight: bold; border-radius: 10px; padding: 12px; font-size: 16px;}
.success-box {padding: 15px; border-radius: 10px; background: linear-gradient(135deg, #667eea, #764ba2);
              color: white; text-align: center; margin: 10px 0;}
@media (max-width: 768px) {[data-testid="column"] {width: 100% !important;}}
</style>""", unsafe_allow_html=True)

PLOT_CONFIG = {'scrollZoom': False, 'displayModeBar': False}

# Session state
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None

# Sidebar login
with st.sidebar:
    st.title("🏋️ Fitness Tracker")
    st.markdown("---")
    
    if st.session_state.user_id is None:
        st.subheader("👤 Login")
        with st.form("login_form"):
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            if st.form_submit_button("🔐 Login", use_container_width=True):
                if username_input and password_input:
                    user = authenticate_user(username_input, password_input)
                    if user:
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials!")
                else:
                    st.error("⚠️ Fill both fields!")
    else:
        st.success(f"👋 **{st.session_state.username}**")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()

# Main app
if st.session_state.user_id is None:
    st.title("🏋️ Welcome to Fitness Tracker")
    st.markdown("### Please login from the sidebar")
else:
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        ["🏠 Home", "💪 Log", "🥗 Food", "📖 Library", "⚖️ Weight", "📊 Progress", "🏆 PRs", "❓ Help"])
    
    # HOME
    with tab1:
        st.title("🏠 Dashboard")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            try:
                active = get_active_session(st.session_state.user_id)
                st.metric("Session", f"#{active[0]}" if active else "None", "🟢" if active else "⚪")
            except: st.metric("Session", "Error", "❌")
        
        with c2:
            try:
                history = get_history(st.session_state.user_id, 1)
                st.metric("Last", history[0][1].strftime("%b %d") if history else "N/A", 
                         f"{history[0][4] or 0} cal" if history else "")
            except: st.metric("Last", "Error", "")
        
        with c3:
            try:
                weight_hist = get_weight_history(st.session_state.user_id)
                st.metric("Weight", f"{weight_hist[0][1]} kg" if weight_hist else "N/A", "")
            except: st.metric("Weight", "Error", "")
        
        st.markdown("---")
        st.subheader("🎯 Session Control")
        c1, c2 = st.columns(2)
        
        with c1:
            if st.button("▶️ Start Session", use_container_width=True):
                try:
                    active = get_active_session(st.session_state.user_id)
                    if active:
                        st.error(f"⚠️ Active: #{active[0]}")
                    else:
                        sid = start_session(st.session_state.user_id, st.session_state.username)
                        st.success(f"✅ Session #{sid}")
                        st.rerun()
                except DatabaseError as e: st.error(f"❌ {e}")
        
        with c2:
            try:
                active = get_active_session(st.session_state.user_id)
                if active and st.button("⏹️ End Session", use_container_width=True):
                    st.session_state.show_end_form = True
                elif not active:
                    st.button("⏹️ End Session", disabled=True, use_container_width=True)
            except: pass
        
        if hasattr(st.session_state, 'show_end_form') and st.session_state.show_end_form:
            try:
                active = get_active_session(st.session_state.user_id)
                if active:
                    with st.form("end_form"):
                        st.write(f"Ending #{active[0]}")
                        calories = st.number_input("Calories 🔥", min_value=0, value=0)
                        ca, cb = st.columns(2)
                        with ca:
                            if st.form_submit_button("✅ Confirm"):
                                end_session(active[0], calories)
                                st.success(f"✅ #{active[0]} ended!")
                                st.session_state.show_end_form = False
                                st.rerun()
                        with cb:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state.show_end_form = False
                                st.rerun()
            except DatabaseError as e: st.error(f"❌ {e}")
        
        st.markdown("---")
        st.subheader("📜 Recent Workouts")
        try:
            history = get_history(st.session_state.user_id, 5)
            if history:
                df = pd.DataFrame(history, columns=["ID", "Date", "Start", "End", "Calories"])
                st.dataframe(df[['ID', 'Date', 'Calories']], use_container_width=True, hide_index=True)
            else:
                st.info("No sessions yet!")
        except Exception as e: st.error(f"Error: {e}")
    
    # LOG
    with tab2:
        st.title("💪 Log Workout")
        try:
            active = get_active_session(st.session_state.user_id)
            if not active:
                st.warning("⚠️ Start a session first!")
            else:
                st.success(f"✅ Session #{active[0]}")
                workout_type = st.radio("Type:", ["🏋️ Lift", "🏃 Cardio"], horizontal=True)
                
                if workout_type == "🏋️ Lift":
                    muscle_group = st.selectbox("Muscle:", list(MUSCLE_GROUPS.keys()))
                    exercise = st.selectbox("Exercise:", MUSCLE_GROUPS[muscle_group])
                    c1, c2, c3 = st.columns(3)
                    with c1: sets = st.number_input("Sets", 1, value=3)
                    with c2: reps = st.number_input("Reps", 1, value=10)
                    with c3: weight = st.number_input("Weight (kg)", 0, value=20)
                    notes = st.text_area("Notes", max_chars=200)
                    
                    if st.button("✅ Log Lift", use_container_width=True):
                        try:
                            add_weightlift_db(active[0], st.session_state.user_id, st.session_state.username,
                                            exercise, muscle_group.split(" ", 1)[1], sets, reps, weight, notes)
                            st.markdown(f'<div class="success-box"><h3>✅ Logged!</h3><p>{exercise}: {sets}×{reps} @ {weight}kg</p></div>', 
                                      unsafe_allow_html=True)
                        except DatabaseError as e: st.error(f"❌ {e}")
                else:
                    machine = st.selectbox("Activity:", CARDIO_MACHINES)
                    duration = st.number_input("Duration (min)", 1, value=30)
                    c1, c2 = st.columns(2)
                    with c1: distance = st.number_input("Distance (km)", 0.0, step=0.1)
                    with c2: calories = st.number_input("Calories", 0)
                    notes = st.text_area("Notes", max_chars=200)
                    
                    if st.button("✅ Log Cardio", use_container_width=True):
                        try:
                            insert_cardio_db(active[0], st.session_state.user_id, st.session_state.username,
                                           machine.split(" ", 1)[1], duration, 
                                           distance if distance > 0 else None,
                                           calories if calories > 0 else None,
                                           notes if notes else None)
                            st.markdown(f'<div class="success-box"><h3>✅ Logged!</h3><p>{machine.split(" ",1)[1]}: {duration}min • {calories}cal</p></div>', 
                                      unsafe_allow_html=True)
                        except DatabaseError as e: st.error(f"❌ {e}")
        except DatabaseError as e: st.error(f"❌ {e}")
    
    # FOOD
    with tab3:
        st.title("🥗 Food Intake")
        with st.form("food_form"):
            f_date = st.date_input("Date", value=date.today())
            f_meal = st.text_input("Meal Name")
            c1, c2, c3 = st.columns(3)
            with c1: f_prot = st.number_input("Protein (g)", 0.0)
            with c2: f_carb = st.number_input("Carbs (g)", 0.0)
            with c3: f_fats = st.number_input("Fats (g)", 0.0)
            
            if st.form_submit_button("✅ Log Meal"):
                if f_meal:
                    log_food_intake_db(st.session_state.user_id, f_date, f_meal, f_prot, f_carb, f_fats)
                    st.success("✅ Meal logged!")
                else:
                    st.error("Enter meal name")
    
    # LIBRARY
    with tab4:
        st.title("📖 Exercise Library")
        lib_muscle = st.selectbox("Browse:", list(MUSCLE_GROUPS.keys()))
        st.write(f"### {lib_muscle}")
        for ex in MUSCLE_GROUPS[lib_muscle]:
            st.write(f"- {ex}")
    
    # WEIGHT
    with tab5:
        st.title("⚖️ Weight")
        weight_input = st.number_input("Weight (kg)", 0.0, value=70.0, step=0.1)
        
        if st.button("✅ Log Weight", use_container_width=True):
            try:
                log_weight_db(st.session_state.user_id, weight_input)
                st.success(f"✅ {weight_input} kg logged!")
                st.rerun()
            except DatabaseError as e: st.error(f"❌ {e}")
        
        st.markdown("---")
        try:
            weight_hist = get_weight_history(st.session_state.user_id)
            if weight_hist:
                df = pd.DataFrame(weight_hist, columns=["Date", "Weight (kg)"]).sort_values("Date")
                fig = px.line(df, x="Date", y="Weight (kg)", markers=True, title="Weight Trend")
                fig.update_traces(line_color='#00C9FF')
                st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)
            else:
                st.info("No logs yet!")
        except Exception as e: st.error(f"Error: {e}")
    
    # PROGRESS
    with tab6:
        st.title("📊 Progress")
        try:
            sessions = get_history(st.session_state.user_id, 20)
            if sessions:
                df = pd.DataFrame(sessions, columns=["ID", "Date", "Start", "End", "Calories"])
                df['Date'] = pd.to_datetime(df['Date'])
                fig = px.bar(df, x='Date', y='Calories', title="Calories Per Session")
                st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)
            else:
                st.info("No data yet!")
        except Exception as e: st.error(f"Error: {e}")
    
    # PRs
    with tab7:
        st.title("🏆 PRs")
        try:
            prs = get_personal_records(st.session_state.user_id)
            if prs:
                df = pd.DataFrame(prs, columns=["Exercise", "Max (kg)", "Date"])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No PRs yet!")
        except DatabaseError as e: st.error(f"❌ {e}")
    
    # HELP
    with tab8:
        st.title("❓ Help")
        st.markdown("""
        ### Navigation Guide
        1. **🏠 Home** - Start/end sessions
        2. **💪 Log** - Record workouts
        3. **🥗 Food** - Track meals
        4. **📖 Library** - Browse exercises
        5. **⚖️ Weight** - Track weight
        6. **📊 Progress** - View charts
        7. **🏆 PRs** - See records
        """)
