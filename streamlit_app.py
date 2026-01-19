import streamlit as st

# PAGE CONFIG MUST BE FIRST!
st.set_page_config(
    page_title="Fitness Tracker 💪",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Now import everything else
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text

# ---------------------------
# DATABASE & ENGINE SETUP
# ---------------------------

# Pulling credentials and names from YOUR Secrets/Variables
DB_USER = st.secrets["DB_USER"]
DB_PASS = st.secrets["DB_PASS"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
db_prod_name = st.secrets["DB_NAME"]          
db_test_name = st.secrets["DB_NAME_TESTING"]  

# Create the pipes (engines) using those variables
engine_prod = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{db_prod_name}")
engine_test = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{db_test_name}")

# Default the active engine to production in session state
if 'active_engine' not in st.session_state:
    st.session_state.active_engine = engine_prod

# Import all functions from your existing gymbros.py
try:
    from gymbros import (
        DatabaseError,
        start_session,
        get_active_session,
        end_session,
        insert_cardio_db,
        add_weightlift_db,
        get_session_details,
        get_personal_records,
        log_weight_db,
        get_weight_history
    )
except ImportError as e:
    st.error(f"❌ Cannot import from gymbros.py: {e}")
    st.info("Make sure gymbros.py is in the same directory as streamlit_app.py")
    st.stop()

# ---------------------------
# AUTHENTICATION FUNCTIONS
# ---------------------------

def authenticate_user(username: str, password: str):
    """Authenticate user. Always checks against PROD engine for credentials."""
    try:
        with engine_prod.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT discord_id, username 
                    FROM user_credentials 
                    WHERE username = :username AND password = :password
                """),
                {"username": username, "password": password}
            ).fetchone()
            return result 
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

# ---------------------------
# HELPER FUNCTIONS (Route to active_engine)
# ---------------------------

def get_history(discord_id: int, limit: int = 5):
    """Get workout history using the currently active engine"""
    try:
        with st.session_state.active_engine.connect() as conn:
            sessions = conn.execute(
                text("""
                    SELECT session_id, date, start_time, end_time, total_calories
                    FROM gym_sessions
                    WHERE discord_id = :uid AND end_time IS NOT NULL
                    ORDER BY session_id DESC
                    LIMIT :limit
                """), {"uid": discord_id, "limit": limit}
            ).fetchall()
            return sessions
    except Exception as e:
        raise DatabaseError(f"Could not retrieve history: {e}")

def test_db_connection():
    """Test and wake up the active database"""
    try:
        with st.session_state.active_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        st.error(f"⚠️ Database is waking up... Please refresh in 10 seconds.")
        return False

def log_food_intake_db(discord_id, entry_date, meal_name, protein, carbs, fats):
    """Inserts food data into the active database"""
    try:
        calories = (protein * 4) + (carbs * 4) + (fats * 9)
        with st.session_state.active_engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO food_intake (discord_id, date, meal_name, calories, protein_g, carbs_g, fats_g)
                    VALUES (:uid, :date, :meal, :cal, :prot, :carb, :fat)
                """),
                {"uid": discord_id, "date": entry_date, "meal": meal_name, 
                 "cal": calories, "prot": protein, "carb": carbs, "fat": fats}
            )
            conn.commit()
        return True
    except Exception as e:
        st.error(f"Error logging food: {e}")
        return False

# ---------------------------
# EXERCISE DATABASE
# ---------------------------

