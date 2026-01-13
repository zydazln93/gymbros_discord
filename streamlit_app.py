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
from sqlalchemy import text

# Import all functions from your existing gymbros.py
try:
    from gymbros import (
        engine,
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
    """Authenticate user with username and password from user_credentials table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT discord_id, username 
                    FROM user_credentials 
                    WHERE username = :username AND password = :password
                """),
                {"username": username, "password": password}
            ).fetchone()
            return result  # Returns (discord_id, username) or None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

# ---------------------------
# HELPER FUNCTIONS FOR STREAMLIT
# ---------------------------

def get_history(discord_id: int, limit: int = 5):
    """Get workout history (Streamlit-specific helper)"""
    try:
        with engine.connect() as conn:
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
    """Test and wake up the database"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        st.error(f"⚠️ Database is waking up... Please refresh in 10 seconds.")
        return False

# Point 3: Function to log food intake
def log_food_intake_db(discord_id, entry_date, meal_name, protein, carbs, fats):
    """Inserts food data into food_intake table"""
    try:
        calories = (protein * 4) + (carbs * 4) + (fats * 9)
        with engine.connect() as conn:
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
    "💪 Chest": [
        "Bench Press", "Incline Bench Press", "Decline Bench Press",
        "Dumbbell Flyes", "Cable Flyes", "Push-Ups", "Chest Press Machine",
        "Pec Deck"
    ],
    "🦾 Back": [
        "Pull-Ups", "Lat Pulldown", "Barbell Row", "Dumbbell Row",
        "T-Bar Row", "Cable Row", "Deadlift", "Face Pulls"
    ],
    "🏋️ Shoulders": [
        "Overhead Press", "Dumbbell Shoulder Press", "Lateral Raises",
        "Front Raises", "Rear Delt Flyes", "Arnold Press", "Upright Row",
        "Shrugs"
    ],
    "💪 Biceps": [
        "Barbell Curl", "Dumbbell Curl", "Hammer Curl", "Preacher Curl",
        "Cable Curl", "Concentration Curl", "21s"
    ],
    "🔥 Triceps": [
        "Tricep Dips", "Skull Crushers", "Overhead Tricep Extension",
        "Cable Pushdown", "Close Grip Bench Press", "Diamond Push-Ups"
    ],
    "🦵 Legs": [
        "Squat", "Leg Press", "Leg Extension", "Leg Curl",
        "Lunges", "Romanian Deadlift", "Calf Raises", "Bulgarian Split Squat"
    ],
    "🎯 Core": [
        "Plank", "Crunches", "Leg Raises", "Russian Twists",
        "Cable Crunches", "Ab Wheel", "Hanging Knee Raises"
    ]
}

CARDIO_MACHINES = [
    "🏃 Treadmill", "🚴 Stationary Bike", "🚣 Rowing Machine",
    "🎿 Elliptical", "🪜 Stair Climber", "🏊 Swimming",
    "🥊 Boxing", "🎾 Sports"
]

# ---------------------------
# MOBILE-RESPONSIVE CSS
# ---------------------------

# Point 1 Fix: CSS to remove "Press Enter to submit form"
st.markdown("""
<style>
    /* Hides the 'Press Enter to submit form' text that covers characters */
    div[data-testid="stForm"] p {
        display: none !important;
    }
    
    /* Mobile-first responsive design */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Button styling - works on all screen sizes */
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%);
        color: white;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        padding: 12px 20px;
        transition: 0.3s;
        font-size: 16px;
    }
    
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    
    /* Metric cards - responsive sizing */
    div[data-testid="stMetricValue"] {
        font-size: clamp(20px, 4vw, 28px);
        font-weight: bold;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: clamp(12px, 2.5vw, 14px);
    }
    
    /* Success box - mobile friendly */
    .success-box {
        padding: 15px;
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
        margin: 10px 0;
    }
    
    .success-box h3 {
        font-size: clamp(16px, 4vw, 20px);
        margin-bottom: 10px;
    }
    
    .success-box p {
        font-size: clamp(14px, 3vw, 16px);
        margin: 5px 0;
    }
    
    /* Input fields - better mobile experience */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>select {
        font-size: 16px !important;  /* Prevents iOS zoom on focus */
        padding: 10px;
    }
    
    /* Tabs - mobile friendly */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
        overflow-x: auto;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-size: clamp(12px, 3vw, 14px);
        padding: 8px 12px;
        white-space: nowrap;
    }
    
    /* Data tables - horizontal scroll on mobile */
    .stDataFrame {
        overflow-x: auto;
    }
    
    /* Form spacing on mobile */
    .stForm {
        padding: 10px;
    }
    
    /* Sidebar adjustments */
    [data-testid="stSidebar"] {
        min-width: 250px;
    }
    
    /* Mobile-specific adjustments */
    @media (max-width: 768px) {
        .stButton>button {
            padding: 15px 10px;
            font-size: 14px;
        }
        
        h1 {
            font-size: 24px !important;
        }
        
        h2 {
            font-size: 20px !important;
        }
        
        h3 {
            font-size: 18px !important;
        }
        
        /* Stack columns vertically on mobile */
        [data-testid="column"] {
            width: 100% !important;
            flex: 100% !important;
        }
        
        /* Better spacing on mobile */
        .element-container {
            margin-bottom: 10px;
        }
    }
    
    /* Very small phones */
    @media (max-width: 480px) {
        .stButton>button {
            font-size: 13px;
            padding: 12px 8px;
        }
        
        div[data-testid="stMetricValue"] {
            font-size: 18px;
        }
    }
