import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, exc as sa_exc
from datetime import datetime, date, timedelta
from typing import List, Any, Optional

# ---------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------
load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DISCORD_TOKEN"]
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    # This check is vital for deployment on Railway!
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# ---------------------------
# CREATE DATABASE ENGINE
# ---------------------------
# Note: On Railway, you must use the internal database variables defined in the service settings
DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}{f':{DB_PORT}' if DB_PORT else ''}/{DB_NAME}"

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

# ---------------------------
# DISCORD BOT SETUP
# ---------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------
# DATABASE HELPER FUNCTIONS 
# ---------------------------

def start_session(user_id: int, user_name: str):
    # ... (existing start_session logic)
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO gym_sessions (date, start_time, notes)
                VALUES (:session_date, :start_time, :notes)
            """),
            {
                "session_date": date.today(),
                "start_time": datetime.now().strftime("%H:%M:%S"),
                "notes": f"Started by {user_name} (ID: {user_id})"
            }
        )
        return result.lastrowid

def get_active_session():
    # ... (existing get_active_session logic)
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT session_id, date, start_time, notes
                FROM gym_sessions
                WHERE end_time IS NULL
                ORDER BY session_id DESC
                LIMIT 1;
            """)
        ).fetchone()
        return result

def end_session(session_id: int, calories: int):
    # ... (existing end_session logic)
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE gym_sessions
                SET end_time = :end_time,
                    total_calories = :calories
                WHERE session_id = :session_id
            """),
            {
                "end_time": datetime.now().strftime("%H:%M:%S"),
                "calories": calories,
                "session_id": session_id
            }
        )

def insert_cardio_db(session_id: int, machine_type: str, duration: int, 
                     distance: float = None, calories: int = None, notes: str = None):
    # ... (existing insert_cardio_db logic)
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO cardio_logs 
                (session_id, date, machine_type, duration_minutes, distance, calories_burned, notes)
                VALUES (:session_id, :date, :machine_type, :duration, :distance, :calories, :notes)
            """),
            {
                "session_id": session_id,
                "date": date.today(),
                "machine_type": machine_type,
                "duration": duration,
                "distance": distance,
                "calories": calories,
                "notes": notes
            }
        )
        return result.lastrowid

def add_weightlift_db(session_id: int, exercise_name: str, muscle_group: str,
                      sets: int, reps: int, weight: int, notes: str = None):
    # ... (existing add_weightlift_db logic)
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO weightlift_logs
                (session_id, date, exercise_name, muscle_group, sets, reps, weight, notes)
                VALUES (:session_id, :date, :exercise, :muscle, :sets, :reps, :weight, :notes)
            """),
            {
                "session_id": session_id,
                "date": date.today(),
                "exercise": exercise_name,
                "muscle": muscle_group,
                "sets": sets,
                "reps": reps,
                "weight": weight,
                "notes": notes
            }
        )
        return result.lastrowid

def get_session_details(session_id: int):
    # ... (existing get_session_details logic)
    with engine.begin() as conn:
        session = conn.execute(
            text("""
                SELECT session_id, date, start_time, end_time, total_calories, notes
                FROM gym_sessions
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        ).fetchone()
        if not session:
            return None

        cardio = conn.execute(
            text("""
                SELECT machine_type, duration_minutes, distance, calories_burned, notes
                FROM cardio_logs
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        ).fetchall()

        lifts = conn.execute(
            text("""
                SELECT exercise_name, muscle_group, sets, reps, weight, notes
                FROM weightlift_logs
                WHERE session_id = :session_id
            """),
            {"session_id": session_id}
        ).fetchall()

        return {
            "session": session,
            "cardio": cardio,
            "lifts": lifts
        }

def get_personal_records():
    # ... (existing get_personal_records logic)
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT 
                    exercise_name,
                    MAX(weight) AS max_weight,
                    (
                        SELECT date 
                        FROM weightlift_logs 
                        WHERE exercise_name = w.exercise_name AND weight = MAX(w.weight)
                        ORDER BY date DESC 
                        LIMIT 1
                    ) AS pr_date
                FROM weightlift_logs w
                GROUP BY exercise_name
                ORDER BY max_weight DESC
            """)
        ).fetchall()
        return result