MUSCLE_GROUPS = {
    "💪 Chest": ["Bench Press", "Incline Bench Press", "Decline Bench Press", "Dumbbell Flyes", "Cable Flyes", "Push-Ups", "Chest Press Machine", "Pec Deck"],
    "🦾 Back": ["Pull-Ups", "Lat Pulldown", "Barbell Row", "Dumbbell Row", "T-Bar Row", "Cable Row", "Deadlift", "Face Pulls"],
    "🏋️ Shoulders": ["Overhead Press", "Dumbbell Shoulder Press", "Lateral Raises", "Front Raises", "Rear Delt Flyes", "Arnold Press", "Upright Row", "Shrugs"],
    "💪 Biceps": ["Barbell Curl", "Dumbbell Curl", "Hammer Curl", "Preacher Curl", "Cable Curl", "Concentration Curl", "21s"],
    "🔥 Triceps": ["Tricep Dips", "Skull Crushers", "Overhead Tricep Extension", "Cable Pushdown", "Close Grip Bench Press", "Diamond Push-Ups"],
    "🦵 Legs": ["Squat", "Leg Press", "Leg Extension", "Leg Curl", "Lunges", "Romanian Deadlift", "Calf Raises", "Bulgarian Split Squat"],
    "🎯 Core": ["Plank", "Crunches", "Leg Raises", "Russian Twists", "Cable Crunches", "Ab Wheel", "Hanging Knee Raises"]
}
CARDIO_MACHINES = ["🏃 Treadmill", "🚴 Stationary Bike", "🚣 Rowing Machine", "🎿 Elliptical", "🪜 Stair Climber", "🏊 Swimming", "🥊 Boxing", "🎾 Sports"]

# ---------------------------
# MOBILE-RESPONSIVE CSS
# ---------------------------

st.markdown("""
<style>
    div[data-testid="stForm"] p { display: none !important; }
    .main { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
    .stButton>button {
        width: 100%; background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%);
        color: white; font-weight: bold; border-radius: 10px; border: none;
        padding: 12px 20px; transition: 0.3s; font-size: 16px;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
    div[data-testid="stMetricValue"] { font-size: clamp(20px, 4vw, 28px); font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: clamp(12px, 2.5vw, 14px); }
    .success-box {
        padding: 15px; border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; text-align: center; margin: 10px 0;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>select {
        font-size: 16px !important; padding: 10px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 5px; overflow-x: auto; }
    .stTabs [data-baseweb="tab"] { font-size: clamp(12px, 3vw, 14px); padding: 8px 12px; white-space: nowrap; }
    @media (max-width: 768px) {
        .stButton>button { padding: 15px 10px; font-size: 14px; }
        h1 { font-size: 24px !important; }
        [data-testid="column"] { width: 100% !important; flex: 100% !important; }
    }
</style>
""", unsafe_allow_html=True)

PLOT_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'staticPlot': False}

# ---------------------------
# SESSION STATE
# ---------------------------

if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None

# ---------------------------
# SIDEBAR
# ---------------------------

if not test_db_connection():
    st.stop()

with st.sidebar:
    st.title("🏋️ Fitness Tracker")
    st.markdown("---")
    
    if st.session_state.user_id is None:
        st.subheader("👤 Login")
        with st.form("login_form"):
            username_input = st.text_input("Username")
            password_input = st.text_input("Password", type="password")
            if st.form_submit_button("🔐 Login", use_container_width=True):
                user = authenticate_user(username_input, password_input)
                if user:
                    st.session_state.user_id = user[0]
                    st.session_state.username = user[1]
                    
                    # SWITCH LOGIC
                    if username_input.lower() == "admin":
                        st.session_state.active_engine = engine_test
                    else:
                        st.session_state.active_engine = engine_prod
                    st.rerun()
                else:
                    st.error("❌ Invalid Login")
    else:
        status = "GYM_TESTING" if st.session_state.active_engine == engine_test else "RAILWAY"
        st.success(f"👋 Welcome, **{st.session_state.username}**!")
        st.info(f"📍 Connected to: **{status}**")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.active_engine = engine_prod
            st.rerun()

# ---------------------------
# MAIN APP
# ---------------------------

