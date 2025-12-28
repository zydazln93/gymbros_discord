import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, exc as sa_exc
from datetime import datetime, date, timedelta
from typing import List, Any, Optional

# --- CUSTOM ERROR ---
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
# ROBUST DATABASE HELPER FUNCTIONS (Multi-User Updated)
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
        raise DatabaseError("Could not retrieve active session due to database issue.")

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
        raise DatabaseError("Could not update the session due to database issue.")

def insert_cardio_db(session_id: int, discord_id: int, discord_username: str, machine_type: str, duration: int, 
                     distance: float = None, calories: int = None, notes: str = None):
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
        raise DatabaseError("Could not log cardio due to database issue.")

def add_weightlift_db(session_id: int, discord_id: int, discord_username: str, exercise_name: str, muscle_group: str,
                      sets: int, reps: int, weight: int, notes: str = None):
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
        raise DatabaseError("Could not log lift due to database issue.")

def get_session_details(session_id: int):
    try:
        with engine.connect() as conn:
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
    except sa_exc.OperationalError as e:
        print(f"DB Error in get_session_details: {e}")
        raise DatabaseError("Could not retrieve session details due to database issue.")

def get_personal_records(discord_id: int):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT 
                        exercise_name,
                        MAX(weight) AS max_weight,
                        (
                            SELECT date 
                            FROM weightlift_logs 
                            WHERE exercise_name = w.exercise_name AND weight = MAX(w.weight) AND discord_id = :discord_id
                            ORDER BY date DESC 
                            LIMIT 1
                        ) AS pr_date
                    FROM weightlift_logs w
                    WHERE discord_id = :discord_id
                    GROUP BY exercise_name
                    ORDER BY max_weight DESC
                """),
                {"discord_id": discord_id}
            ).fetchall()
            return result
    except sa_exc.OperationalError as e:
        print(f"DB Error in get_personal_records: {e}")
        raise DatabaseError("Could not retrieve personal records due to database issue.")

# --- Weight Tracking Helpers ---

def log_weight_db(discord_id: int, weight_kg: float) -> int:
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO weight_check (discord_id, date_checked, weight_kg)
                    VALUES (:discord_id, :date_checked, :weight_kg)
                """),
                {
                    "discord_id": discord_id,
                    "date_checked": date.today(),
                    "weight_kg": weight_kg
                }
            )
            return result.lastrowid
    except sa_exc.OperationalError as e:
        print(f"DB Error in log_weight_db: {e}")
        raise DatabaseError("Could not log weight due to database issue.")