# --- Weight Tracking Helpers (FIXED to use weight_check table) ---

def log_weight_db(weight_kg: float) -> int:
    """Logs the user's body weight (in kg) into the weight_check table."""
    # FIX: Update table name and use only date_checked and weight_kg columns
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO weight_check (date_checked, weight_kg)
                VALUES (:date_checked, :weight_kg)
            """),
            {
                "date_checked": date.today(),
                # Assuming weight_kg is converted to INT for the DB column type
                "weight_kg": int(weight_kg)
            }
        )
        return result.lastrowid

def get_weight_history():
    """Retrieves the last 10 weight entries from the weight_check table."""
    # FIX: Update table name and select the correct columns
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT date_checked, weight_kg
                FROM weight_check
                ORDER BY date_checked DESC
                LIMIT 10
            """)
        ).fetchall()
        return result

# ---------------------------
# BOT EVENTS
# ---------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        # Check DB Connection only
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
            
    except sa_exc.OperationalError as e:
        print(f"✗ Database connection failed. Check DB credentials or host reachability. Error: {e}")
    except Exception as e:
        print(f"✗ An unexpected error occurred during setup: {e}")
    print("Bot is now running!")

@bot.event
async def on_command_error(ctx, error):
    # ... (existing on_command_error logic)
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Check `!command` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided! Ensure numbers are integers/floats and check `!command`.")
    else:
        print(f"Error: {error}")
        await ctx.send("❌ An unexpected error occurred while processing your command! Check console logs.")

# ---------------------------
# Aesthetic Table Helper (Unchanged)
# ---------------------------

def create_table(headers: List[str], rows: List[List[Any]]) -> str:
    # ... (existing create_table logic)
    processed_rows = []
    for row in rows:
        # Convert None/null values to a standard string representation
        processed_rows.append([str(cell) if cell is not None else "-" for cell in row])

    # Calculate column widths based on max content length
    col_widths = [len(h) for h in headers]
    for row in processed_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Create separator lines
    def make_line(left: str, mid: str, right: str, fill: str) -> str:
        return left + mid.join([fill * (w + 2) for w in col_widths]) + right

    top = make_line("┌", "┬", "┐", "─")
    middle = make_line("├", "┼", "┤", "─")
    bottom = make_line("└", "┴", "┘", "─")
    
    # Construct the table
    lines = [top]
    
    # Add Header
    header_row = "│"
    for i, h in enumerate(headers):
        header_row += f" {h:<{col_widths[i]}} │"
    lines.append(header_row)
    lines.append(middle)
    
    # Add Rows
    for row in processed_rows:
        line = "│"
        for i, cell in enumerate(row):
            line += f" {str(cell):<{col_widths[i]}} │"
        lines.append(line)
    
    lines.append(bottom)
    return "\n".join(lines)


# ---------------------------
# BOT COMMANDS / INSTRUCTIONS
# ---------------------------
@bot.command()
async def ping(ctx):
    """Test if bot is responsive"""
    await ctx.send("🏓 Pong!")

