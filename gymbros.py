"""
FastAPI Backend for FitTrack Flutter App
Deploy this to Railway, Render, or any cloud host.

Install: pip install fastapi uvicorn sqlalchemy pymysql python-dotenv
Run locally: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from datetime import date, datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy import exc as sa_exc

# ---------------------------
load_dotenv()
# ---------------------------

DB_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}{':' + os.getenv('DB_PORT') if os.getenv('DB_PORT') else ''}"
    f"/{os.getenv('DB_NAME')}"
)
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)

app = FastAPI(title="FitTrack API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    discord_id: int
    discord_name: str

class EndSessionRequest(BaseModel):
    session_id: int
    calories: int

class CardioRequest(BaseModel):
    session_id: int
    discord_id: int
    discord_name: str
    machine_type: str
    duration_minutes: int
    distance: Optional[float] = None
    calories_burned: Optional[int] = None
    notes: Optional[str] = None

class LiftRequest(BaseModel):
    session_id: int
    discord_id: int
    discord_name: str
    exercise_name: str
    muscle_group: str
    sets: int
    reps: int
    weight: int
    notes: Optional[str] = None

class WeightRequest(BaseModel):
    discord_id: int
    weight_kg: float

# ─── Sessions ─────────────────────────────────────────────────────────────────

@app.post("/sessions/start")
def start_session(req: StartSessionRequest):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO gym_sessions (discord_id, discord_name, date, start_time, notes)
                VALUES (:discord_id, :discord_name, :session_date, :start_time, :notes)
            """),
            {
                "discord_id": req.discord_id,
                "discord_name": req.discord_name,
                "session_date": date.today(),
                "start_time": datetime.now().strftime("%H:%M:%S"),
                "notes": f"Started by {req.discord_name}",
            },
        )
        return {"session_id": result.lastrowid, "message": "Session started"}


@app.get("/sessions/active/{discord_id}")
def get_active_session(discord_id: int):
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT session_id, date, start_time, notes
                FROM gym_sessions
                WHERE discord_id = :discord_id AND end_time IS NULL
                ORDER BY session_id DESC LIMIT 1
            """),
            {"discord_id": discord_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No active session")
    return {
        "session_id": row[0],
        "date": str(row[1]),
        "start_time": str(row[2]),
        "notes": row[3],
    }


@app.post("/sessions/end")
def end_session(req: EndSessionRequest):
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE gym_sessions
                SET end_time = :end_time, total_calories = :calories
                WHERE session_id = :session_id
            """),
            {
                "end_time": datetime.now().strftime("%H:%M:%S"),
                "calories": req.calories,
                "session_id": req.session_id,
            },
        )
    return {"message": "Session ended"}