if st.session_state.user_id is not None:
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🏠 Home", "💪 Log", "🥗 Food", "📖 Library", "⚖️ Weight", "📊 Progress", "🏆 PRs", "❓ Help"
    ])
    
    with tab1:
        st.title("🏠 Dashboard")
        col1, col2, col3 = st.columns(3)
        try:
            active = get_active_session(st.session_state.user_id)
            with col1: st.metric("Session", f"#{active[0]}" if active else "None")
            history = get_history(st.session_state.user_id, 1)
            with col2: st.metric("Last", history[0][1].strftime("%b %d") if history else "N/A")
            weight_hist = get_weight_history(st.session_state.user_id)
            with col3: st.metric("Weight", f"{weight_hist[0][1]} kg" if weight_hist else "N/A")
        except: pass

        st.markdown("---")
        st.subheader("🎯 Session Control")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶️ Start Session"):
                if not active:
                    start_session(st.session_state.user_id, st.session_state.username)
                    st.rerun()
        with c2:
            if active and st.button("⏹️ End Session"):
                st.session_state.show_end_form = True

        if getattr(st.session_state, 'show_end_form', False):
            with st.form("end_f"):
                cals = st.number_input("Calories", 0)
                if st.form_submit_button("Confirm"):
                    end_session(active[0], cals)
                    st.session_state.show_end_form = False
                    st.rerun()

    with tab2:
        st.title("💪 Log Workout")
        active = get_active_session(st.session_state.user_id)
        if active:
            w_type = st.radio("Type", ["Lift", "Cardio"], horizontal=True)
            if w_type == "Lift":
                m = st.selectbox("Muscle", list(MUSCLE_GROUPS.keys()))
                ex = st.selectbox("Exercise", MUSCLE_GROUPS[m])
                c1, c2, c3 = st.columns(3)
                sets, reps, lbs = c1.number_input("S", 1), c2.number_input("R", 1), c3.number_input("kg", 0)
                if st.button("Log Lift"):
                    add_weightlift_db(active[0], st.session_state.user_id, st.session_state.username, ex, m.split()[1], sets, reps, lbs, "")
                    st.success("Lift Recorded")
            else:
                machine = st.selectbox("Activity", CARDIO_MACHINES)
                duration = st.number_input("Duration (min)", 1)
                if st.button("Log Cardio"):
                    insert_cardio_db(active[0], st.session_state.user_id, st.session_state.username, machine.split()[1], duration, None, None, None)
                    st.success("Cardio Recorded")
        else: st.warning("Start session first")

    with tab3:
        st.title("🥗 Food Intake")
        with st.form("food_form"):
            f_date = st.date_input("Select Date", value=date.today())
            f_meal = st.text_input("Meal Name")
            c1, c2, c3 = st.columns(3)
            p, c, f = c1.number_input("Proteins"), c2.number_input("Carbs"), c3.number_input("Fats")
            if st.form_submit_button("✅ Log Meal") and f_meal:
                log_food_intake_db(st.session_state.user_id, f_date, f_meal, p, c, f)
                st.success("Meal logged!")

    with tab4:
        st.title("📖 Library")
        lib = st.selectbox("Browse", list(MUSCLE_GROUPS.keys()))
        for ex in MUSCLE_GROUPS[lib]: st.write(f"- {ex}")

    with tab5:
        st.title("⚖️ Weight")
        weight_input = st.number_input("Current Weight (kg)", 0.0)
        if st.button("Record Weight"):
            log_weight_db(st.session_state.user_id, weight_input)
            st.rerun()
        wh = get_weight_history(st.session_state.user_id)
        if wh:
            df_w = pd.DataFrame(wh, columns=["Date", "kg"]).sort_values("Date")
            st.plotly_chart(px.line(df_w, x="Date", y="kg"), config=PLOT_CONFIG)

    with tab6:
        st.title("📊 Progress")
        history = get_history(st.session_state.user_id, 20)
        if history:
            df_h = pd.DataFrame(history, columns=["ID", "Date", "Start", "End", "Calories"])
            st.plotly_chart(px.bar(df_h, x="Date", y="Calories"), config=PLOT_CONFIG)

    with tab7:
        st.title("🏆 PRs")
        prs = get_personal_records(st.session_state.user_id)
        if prs: st.dataframe(pd.DataFrame(prs, columns=["Exercise", "kg", "Date"]), hide_index=True)

    with tab8:
        st.title("❓ Help")
        st.write("Home: Sessions | Log: Workouts | Food: Nutrition | Library: Exercises")
else:
    st.title("🏋️ Welcome")
    st.info("Please login from the sidebar.")
