import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, exc as sa_exc
from datetime import datetime, date, timedelta
from typing import List, Any, Optional

# Define a custom exception for database issues within the bot logic
class DatabaseError(Exception):
    """Raised when a database operation fails unexpectedly."""
    pass

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
    raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# ---------------------------
# CREATE DATABASE ENGINE
# ---------------------------
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
# DATABASE HELPERS (Multi-User Updated)
# ---------------------------

def start_session(discord_id: int, discord_username: str):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO gym_sessions (discord_id, discord_username, date, start_time, notes)
                    VALUES (:discord_id, :discord_username, :session_date, :start_time, :notes)
                """),
                {
                    "discord_id": discord_id,
                    "discord_username": discord_username,
                    "session_date": date.today(),
                    "start_time": datetime.now().strftime("%H:%M:%S"),
                    "notes": f"Started by {discord_username}"
                }
            )
            return result.lastrowid
    except sa_exc.OperationalError as e:
        print(f"DB Error in start_session: {e}")
        raise DatabaseError("Could not connect to the database. Try again.")
    except Exception as e:
        print(f"Unexpected DB Error: {e}")
        raise DatabaseError("An unexpected database error occurred.")

def get_active_session(discord_id: int):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT session_id, date, start_time, notes
                    FROM gym_sessions
                    WHERE discord_id = :discord_id AND end_time IS NULL
                    ORDER BY session_id DESC
                    LIMIT 1;
                """),
                {"discord_id": discord_id}
            ).fetchone()
            return result
    except sa_exc.OperationalError as e:
        print(f"DB Error in get_active_session: {e}")
        raise DatabaseError("Could not retrieve active session.")

def end_session(session_id: int, calories: int):
    try:
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
    except sa_exc.OperationalError as e:
        print(f"DB Error in end_session: {e}")
        raise DatabaseError("Could not update the session.")

def insert_cardio_db(session_id: int, discord_id: int, discord_username: str, machine_type: str, 
                     duration: int, distance: float = None, calories: int = None, notes: str = None):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO cardio_logs 
                    (session_id, discord_id, discord_username, date, machine_type, duration_minutes, distance, calories_burned, notes)
                    VALUES (:session_id, :discord_id, :discord_username, :date, :machine_type, :duration, :distance, :calories, :notes)
                """),
                {
                    "session_id": session_id,
                    "discord_id": discord_id,
                    "discord_username": discord_username,
                    "date": date.today(),
                    "machine_type": machine_type,
                    "duration": duration,
                    "distance": distance,
                    "calories": calories,
                    "notes": notes
                }
            )
            return result.lastrowid
    except sa_exc.OperationalError as e:
        print(f"DB Error in insert_cardio_db: {e}")
        raise DatabaseError("Could not log cardio.")

def add_weightlift_db(session_id: int, discord_id: int, discord_username: str, exercise_name: str, 
                      muscle_group: str, sets: int, reps: int, weight: int, notes: str = None):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO weightlift_logs
                    (session_id, discord_id, discord_username, date, exercise_name, muscle_group, sets, reps, weight, notes)
                    VALUES (:session_id, :discord_id, :discord_username, :date, :exercise, :muscle, :sets, :reps, :weight, :notes)
                """),
                {
                    "session_id": session_id,
                    "discord_id": discord_id,
                    "discord_username": discord_username,
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
    except sa_exc.OperationalError as e:
        print(f"DB Error in add_weightlift_db: {e}")
        raise DatabaseError("Could not log lift.")

def get_session_details(session_id: int):
    try:
        with engine.connect() as conn:
            session = conn.execute(
                text("SELECT session_id, date, start_time, end_time, total_calories, notes FROM gym_sessions WHERE session_id = :sid"),
                {"sid": session_id}
            ).fetchone()
            if not session: return None
            cardio = conn.execute(text("SELECT machine_type, duration_minutes, distance, calories_burned, notes FROM cardio_logs WHERE session_id = :sid"), {"sid": session_id}).fetchall()
            lifts = conn.execute(text("SELECT exercise_name, muscle_group, sets, reps, weight, notes FROM weightlift_logs WHERE session_id = :sid"), {"sid": session_id}).fetchall()
            return {"session": session, "cardio": cardio, "lifts": lifts}
    except Exception as e:
        raise DatabaseError("Could not retrieve session details.")

def get_personal_records(discord_id: int):
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("""
                    SELECT exercise_name, MAX(weight) as max_w, MAX(date) as pr_date
                    FROM weightlift_logs 
                    WHERE discord_id = :discord_id
                    GROUP BY exercise_name
                    ORDER BY max_w DESC
                """),
                {"discord_id": discord_id}
            ).fetchall()
    except Exception:
        raise DatabaseError("Could not retrieve PRs.")