</style>
""", unsafe_allow_html=True)

# Point 4: Chart config to disable zoom features
PLOT_CONFIG = {'scrollZoom': False, 'displayModeBar': False, 'staticPlot': False}

# ---------------------------
# SESSION STATE INITIALIZATION
# ---------------------------

# Point 1: Keeping state active keeps user logged in while browser is open
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None

# ---------------------------
# SIDEBAR - USER LOGIN
# ---------------------------

# Test database connection first
if not test_db_connection():
    st.warning("🔄 Waking up database... Please wait and refresh.")
    st.stop()

with st.sidebar:
    st.title("🏋️ Fitness Tracker")
    st.markdown("---")
    
    if st.session_state.user_id is None:
        st.subheader("👤 Login")
        
        with st.form("login_form"):
            username_input = st.text_input("Username", placeholder="Enter your username")
            password_input = st.text_input("Password", type="password", placeholder="Enter your password")
            login_button = st.form_submit_button("🔐 Login", use_container_width=True)
            
            if login_button:
                if username_input and password_input:
                    user = authenticate_user(username_input, password_input)
                    if user:
                        st.session_state.user_id = user[0]  # discord_id
                        st.session_state.username = user[1]  # username
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password!")
                else:
                    st.error("⚠️ Please fill in both fields!")
    else:
        st.success(f"👋 Welcome, **{st.session_state.username}**!")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()
        
        st.markdown("---")
        st.subheader("📊 Quick Stats")
        
        try:
            active = get_active_session(st.session_state.user_id)
            if active:
                st.info(f"🟢 Active Session: #{active[0]}")
            else:
                st.warning("⚪ No active session")
        except:
            pass

# ---------------------------
# MAIN APP (Only if logged in)
# ---------------------------

if st.session_state.user_id is None:
    st.title("🏋️ Welcome to Fitness Tracker")
    st.markdown("""
    ### Please login from the sidebar to continue
    
    This app helps you:
    - 📝 Track gym sessions
    - 💪 Log weightlifting exercises
    - 🏃 Record cardio workouts
    - ⚖️ Monitor body weight
    - 📊 View progress and personal records
    """)
else:
    # Point 2, 3, 5: Added Library, Food, and Help tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🏠 Home", "💪 Log", "🥗 Food", "📖 Library", "⚖️ Weight", 
        "📊 Progress", "🏆 PRs", "❓ Help"
    ])
    
    # ---------------------------
    # TAB 1: DASHBOARD
    # ---------------------------
    with tab1:
        st.title("🏠 Dashboard")
        
        # Metrics in responsive columns
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            try:
                active = get_active_session(st.session_state.user_id)
                if active:
                    st.metric("Session", f"#{active[0]}", "🟢")
                else:
                    st.metric("Session", "None", "⚪")
            except:
                st.metric("Session", "Error", "❌")
        
        with col2:
            try:
                history = get_history(st.session_state.user_id, 1)
                if history:
                    st.metric("Last", history[0][1].strftime("%b %d"), f"{history[0][4] or 0} cal")
                else:
                    st.metric("Last", "N/A", "")
            except:
                st.metric("Last", "Error", "")
        
        with col3:
            try:
                weight_hist = get_weight_history(st.session_state.user_id)
                if weight_hist:
                    st.metric("Weight", f"{weight_hist[0][1]} kg", "")
                else:
                    st.metric("Weight", "N/A", "")
            except:
                st.metric("Weight", "Error", "")
        
        st.markdown("---")
        
        # Session Control - stacked on mobile
        st.subheader("🎯 Session Control")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("▶️ Start Session", use_container_width=True, key="start_btn"):
                try:
                    active = get_active_session(st.session_state.user_id)
                    if active:
                        st.error(f"⚠️ Active session: #{active[0]}")
                    else:
                        session_id = start_session(st.session_state.user_id, st.session_state.username)
                        st.success(f"✅ Session #{session_id} started!")
                        st.rerun()
                except DatabaseError as e:
                    st.error(f"❌ {e}")
        
        with col2:
            try:
                active = get_active_session(st.session_state.user_id)
                if active:
                    if st.button("⏹️ End Session", use_container_width=True, key="end_btn"):
                        st.session_state.show_end_form = True
                else:
                    st.button("⏹️ End Session", use_container_width=True, disabled=True, key="end_btn_disabled")
            except:
                pass
        
        # End session form (appears below buttons)
        if hasattr(st.session_state, 'show_end_form') and st.session_state.show_end_form:
            try:
                active = get_active_session(st.session_state.user_id)
                if active:
                    with st.form("end_session_form"):
                        st.write(f"Ending Session #{active[0]}")
                        calories = st.number_input("Calories Burned 🔥", min_value=0, value=0)
                        col_a, col_b = st.columns(2)
                        with col_a:
                            submitted = st.form_submit_button("✅ Confirm", use_container_width=True)
                        with col_b:
                            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
                        
                        if submitted:
                            end_session(active[0], calories)
                            st.success(f"✅ Session #{active[0]} ended! Total: {calories} cal")
                            st.session_state.show_end_form = False
                            st.rerun()
                        if cancelled:
                            st.session_state.show_end_form = False
                            st.rerun()
            except DatabaseError as e:
                st.error(f"❌ {e}")
        
        st.markdown("---")
        
        # Recent History
        st.subheader("📜 Recent Workouts")
        try:
            history = get_history(st.session_state.user_id, 5)
            if history:
                df = pd.DataFrame(history, columns=["ID", "Date", "Start", "End", "Calories"])
                df['Dur(m)'] = df.apply(lambda row: 
                    ((datetime.combine(date.today(), (datetime.min + row['End']).time()) - 
                      datetime.combine(date.today(), (datetime.min + row['Start']).time())).seconds // 60) 
                    if row['End'] else 0, axis=1)
                df_display = df[['ID', 'Date', 'Dur(m)', 'Calories']]
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.info("No completed sessions yet!")
        except Exception as e:
            st.error(f"Error: {e}")
    
    # ---------------------------
    # TAB 2: LOG WORKOUT
    # ---------------------------
    with tab2:
        st.title("💪 Log Workout")
        
        # Check for active session
        try:
            active = get_active_session(st.session_state.user_id)
            if not active:
                st.warning("⚠️ Start a session first!")
            else:
                st.success(f"✅ Session #{active[0]}")
                
                workout_type = st.radio("Type:", ["🏋️ Lift", "🏃 Cardio"], horizontal=True)
                
                st.markdown("---")
                
                if workout_type == "🏋️ Lift":
                    st.subheader("💪 Log Lift")
                    
                    muscle_group = st.selectbox("Muscle Group:", list(MUSCLE_GROUPS.keys()))
                    clean_muscle = muscle_group.split(" ", 1)[1]
                    exercise = st.selectbox("Exercise:", MUSCLE_GROUPS[muscle_group])
                    
                    col3, col4, col5 = st.columns(3)
                    
                    with col3:
                        sets = st.number_input("Sets", min_value=1, value=3)
                    with col4:
                        reps = st.number_input("Reps", min_value=1, value=10)
                    with col5:
                        weight = st.number_input("Weight (kg)", min_value=0, value=20)
                    
                    notes = st.text_area("Notes (optional)", max_chars=200)
                    
                    if st.button("✅ Log Lift", use_container_width=True):
                        try:
                            lift_id = add_weightlift_db(
                                active[0], st.session_state.user_id, st.session_state.username,
                                exercise, clean_muscle, sets, reps, weight, notes
                            )
                            st.markdown(f"""
                            <div class="success-box">
                                <h3>✅ Lift Logged!</h3>
                                <p><strong>{exercise}</strong></p>
                                <p>{sets}×{reps} @ {weight}kg</p>
                            </div>
                            """, unsafe_allow_html=True)
                        except DatabaseError as e:
                            st.error(f"❌ {e}")
                
                else:  # Cardio
                    st.subheader("🏃 Log Cardio")
                    
                    machine = st.selectbox("Activity:", CARDIO_MACHINES)
                    duration = st.number_input("Duration (min)", min_value=1, value=30)
                    
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        distance = st.number_input("Distance (km)", min_value=0.0, value=0.0, step=0.1)
                    
                    with col4:
                        calories = st.number_input("Calories", min_value=0, value=0)
                    
                    notes = st.text_area("Notes (optional)", max_chars=200)
                    
                    if st.button("✅ Log Cardio", use_container_width=True):
                        try:
                            clean_machine = machine.split(" ", 1)[1]
                            cardio_id = insert_cardio_db(
                                active[0], st.session_state.user_id, st.session_state.username,
                                clean_machine, duration, 
                                distance if distance > 0 else None,
                                calories if calories > 0 else None,
                                notes if notes else None
                            )
                            st.markdown(f"""
                            <div class="success-box">
                                <h3>✅ Cardio Logged!</h3>
                                <p><strong>{clean_machine}</strong></p>
                                <p>{duration} min • {calories} cal</p>
                            </div>
                            """, unsafe_allow_html=True)
                        except DatabaseError as e:
                            st.error(f"❌ {e}")
        
        except DatabaseError as e:
            st.error(f"❌ {e}")

    # ---------------------------
    # TAB 3: FOOD INTAKE
    # ---------------------------
    with tab3:
        st.title("🥗 Food Intake")
        with st.form("food_form"):
            # Point 3: Calendar format date input
            f_date = st.date_input("Select Date", value=date.today())
            f_meal = st.text_input("Meal Name")
            c1, c2, c3 = st.columns(3)
            with c1: f_prot = st.number_input("Proteins (g)", 0.0)
            with c2: f_carb = st.number_input("Carbs (g)", 0.0)
            with c3: f_fats = st.number_input("Fats (g)", 0.0)
            
            if st.form_submit_button("✅ Log Meal"):
                if f_meal:
                    log_food_intake_db(st.session_state.user_id, f_date, f_meal, f_prot, f_carb, f_fats)
                    st.success("Meal logged!")
                else:
                    st.error("Please enter a meal name.")

    # ---------------------------
    # TAB 4: MUSCLE GROUP LIBRARY
    # ---------------------------
    with tab4:
        st.title("📖 Exercise Library")
        # Point 2: Dropdown for muscle groups that runs even without sessions
        lib_muscle = st.selectbox("Browse Muscle Groups", list(MUSCLE_GROUPS.keys()))
        st.write(f"### Recommended Exercises for {lib_muscle}:")
        for ex in MUSCLE_GROUPS[lib_muscle]:
            st.write(f"- {ex}")

    # ---------------------------
    # TAB 5: WEIGHT TRACKER
    # ---------------------------
    with tab5:
        st.title("⚖️ Weight")
        
        st.subheader("Log Weight")
        weight_input = st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.1)
        
        if st.button("✅ Log Weight", use_container_width=True):
            try:
                log_id = log_weight_db(st.session_state.user_id, weight_input)
                st.success(f"✅ {weight_input} kg logged!")
                st.rerun()
            except DatabaseError as e:
                st.error(f"❌ {e}")
        
        st.markdown("---")
        st.subheader("📈 Progress")
        
        try:
            weight_hist = get_weight_history(st.session_state.user_id)
            if weight_hist:
                df = pd.DataFrame(weight_hist, columns=["Date", "Weight (kg)"])
                df = df.sort_values("Date")
                
                fig = px.line(df, x="Date", y="Weight (kg)", 
                              markers=True, 
                              title="Weight Trend")
                fig.update_traces(line_color='#00C9FF', marker=dict(size=8))
                fig.update_layout(height=400)
                # Point 4: Chart with autoscale and no zoom
                st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)
            else:
                st.info("No weight logs yet!")
        except Exception as e:
            st.error(f"Error: {e}")
    
    # ---------------------------
    # TAB 6: PROGRESS
    # ---------------------------
    with tab6:
        st.title("📊 Progress")
        
        try:
            sessions = get_history(st.session_state.user_id, 20)
            if sessions:
                df = pd.DataFrame(sessions, columns=["ID", "Date", "Start", "End", "Calories"])
                df['Date'] = pd.to_datetime(df['Date'])
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df['Date'],
                    y=df['Calories'],
                    marker_color='#92FE9D',
                    name='Calories'
                ))
                fig.update_layout(
                    title="Calories Per Session",
                    xaxis_title="Date",
                    yaxis_title="Calories",
                    template="plotly_dark",
                    height=400
                )
                # Point 4: Chart with autoscale and no zoom
                st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)
            else:
                st.info("No workout data yet!")
        except Exception as e:
            st.error(f"Error: {e}")
    
    # ---------------------------
    # TAB 7: PERSONAL RECORDS
    # ---------------------------
    with tab7:
        st.title("🏆 PRs")
        
        try:
            prs = get_personal_records(st.session_state.user_id)
            if prs:
                df = pd.DataFrame(prs, columns=["Exercise", "Max (kg)", "Date"])
                
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # Top 5 PRs chart
                top_5 = df.head(5)
                fig = px.bar(top_5, x="Exercise", y="Max (kg)",
                             color="Max (kg)",
                             color_continuous_scale="Viridis",
                             title="Top 5 PRs")
                fig.update_layout(height=400)
                # Point 4: Chart with autoscale and no zoom
                st.plotly_chart(fig, use_container_width=True, config=PLOT_CONFIG)
            else:
                st.info("🏅 No PRs yet!")
        except DatabaseError as e:
            st.error(f"❌ {e}")

    # ---------------------------
    # TAB 8: HELP
    # ---------------------------
    with tab8:
        st.title("❓ Help & Navigation")
        st.markdown("""
        ### Welcome to your Fitness Tracker!
        Here is how to navigate the site:
        
        1. **🏠 Home**: Start and End your gym sessions here. You can also see your last workout stats.
        2. **💪 Log**: Once a session is started, come here to record your lifting or cardio.
        3. **🥗 Food**: Log your daily meals and macros. Use the calendar to select the date.
        4. **📖 Library**: Check exercise recommendations for different muscle groups anytime.
        5. **⚖️ Weight**: Track your body weight over time.
        6. **📊 Progress**: View charts of your calorie burn and consistency.
        7. **🏆 PRs**: See your all-time best lifts.
        """)