@bot.command()
async def command(ctx):
    """Display all available bot commands with examples (Updated)"""
    embed = discord.Embed(
        title="🤖 Fitness Tracker Bot - Command List",
        description="Here are all available commands:",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="📋 Session Management",
        value=(
            "```"
            "!session_start [notes]      Start a new gym session\n"
            "!session_end                End active session (asks for calories)\n"
            "!current                    View your active session\n"
            "!session <id>               View specific session details\n"
            "!today                      View all today's sessions"
            "```"
        ),
        inline=False
    )
    embed.add_field(
        name="💪 Exercise Logging",
        value=(
            "```"
            "!add_cardio <machine> <mins> [km] [cal] [notes]\n"
            "!add_lift <exercise> <muscle> <sets> <reps> <kg> [notes]"
            "```"
        ),
        inline=False
    )
    # Calorie Tracking commands REMOVED for now
    
    embed.add_field(
        name="⚖️ Weight Tracking",
        value=(
            "```"
            "!log_weight <weight_kg>      Log current body weight in KG\n"
            "!view_progress              View last 10 weight logs"
            "```"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Reporting",
        value=(
            "```"
            "!history                    View last 5 completed sessions\n"
            "!pr                         View all Personal Records"
            "```"
        ),
        inline=False
    )
    embed.add_field(
        name="💡 Tips",
        value=(
            "• Use quotes for multi-word values: `\"Bench Press\"`\n"
            "• Optional parameters are shown in [brackets]\n"
            "• The ID for `!session` is the **Session ID**"
        ),
        inline=False
    )
    embed.set_footer(text="💪 Track your gains! | Made for fitness enthusiasts")
    await ctx.send(embed=embed)

# -----------------------------------------
# Session and Logging commands (Unchanged)
# -----------------------------------------
@bot.command()
async def session_start(ctx, *, notes: str = None):
    active = get_active_session()
    if active:
        await ctx.reply(f"⚠️ You already have an active session (ID: **{active[0]}**). End it with `!session_end` first.")
        return
    session_id = start_session(ctx.author.id, str(ctx.author))
    await ctx.reply(f"✅ **Gym session started!**\n📋 Session ID: **{session_id}**\n📅 Date: {date.today()}\n⏰ Start time: {datetime.now().strftime('%H:%M')}\n💪 Let's crush this workout!")

@bot.command()
async def session_end(ctx):
    active = get_active_session()
    if not active:
        await ctx.reply("❌ You don't have any active session. Start one with `!session_start`")
        return
    
    session_id = active[0]
    start_val = active[2]
    
    start_time_obj = None
    if isinstance(start_val, timedelta):
        start_time_obj = (datetime.min + start_val).time()
    else:
        try:
            start_time_obj = datetime.strptime(str(start_val), "%H:%M:%S").time()
        except ValueError:
            await ctx.reply("❌ Error parsing start time. Cannot calculate duration.")
            return

    start_dt = datetime.combine(date.today(), start_time_obj)
    end_dt = datetime.now()
    
    if end_dt < start_dt:
        start_dt -= timedelta(days=1)
        
    duration = (end_dt - start_dt).seconds // 60

    await ctx.reply(f"📊 Session ID **{session_id}** found.\n⏱️ Duration: **{duration} minutes**\n\nHow many calories did you burn? 🔥\nReply with just the number (you have 60 seconds).")
    
    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.isdigit()
    
    try:
        msg = await bot.wait_for("message", check=check, timeout=60)
    except:
        await ctx.reply("⏳ Timeout! You took too long. Session is still active.")
        return
    
    calories = int(msg.content)
    end_session(session_id, calories)
    await ctx.reply(f"✅ **Session ended!**\n🔥 Total calories recorded: **{calories}**\n⏱️ Workout duration: **{duration} minutes**\n🏋️ Great job today! 💪")

@bot.command()
async def add_cardio(ctx, machine: str, duration: int, distance: float = None, calories: int = None, *, notes: str = None):
    active = get_active_session()
    if not active:
        await ctx.reply("❌ No active session found. Start one with `!session_start`")
        return
    
    session_id = active[0] 

    cardio_id = insert_cardio_db(session_id, machine, duration, distance, calories, notes)

    response = f"✅ **Cardio logged!** (ID: `{cardio_id}`)\n🏃 Machine: **{machine}**\n⏱️ Duration: **{duration} minutes**\n"
    if distance: response += f"📏 Distance: **{distance} km**\n"
    if calories: response += f"🔥 Calories: **{calories}**\n"
    await ctx.reply(response)

@bot.command()
async def add_lift(ctx, exercise: str, muscle: str, sets: int, reps: int, weight: int, *, notes: str = None):
    active = get_active_session()
    if not active:
        await ctx.reply("❌ No active session found. Start one with `!session_start`")
        return
    
    lift_id = add_weightlift_db(active[0], exercise, muscle, sets, reps, weight, notes)
    await ctx.reply(f"✅ **Lift logged!** (ID: `{lift_id}`)\n💪 Exercise: **{exercise}**\n🎯 Muscle: **{muscle}**\n📊 **{sets}**×**{reps}** @ **{weight}kg**")

@bot.command()
async def current(ctx):
    active = get_active_session()
    if not active:
        await ctx.reply("📅 No active session found.\nStart one with `!session_start`")
        return
    details = get_session_details(active[0])
    if not details:
        await ctx.reply("❌ Error retrieving session details.")
        return
    session = details["session"]
    embed = discord.Embed(title=f"🏋️ Current Session #{session[0]}", description="**Status:** 🟢 Active", color=discord.Color.green())
    embed.add_field(name="📅 Session Info", value=f"**Date:** {session[1]}\n**Start:** {session[2]}\n**End:** Ongoing", inline=False)
    
    if details["cardio"]:
        cardio_text = ""
        for log in details["cardio"]:
            cardio_text += f"• **{log[0]}** ({log[1]}min"
            if log[2]: cardio_text += f", {log[2]}km"
            if log[3]: cardio_text += f", {log[3]} cal"
            cardio_text += ")\n"
        embed.add_field(name="🏃 Cardio", value=cardio_text, inline=False)
    
    if details["lifts"]:
        lift_text = ""
        for log in details["lifts"]:
            lift_text += f"• **{log[0]}** ({log[1]}): {log[2]}×{log[3]} @ {log[4]}kg\n"
        embed.add_field(name="💪 Weightlifting", value=lift_text, inline=False)
    
    if not details["cardio"] and not details["lifts"]:
        embed.add_field(name="📝 Logs", value="No exercises logged yet. Use `!add_cardio` or `!add_lift`!", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def session(ctx, session_id: int):
    details = get_session_details(session_id)
    if not details:
        await ctx.reply(f"❌ Session ID `{session_id}` not found!")
        return
    session = details["session"]
    status = "🟢 Active" if session[3] is None else "✅ Completed"
    color = discord.Color.green() if session[3] is None else discord.Color.blue()
    embed = discord.Embed(title=f"🏋️ Gym Session #{session[0]}", description=f"**Status:** {status}", color=color)
    end_time = session[3] if session[3] else "Ongoing"
    calories = session[4] if session[4] else "Not recorded"
    embed.add_field(name="📅 Session Info", value=f"**Date:** {session[1]}\n**Start:** {session[2]}\n**End:** {end_time}\n**Calories:** {calories}", inline=False)

    if details["cardio"]:
        cardio_text = ""
        for log in details["cardio"]:
            cardio_text += f"• **{log[0]}** ({log[1]}min"
            if log[2]: cardio_text += f", {log[2]}km"
            if log[3]: cardio_text += f", {log[3]} cal"
            cardio_text += ")\n"
        embed.add_field(name="🏃 Cardio", value=cardio_text, inline=False)
    
    if details["lifts"]:
        lift_text = ""
        for log in details["lifts"]:
            lift_text += f"• **{log[0]}** ({log[1]}): {log[2]}×{log[3]} @ {log[4]}kg\n"
        embed.add_field(name="💪 Weightlifting", value=lift_text, inline=False)
    
    if session[5]: embed.add_field(name="📝 Notes", value=session[5], inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def today(ctx):
    with engine.begin() as conn:
        sessions = conn.execute(
            text("""
                SELECT session_id, start_time, end_time, total_calories
                FROM gym_sessions
                WHERE date = :today
                ORDER BY session_id DESC
            """), {"today": date.today()}
        ).fetchall()
    if not sessions:
        await ctx.reply(f"📅 No gym sessions found for today ({date.today()}).")
        return
    embed = discord.Embed(title=f"📅 Today's Workouts - {date.today()}", color=discord.Color.gold())
    for session in sessions:
        status = "🟢 Active" if session[2] is None else "✅ Completed"
        end_time = session[2] if session[2] else "Ongoing"
        calories = session[3] if session[3] else "Not recorded"
        embed.add_field(name=f"Session #{session[0]} - {status}", value=f"**Start:** {session[1]}\n**End:** {end_time}\n**Calories:** {calories}", inline=True)
    embed.set_footer(text=f"Use !session <id> to view details • Use !current for active session")
    await ctx.send(embed=embed)


# -----------------------------------------
# Aesthetic Table Commands (History & PR) (Unchanged)
# -----------------------------------------

@bot.command()
async def history(ctx):
    """Displays last 5 completed sessions in an aesthetic table"""
    with engine.begin() as conn:
        sessions = conn.execute(
            text("""
                SELECT session_id, date, start_time, end_time, total_calories
                FROM gym_sessions
                WHERE end_time IS NOT NULL
                ORDER BY session_id DESC
                LIMIT 5
            """)
        ).fetchall()

    if not sessions:
        await ctx.reply("📭 No completed sessions found.")
        return

    headers = ["ID", "Date", "Time", "Dur(m)", "Cals"]
    rows = []

    def safe_time_parse(time_value):
        if isinstance(time_value, timedelta):
            return (datetime.min + time_value).time()
        elif hasattr(time_value, 'hour'):
            return time_value
        else:
            return datetime.strptime(str(time_value), "%H:%M:%S").time()

    for s in sessions:
        s_id = s[0]
        s_date = s[1].strftime("%b %d")
        duration = "-"
        time_str = str(s[2])
        
        try:
            start_time_obj = safe_time_parse(s[2])
            end_time_obj = safe_time_parse(s[3])
            
            t_start = datetime.combine(date.today(), start_time_obj)
            t_end = datetime.combine(date.today(), end_time_obj)
            
            if t_end < t_start: t_end += timedelta(days=1)
            
            duration = (t_end - t_start).seconds // 60
            time_str = start_time_obj.strftime("%H:%M")
        except Exception:
            pass 
        
        cals = s[4] if s[4] else "-"
        
        rows.append([f"#{s_id}", s_date, time_str, duration, cals])
    
    table = create_table(headers, rows)
    
    embed = discord.Embed(title="📜 Workout History", color=discord.Color.dark_theme())
    embed.description = f"```text\n{table}\n```"
    await ctx.send(embed=embed)


@bot.command(name="pr")
async def personal_records(ctx):
    """Displays your all-time Personal Records (PRs)"""
    records = get_personal_records()
    
    if not records:
        await ctx.reply("🏅 No weightlifting logs found yet! Use `!add_lift` to start tracking PRs.")
        return

    headers = ["Exercise", "Max Weight (kg)", "Date Achieved"]
    rows = []
    
    for r in records:
        exercise_name = (r[0][:15] + '..') if len(r[0]) > 15 else r[0]
        max_weight = r[1]
        
        pr_date = r[2].strftime("%b %d, %Y") if r[2] else "-"
        
        rows.append([exercise_name, max_weight, pr_date])

    table = create_table(headers, rows)

    embed = discord.Embed(title="🏆 All-Time Personal Records (PRs)", color=discord.Color.gold())
    embed.description = f"These are your heaviest logged lifts:\n```text\n{table}\n```"
    embed.set_footer(text="Keep pushing for new PRs! 💪")
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------------------
# Weight Tracking Commands (Using weight_check table)
# ---------------------------------------------------------------------------------------

@bot.command(name="log_weight") 
async def log_weight(ctx, weight: float):
    """Logs your current body weight in kilograms."""
    
    try:
        weight_int = float(weight)
    except ValueError:
        await ctx.reply("❌ Invalid weight input. Please provide a number (e.g., `75.5` or `75`).")
        return
    
    log_id = log_weight_db(weight_int)
    
    await ctx.reply(f"✅ **Weight logged!** (ID: `{log_id}`)\n⚖️ Current Weight: **{weight_int} KG** recorded for {date.today()}.\nNote: Your table only stores weight as an integer (KG).")

@bot.command(name="view_progress")
async def view_progress(ctx):
    """Displays your last 10 logged body weight entries."""
    history = get_weight_history()
    
    if not history:
        await ctx.reply("📈 No weight logs found. Use `!log_weight <weight_kg>` to start tracking.")
        return
        
    headers = ["Date", "Weight (KG)"]
    rows = []
    
    for entry in history:
        date_str = entry[0].strftime("%b %d")
        weight_str = str(entry[1])
        
        rows.append([date_str, weight_str])

    table = create_table(headers, rows)

    embed = discord.Embed(title="📊 Weight Progress (Last 10 Entries)", color=discord.Color.teal())
    embed.description = f"```text\n{table}\n```"
    await ctx.send(embed=embed)


# ---------------------------
# RUN BOT
# ---------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