def get_weight_history(discord_id: int):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT date_checked, weight_kg
                    FROM weight_check
                    WHERE discord_id = :discord_id
                    ORDER BY date_checked DESC
                    LIMIT 10
                """),
                {"discord_id": discord_id}
            ).fetchall()
            return result
    except sa_exc.OperationalError as e:
        print(f"DB Error in get_weight_history: {e}")
        raise DatabaseError("Could not retrieve weight history due to database issue.")

# ---------------------------
# BOT EVENTS
# ---------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
    except sa_exc.OperationalError as e:
        print(f"✗ Database connection failed. Fatal Error: {e}")
    except Exception as e:
        print(f"✗ An unexpected error occurred during setup: {e}")
    print("Bot is now running!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`. Check `!command` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument provided! Ensure numbers are correct and check `!command`.")
    elif isinstance(error, DatabaseError): 
        await ctx.send(f"❌ Database Error: {error}. Please try again in a few seconds.")
    else:
        print(f"Critical Error: {error}")
        await ctx.send("❌ An unexpected error occurred while processing your command!")

# ---------------------------
# Aesthetic Table Helper 
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

    top = make_line("┌", "┬", "┐", "─")
    middle = make_line("├", "┼", "┤", "─")
    bottom = make_line("└", "┴", "┘", "─")
    
    lines = [top]
    header_row = "│"
    for i, h in enumerate(headers):
        header_row += f" {h:<{col_widths[i]}} │"
    lines.append(header_row)
    lines.append(middle)
    
    for row in processed_rows:
        line = "│"
        for i, cell in enumerate(row):
            line += f" {str(cell):<{col_widths[i]}} │"
        lines.append(line)
    
    lines.append(bottom)
    return "\n".join(lines)


# ---------------------------
# BOT COMMANDS
# ---------------------------

@bot.command()
async def command(ctx):
    """Display all available bot commands with examples"""
    embed = discord.Embed(
        title="🤖 Fitness Tracker Bot - Command List",
        description="Here are all available commands:",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="📋 Session Management",
        value=(
            "```"
            "!session_start [notes]      Start a new gym session\n"
            "!session_end                End active session (asks for calories)\n"
            "!current                    View your active session\n"
            "!session <id>               View specific session details\n"
            "!today                      View all today's sessions"
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
    
    embed.add_field(
        name="⚖️ Weight Tracking",
        value=(
            "```"
            "!log_weight <weight_kg>     Log current body weight in KG\n"
            "!view_progress              View last 10 weight logs"
            "```"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Reporting",
        value=(
            "```"
            "!history                    View last 5 completed sessions\n"
            "!pr                         View your Personal Records"
            "```"
        ),
        inline=False
    )
    embed.set_footer(text="💪 Track your gains! | Made for fitness enthusiasts")
    await ctx.send(embed=embed)


@bot.command()
async def session_start(ctx, *, notes: str = None):
    try:
        active = get_active_session(ctx.author.id)
        if active:
            await ctx.reply(f"⚠️ You already have an active session (ID: **{active[0]}**).")
            return
        session_id = start_session(ctx.author.id, str(ctx.author))
        await ctx.reply(f"✅ **Gym session started for {ctx.author.name}!**\n📋 Session ID: **{session_id}**\n⏰ Start time: {datetime.now().strftime('%H:%M')}")
    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")
    except Exception:
        await ctx.reply("❌ An unexpected error occurred starting the session.")

@bot.command()
async def session_end(ctx):
    try:
        active = get_active_session(ctx.author.id)
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
                await ctx.reply("❌ Error parsing start time.")
                return

        start_dt = datetime.combine(date.today(), start_time_obj)
        end_dt = datetime.now()
        if end_dt < start_dt:
            start_dt -= timedelta(days=1)
            
        duration = (end_dt - start_dt).seconds // 60

        await ctx.reply(f"📊 Session ID **{session_id}** found. Duration: **{duration} minutes**.\nHow many calories did you burn? 🔥")
        
        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.isdigit()
        
        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            calories = int(msg.content)
            end_session(session_id, calories)
            await ctx.reply(f"✅ **Session ended!** 🔥 Total calories recorded: **{calories}**")
        except Exception:
            await ctx.reply("⏳ Timeout or error! Session remains active.")

    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")
    except Exception:
        await ctx.reply("❌ An unexpected error occurred ending the session.")


@bot.command()
async def add_cardio(ctx, machine: str, duration: int, distance: float = None, calories: int = None, *, notes: str = None):
    try:
        active = get_active_session(ctx.author.id)
        if not active:
            await ctx.reply("❌ No active session found.")
            return
        
        insert_cardio_db(active[0], ctx.author.id, str(ctx.author), machine, duration, distance, calories, notes)

        # Display zero instead of None if you leave the calories section blank
        cal_display = calories if calories is not None else 0
        
        await ctx.reply(
            f"✅ **Cardio logged!**\n" 
            f"🏃 Machine: **{machine}**\n"
            f"⏱️ **{duration} min**\n"
            f"🔥 Calories Burned: **{cal_display} calories**"
        )
    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")

@bot.command()
async def add_lift(ctx, exercise: str, muscle: str, sets: int, reps: int, weight: int, *, notes: str = None):
    try:
        active = get_active_session(ctx.author.id)
        if not active:
            await ctx.reply("❌ No active session found.")
            return
        
        add_weightlift_db(active[0], ctx.author.id, str(ctx.author), exercise, muscle, sets, reps, weight, notes)
        await ctx.reply(
                    f"✅ **Lift logged!** (ID: `{lift_id}`)\n"
                    f"💪 Exercise: **{exercise}**\n"
                    f"🎯 Muscle: **{muscle}**\n"
                    f"📊 **{sets}**×**{reps}** @ **{weight}kg**"
                )
    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")

@bot.command()
async def current(ctx):
    try:
        active = get_active_session(ctx.author.id)
        if not active:
            await ctx.reply("📅 No active session found.")
            return
        details = get_session_details(active[0])
        session = details["session"]
        embed = discord.Embed(title=f"🏋️ Current Session #{session[0]}", color=discord.Color.green())
        embed.add_field(name="📅 Info", value=f"**Date:** {session[1]}\n**Start:** {session[2]}", inline=False)
        
        if details["cardio"]:
            cardio_text = "\n".join([f"• **{log[0]}** ({log[1]}min)" for log in details["cardio"]])
            embed.add_field(name="🏃 Cardio", value=cardio_text, inline=False)
        
        if details["lifts"]:
            lift_text = "\n".join([f"• **{log[0]}**: {log[2]}×{log[3]} @ {log[4]}kg" for log in details["lifts"]])
            embed.add_field(name="💪 Weightlifting", value=lift_text, inline=False)
        
        await ctx.send(embed=embed)
    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")

@bot.command()
async def history(ctx):
    try:
        with engine.connect() as conn:
            # We fetch the raw data from the gym_sessions table
            sessions = conn.execute(
                text("""
                    SELECT session_id, date, start_time, end_time, total_calories
                    FROM gym_sessions
                    WHERE discord_id = :uid AND end_time IS NOT NULL
                    ORDER BY session_id DESC
                    LIMIT 5
                """), {"uid": ctx.author.id}
            ).fetchall()

        if not sessions:
            await ctx.reply("📭 No completed sessions found.")
            return

        headers = ["ID", "Date", "Dur(m)", "Cals"]
        rows = []
        
        for s in sessions:
            session_id, s_date, s_start, s_end, s_cals = s
            
            # --- DURATION CALCULATION ---
            # Convert timedelta/string to a usable format to calculate minutes
            try:
                # Combining with a dummy date to subtract times safely
                start_dt = datetime.combine(date.today(), (datetime.min + s_start).time())
                end_dt = datetime.combine(date.today(), (datetime.min + s_end).time())
                
                # If the session crossed midnight
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                
                duration_mins = (end_dt - start_dt).seconds // 60
            except:
                duration_mins = "???" # Fallback if data is corrupted

            # Append the actual calculated duration instead of "-"
            rows.append([
                f"#{session_id}", 
                s_date.strftime("%b %d"), 
                f"{duration_mins}", 
                s_cals if s_cals is not None else "0"
            ])
        
        table = create_table(headers, rows)
        embed = discord.Embed(title="📜 Workout History", color=discord.Color.dark_theme())
        embed.description = f"```text\n{table}\n```"
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"History Error: {e}")
        await ctx.reply(f"❌ Error generating history: {e}")

@bot.command()
async def pr(ctx):
    try:
        records = get_personal_records(ctx.author.id)
        if not records:
            await ctx.reply("🏅 No records found yet!")
            return

        headers = ["Exercise", "Max (kg)", "Date"]
        rows = [[r[0][:15], r[1], r[2].strftime("%b %d") if r[2] else "-"] for r in records]
        table = create_table(headers, rows)
        
        # Create the embed
        embed = discord.Embed(title="🏆 Personal Records", color=discord.Color.gold())
        
        # Add "User A's personal record" at the very top of the description
        # We use ctx.author.display_name to get their current nickname or username
        user_text = f"**This is {ctx.author.display_name}'s personal records**\n"
        embed.description = f"{user_text}```text\n{table}\n```"
        
        # Optional: Add their avatar icon next to the title for a cleaner look
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)
    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")

@bot.command()
async def log_weight(ctx, weight: float):
    try:
        log_id = log_weight_db(ctx.author.id, weight)
        await ctx.reply(f"✅ **Weight logged!** ⚖️ **{weight} KG** recorded.")
    except DatabaseError as e:
        await ctx.reply(f"❌ {e}")

@bot.command()
async def view_progress(ctx):
    try:
        history = get_weight_history(ctx.author.id)
        if not history:
            await ctx.reply("📈 No logs found.")
            return
        headers = ["Date", "KG"]
        rows = [[entry[0].strftime("%b %d"), str(entry[1])] for entry in history]
        table = create_table(headers, rows)
        embed = discord.Embed(title="📊 Weight Progress", color=discord.Color.teal())
        embed.description = f"```text\n{table}\n```"
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.reply(f"❌ Error: {e}")

# ---------------------------
# RUN BOT
# ---------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)