@app.get("/sessions/{session_id}")
def get_session_details(session_id: int):
    with engine.connect() as conn:
        session = conn.execute(
            text("SELECT session_id, date, start_time, end_time, total_calories, notes FROM gym_sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        cardio = conn.execute(
            text("SELECT machine_type, duration_minutes, distance, calories_burned, notes FROM cardio_logs WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchall()

        lifts = conn.execute(
            text("SELECT exercise_name, muscle_group, sets, reps, weight, notes FROM weightlift_logs WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchall()

    return {
        "session": {
            "session_id": session[0], "date": str(session[1]),
            "start_time": str(session[2]), "end_time": str(session[3]),
            "total_calories": session[4], "notes": session[5],
        },
        "cardio": [
            {"machine_type": r[0], "duration_minutes": r[1], "distance": r[2], "calories_burned": r[3], "notes": r[4]}
            for r in cardio
        ],
        "lifts": [
            {"exercise_name": r[0], "muscle_group": r[1], "sets": r[2], "reps": r[3], "weight": r[4], "notes": r[5]}
            for r in lifts
        ],
    }


@app.get("/sessions/history/{discord_id}")
def get_history(discord_id: int):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT session_id, date, start_time, end_time, total_calories
                FROM gym_sessions
                WHERE discord_id = :uid AND end_time IS NOT NULL
                ORDER BY session_id DESC LIMIT 5
            """),
            {"uid": discord_id},
        ).fetchall()

    results = []
    for s in rows:
        try:
            start_dt = datetime.combine(date.today(), (datetime.min + s[2]).time())
            end_dt = datetime.combine(date.today(), (datetime.min + s[3]).time())
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            duration_mins = (end_dt - start_dt).seconds // 60
        except Exception:
            duration_mins = None

        results.append({
            "session_id": s[0],
            "date": str(s[1]),
            "duration_mins": duration_mins,
            "total_calories": s[4],
        })
    return results

# ─── Cardio ───────────────────────────────────────────────────────────────────

@app.post("/cardio")
def add_cardio(req: CardioRequest):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO cardio_logs
                (session_id, discord_id, discord_name, date, machine_type, duration_minutes, distance, calories_burned, notes)
                VALUES (:session_id, :discord_id, :discord_name, :date, :machine_type, :duration, :distance, :calories, :notes)
            """),
            {
                "session_id": req.session_id, "discord_id": req.discord_id,
                "discord_name": req.discord_name, "date": date.today(),
                "machine_type": req.machine_type, "duration": req.duration_minutes,
                "distance": req.distance, "calories": req.calories_burned, "notes": req.notes,
            },
        )
    return {"cardio_id": result.lastrowid, "message": "Cardio logged"}

# ─── Lifts ────────────────────────────────────────────────────────────────────

@app.post("/lifts")
def add_lift(req: LiftRequest):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO weightlift_logs
                (session_id, discord_id, discord_name, date, exercise_name, muscle_group, sets, reps, weight, notes)
                VALUES (:session_id, :discord_id, :discord_name, :date, :exercise, :muscle, :sets, :reps, :weight, :notes)
            """),
            {
                "session_id": req.session_id, "discord_id": req.discord_id,
                "discord_name": req.discord_name, "date": date.today(),
                "exercise": req.exercise_name, "muscle": req.muscle_group,
                "sets": req.sets, "reps": req.reps, "weight": req.weight, "notes": req.notes,
            },
        )
    return {"lift_id": result.lastrowid, "message": "Lift logged"}


@app.get("/lifts/pr/{discord_id}")
def get_personal_records(discord_id: int):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT 
                    exercise_name,
                    MAX(weight) AS max_weight,
                    (
                        SELECT date FROM weightlift_logs
                        WHERE exercise_name = w.exercise_name AND weight = MAX(w.weight) AND discord_id = :discord_id
                        ORDER BY date DESC LIMIT 1
                    ) AS pr_date
                FROM weightlift_logs w
                WHERE discord_id = :discord_id
                GROUP BY exercise_name
                ORDER BY max_weight DESC
            """),
            {"discord_id": discord_id},
        ).fetchall()
    return [{"exercise_name": r[0], "max_weight": r[1], "pr_date": str(r[2]) if r[2] else None} for r in rows]

# ─── Weight Tracking ──────────────────────────────────────────────────────────

@app.post("/weight")
def log_weight(req: WeightRequest):
    with engine.begin() as conn:
        result = conn.execute(
            text("INSERT INTO weight_check (discord_id, date_checked, weight_kg) VALUES (:discord_id, :date_checked, :weight_kg)"),
            {"discord_id": req.discord_id, "date_checked": date.today(), "weight_kg": req.weight_kg},
        )
    return {"log_id": result.lastrowid, "message": "Weight logged"}


@app.get("/weight/{discord_id}")
def get_weight_history(discord_id: int):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT date_checked, weight_kg FROM weight_check WHERE discord_id = :discord_id ORDER BY date_checked ASC LIMIT 10"),
            {"discord_id": discord_id},
        ).fetchall()
    return [{"date_checked": str(r[0]), "weight_kg": float(r[1])} for r in rows]


@app.get("/health")
def health():
    return {"status": "ok"}