def log_weight_db(discord_id: int, discord_username: str, weight_kg: float):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("INSERT INTO weight_check (discord_id, discord_username, date_checked, weight_kg) VALUES (:discord_id, :discord_username, :d, :w)"),
                {"discord_id": discord_id, "discord_username": discord_username, "d": date.today(), "w": int(weight_kg)}
            )
            return result.lastrowid
    except Exception:
        raise DatabaseError("Could not log weight.")

def get_weight_history(discord_id: int):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT date_checked, weight_kg FROM weight_check WHERE discord_id = :discord_id ORDER BY date_checked DESC LIMIT 10"),
            {"discord_id": discord_id}
        ).fetchall()

# ---------------------------
# Aesthetic Table Helper (Kept Original)
# ---------------------------

def create_table(headers: List[str], rows: List[List[Any]]) -> str:
    processed_rows = []
    for row in rows:
        processed_rows.append([str(cell) if cell is not None else "-" for cell in row])
    col_widths = [len(h) for h in headers]
    for row in processed_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    def make_line(left: str, mid: str, right: str, fill: str) -> str:
        return left + mid.join([fill * (w + 2) for w in col_widths]) + right
    top, middle, bottom = make_line("┌", "┬", "┐", "─"), make_line("├", "┼", "┤", "─"), make_line("└", "┴", "┘", "─")
    lines = [top]
    header_row = "│"
    for i, h in enumerate(headers):
        header_row += f" {h:<{col_widths[i]}} │"
    lines.extend([header_row, middle])
    for row in processed_rows:
        line = "│"
        for i, cell in enumerate(row):
            line += f" {str(cell):<{col_widths[i]}} │"
        lines.append(line)
    lines.append(bottom)
    return "\n".join(lines)

# ---------------------------
# BOT EVENTS & ERROR HANDLING
# ---------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
    print("Bot is now running!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided! Check your numbers.")
    elif isinstance(error, DatabaseError):
        await ctx.send(f"❌ Database Error: {error}")
    else:
        print(f"Critical Error: {error}")
        await ctx.send("❌ An unexpected error occurred.")

# ---------------------------
# BOT COMMANDS
# ---------------------------

@bot.command()
async def session_start(ctx, *, notes: str = None):
    try:
        active = get_active_session(ctx.author.id)
        if active:
            return await ctx.reply(f"⚠️ You already have an active session (ID: **{active[0]}**).")
        session_id = start_session(ctx.author.id, str(ctx.author))
        await ctx.reply(f"✅ **Gym session started!**\n📋 Session ID: **{session_id}**\n💪 Let's crush this, {ctx.author.name}!")
    except DatabaseError as e: await ctx.reply(f"❌ {e}")

@bot.command()
async def add_lift(ctx, exercise: str, muscle: str, sets: int, reps: int, weight: int, *, notes: str = None):
    try:
        active = get_active_session(ctx.author.id)
        if not active: return await ctx.reply("❌ No active session found.")
        lift_id = add_weightlift_db(active[0], ctx.author.id, str(ctx.author), exercise, muscle, sets, reps, weight, notes)
        await ctx.reply(f"✅ **Lift logged!** (ID: `{lift_id}`)\n💪 Exercise: **{exercise}** log by **{ctx.author.name}**")
    except DatabaseError as e: await ctx.reply(f"❌ {e}")

@bot.command(name="pr")
async def pr(ctx):
    try:
        records = get_personal_records(ctx.author.id)
        if not records: return await ctx.reply("🏅 No lifts logged yet!")
        headers, rows = ["Exercise", "Max (kg)", "Date"], []
        for r in records:
            rows.append([r[0][:15], r[1], r[2].strftime("%b %d") if r[2] else "-"] )
        table = create_table(headers, rows)
        await ctx.send(f"🏆 **{ctx.author.name}'s Personal Records**\n```text\n{table}\n```")
    except DatabaseError as e: await ctx.reply(f"❌ {e}")

@bot.command()
async def session_end(ctx):
    try:
        active = get_active_session(ctx.author.id)
        if not active: return await ctx.reply("❌ No active session.")
        
        session_id, start_val = active[0], active[2]
        # Your original time parsing logic
        if isinstance(start_val, timedelta): start_time_obj = (datetime.min + start_val).time()
        else: start_time_obj = datetime.strptime(str(start_val), "%H:%M:%S").time()

        duration = (datetime.combine(date.today(), datetime.now().time()) - datetime.combine(date.today(), start_time_obj)).seconds // 60
        await ctx.reply(f"📊 Session **{session_id}** duration: **{duration}m**.\nHow many calories burned? 🔥")

        def check(msg): return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.isdigit()
        msg = await bot.wait_for("message", check=check, timeout=60)
        end_session(session_id, int(msg.content))
        await ctx.reply(f"✅ **Session ended, {ctx.author.name}!** 💪")
    except Exception: await ctx.reply("❌ Error ending session.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | Multi-user mode active.")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
