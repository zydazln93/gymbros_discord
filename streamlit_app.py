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
# HELPER FUNCTIONS FOR STREAMLIT
# ---------------------------

def get_history(discord_id: int, limit: int = 5):
    """Get workout history (Streamlit-specific helper)"""
    try:
        from sqlalchemy import text
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
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        st.error(f"⚠️ Database is waking up... Please refresh in 10 seconds.")
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
# CUSTOM CSS
# ---------------------------

st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%);
        color: white;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        padding: 10px;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: bold;
    }
    .success-box {
        padding: 20px;
        border-radius: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# SESSION STATE INITIALIZATION
# ---------------------------

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
        user_id_input = st.text_input("User ID (Discord ID)")
        username_input = st.text_input("Username")
        
        if st.button("Login"):
            if user_id_input and username_input:
                try:
                    st.session_state.user_id = int(user_id_input)
                    st.session_state.username = username_input
                    st.rerun()
                except ValueError:
                    st.error("User ID must be a number!")
            else:
                st.error("Please fill in both fields!")
    else:
        st.success(f"👋 Welcome, **{st.session_state.username}**!")
        if st.button("Logout"):
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
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠 Dashboard", "💪 Log Workout", "⚖️ Weight Tracker", 
        "📊 Progress", "🏆 Personal Records"
    ])
    
    # ---------------------------
    # TAB 1: DASHBOARD
    # ---------------------------
    with tab1:
        st.title("🏠 Dashboard")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            try:
                active = get_active_session(st.session_state.user_id)
                if active:
                    st.metric("Active Session", f"#{active[0]}", "🟢 In Progress")
                else:
                    st.metric("Active Session", "None", "⚪ Idle")
            except:
                st.metric("Active Session", "Error", "❌")
        
        with col2:
            try:
                history = get_history(st.session_state.user_id, 1)
                if history:
                    st.metric("Last Workout", history[0][1].strftime("%b %d"), f"{history[0][4] or 0} cal")
                else:
                    st.metric("Last Workout", "N/A", "")
            except:
                st.metric("Last Workout", "Error", "")
        
        with col3:
            try:
                weight_hist = get_weight_history(st.session_state.user_id)
                if weight_hist:
                    st.metric("Current Weight", f"{weight_hist[0][1]} kg", "")
                else:
                    st.metric("Current Weight", "N/A", "")
            except:
                st.metric("Current Weight", "Error", "")
        
        st.markdown("---")
        
        # Session Control
        st.subheader("🎯 Session Control")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("▶️ Start New Session", use_container_width=True):
                try:
                    active = get_active_session(st.session_state.user_id)
                    if active:
                        st.error(f"⚠️ You already have an active session (ID: {active[0]})")
                    else:
                        session_id = start_session(st.session_state.user_id, st.session_state.username)
                        st.success(f"✅ Session #{session_id} started!")
                        st.rerun()
                except DatabaseError as e:
                    st.error(f"❌ {e}")
        
        with col2:
            if st.button("⏹️ End Active Session", use_container_width=True):
                try:
                    active = get_active_session(st.session_state.user_id)
                    if not active:
                        st.error("❌ No active session found")
                    else:
                        with st.form("end_session_form"):
                            calories = st.number_input("Total Calories Burned 🔥", min_value=0, value=0)
                            submitted = st.form_submit_button("Confirm End Session")
                            if submitted:
                                end_session(active[0], calories)
                                st.success(f"✅ Session #{active[0]} ended! Total: {calories} cal")
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
                df['Duration (min)'] = df.apply(lambda row: 
                    ((datetime.combine(date.today(), (datetime.min + row['End']).time()) - 
                      datetime.combine(date.today(), (datetime.min + row['Start']).time())).seconds // 60) 
                    if row['End'] else 0, axis=1)
                df_display = df[['ID', 'Date', 'Duration (min)', 'Calories']]
                st.dataframe(df_display, use_container_width=True)
            else:
                st.info("No completed sessions yet!")
        except Exception as e:
            st.error(f"Error loading history: {e}")
    
    # ---------------------------
    # TAB 2: LOG WORKOUT
    # ---------------------------
    with tab2:
        st.title("💪 Log Workout")
        
        # Check for active session
        try:
            active = get_active_session(st.session_state.user_id)
            if not active:
                st.warning("⚠️ Please start a session first from the Dashboard!")
            else:
                st.success(f"✅ Logging to Session #{active[0]}")
                
                workout_type = st.radio("Choose workout type:", ["🏋️ Weightlifting", "🏃 Cardio"], horizontal=True)
                
                st.markdown("---")
                
                if workout_type == "🏋️ Weightlifting":
                    st.subheader("💪 Log Weightlifting Exercise")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        muscle_group = st.selectbox("Choose Muscle Group:", list(MUSCLE_GROUPS.keys()))
                    
                    with col2:
                        # Remove emoji from muscle group key for cleaner display
                        clean_muscle = muscle_group.split(" ", 1)[1]
                        exercise = st.selectbox("Choose Exercise:", MUSCLE_GROUPS[muscle_group])
                    
                    col3, col4, col5 = st.columns(3)
                    
                    with col3:
                        sets = st.number_input("Sets", min_value=1, value=3)
                    with col4:
                        reps = st.number_input("Reps", min_value=1, value=10)
                    with col5:
                        weight = st.number_input("Weight (kg)", min_value=0, value=20)
                    
                    notes = st.text_area("Notes (optional)")
                    
                    if st.button("✅ Log Lift", use_container_width=True):
                        try:
                            lift_id = add_weightlift_db(
                                active[0], st.session_state.user_id, st.session_state.username,
                                exercise, clean_muscle, sets, reps, weight, notes
                            )
                            st.markdown(f"""
                            <div class="success-box">
                                <h3>✅ Lift Logged Successfully!</h3>
                                <p><strong>{exercise}</strong> - {sets}×{reps} @ {weight}kg</p>
                                <p>Log ID: #{lift_id}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        except DatabaseError as e:
                            st.error(f"❌ {e}")
                
                else:  # Cardio
                    st.subheader("🏃 Log Cardio Exercise")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        machine = st.selectbox("Choose Machine/Activity:", CARDIO_MACHINES)
                    
                    with col2:
                        duration = st.number_input("Duration (minutes)", min_value=1, value=30)
                    
                    col3, col4 = st.columns(2)
                    
                    with col3:
                        distance = st.number_input("Distance (km) - Optional", min_value=0.0, value=0.0, step=0.1)
                    
                    with col4:
                        calories = st.number_input("Calories Burned - Optional", min_value=0, value=0)
                    
                    notes = st.text_area("Notes (optional)")
                    
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
                                <h3>✅ Cardio Logged Successfully!</h3>
                                <p><strong>{clean_machine}</strong> - {duration} min</p>
                                <p>🔥 {calories} calories burned</p>
                            </div>
                            """, unsafe_allow_html=True)
                        except DatabaseError as e:
                            st.error(f"❌ {e}")
        
        except DatabaseError as e:
            st.error(f"❌ {e}")
    
    # ---------------------------
    # TAB 3: WEIGHT TRACKER
    # ---------------------------
    with tab3:
        st.title("⚖️ Weight Tracker")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Log New Weight")
            weight_input = st.number_input("Weight (kg)", min_value=0.0, value=70.0, step=0.1)
            
            if st.button("✅ Log Weight", use_container_width=True):
                try:
                    log_id = log_weight_db(st.session_state.user_id, weight_input)
                    st.success(f"✅ Weight logged: {weight_input} kg")
                    st.rerun()
                except DatabaseError as e:
                    st.error(f"❌ {e}")
        
        with col2:
            st.subheader("📈 Weight Progress Chart")
            try:
                weight_hist = get_weight_history(st.session_state.user_id)
                if weight_hist:
                    df = pd.DataFrame(weight_hist, columns=["Date", "Weight (kg)"])
                    df = df.sort_values("Date")
                    
                    fig = px.line(df, x="Date", y="Weight (kg)", 
                                  markers=True, 
                                  title="Weight Trend Over Time")
                    fig.update_traces(line_color='#00C9FF', marker=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No weight logs yet!")
            except Exception as e:
                st.error(f"Error loading weight history: {e}")
    
    # ---------------------------
    # TAB 4: PROGRESS
    # ---------------------------
    with tab4:
        st.title("📊 Workout Progress")
        
        try:
            sessions = get_history(st.session_state.user_id, 20)
            if sessions:
                df = pd.DataFrame(sessions, columns=["ID", "Date", "Start", "End", "Calories"])
                df['Date'] = pd.to_datetime(df['Date'])
                
                # Calories chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df['Date'],
                    y=df['Calories'],
                    marker_color='#92FE9D',
                    name='Calories'
                ))
                fig.update_layout(
                    title="Calories Burned Per Session",
                    xaxis_title="Date",
                    yaxis_title="Calories",
                    template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No workout data yet!")
        except Exception as e:
            st.error(f"Error loading progress: {e}")
    
    # ---------------------------
    # TAB 5: PERSONAL RECORDS
    # ---------------------------
    with tab5:
        st.title("🏆 Personal Records")
        
        try:
            prs = get_personal_records(st.session_state.user_id)
            if prs:
                df = pd.DataFrame(prs, columns=["Exercise", "Max Weight (kg)", "Date"])
                
                # Display in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.dataframe(df, use_container_width=True)
                
                with col2:
                    # Top 5 PRs chart
                    top_5 = df.head(5)
                    fig = px.bar(top_5, x="Exercise", y="Max Weight (kg)",
                                 color="Max Weight (kg)",
                                 color_continuous_scale="Viridis",
                                 title="Top 5 Personal Records")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("🏅 No personal records yet! Start logging workouts to see your PRs!")
        except DatabaseError as e:
            st.error(f"❌ {e}")