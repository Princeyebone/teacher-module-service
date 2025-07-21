from typing import List
from datetime import date
from pydantic import BaseModel
import google.generativeai as genai
import json
from model import AcademicCalendar, WeeklyTimeTable, CalendarEvent  # import your models
from config import settings  


# Example: using your Pydantic models (simplified)
class Timetable(BaseModel):
    weekday: str
    pupils: str
    subject: str
    start_time: str
    end_time: str
    location: str | None = None

class AcademicCalendar(BaseModel):
    semester_name: str
    academic_level: str | None = None
    semester_start_date: date
    mid_semester_break_start_date: date | None = None
    mid_semester_break_end_date: date | None = None
    semester_end_date: date

class CalendarEvent(BaseModel):
    event_name: str | None = None
    event_start_date: date | None = None
    event_end_date: date | None = None
    event_start_time: str | None = None
    event_end_time: str | None = None
    is_holiday: bool | None = None
    requires_no_classes: bool | None = None


def build_gemini_prompt(calendar: AcademicCalendar, 
                        timetable: List[Timetable], 
                        events: List[CalendarEvent], 
                        country:str)->str:
    """
    Build the AI prompt to generate class sessions & planner events.
    """

    # Format Academic Calendar
    cal_text = (
        f"Semester: {calendar.semester_name}, Level: {calendar.academic_level or 'N/A'}\n"
        f"Start: {calendar.semester_start_date}, "
        f"Mid-Semester Break: {calendar.mid_semester_break_start_date or 'None'} to {calendar.mid_semester_break_end_date or 'None'}, "
        f"End: {calendar.semester_end_date}\n"
        f"COUNTRY: {country}"
    )

    # Format Weekly Timetable
    days = {}
    for t in timetable:
        days.setdefault(t.weekday, []).append(
            f"- {t.start_time}-{t.end_time}: {t.subject} (for {t.pupils})"
        )
    tt_text = "\n".join([f"{d}:\n" + "\n".join(s) for d, s in days.items()])

    # Format Events
    ev_text = "\n".join([
        f"- {e.event_start_date} {e.event_start_time or '00:00'}-{e.event_end_time or '23:59'}: {e.event_name} "
        f"[{'holiday' if e.is_holiday else 'event'}{' ,requires_no_classes=True' if e.requires_no_classes else ''}]"
        for e in events
    ]) or "No special events."

    # Build Final Prompt
    prompt = f"""
You are a scheduling assistant.

TASK:
Generate a complete class session schedule and planner events for the semester based on the academic calendar, weekly timetable, and special events provided.

RULES:
1. Only schedule classes on valid teaching days (skip weekends, holidays, or breaks).
2. Follow the weekly timetable strictly for subjects, times, and pupils.
3. Skip any day where an event requires no classes.
4. Number sessions per subject starting from 1.
5. Consider national holidays for {country} (even if not explicitly provided).
6. Output only valid JSON exactly in the format below.

OUTPUT FORMAT:
{{
  "class_sessions": [
    {{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "subject": "Mathematics", "class_name": "Basic 5", "session_number": 1}}
  ],
  "planner_events": [
    {{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "title": "Staff Meeting", "description": "Discuss mid-semester results", "event_type": "meeting", "related_session_id": null}}
  ]
}}

INPUT DATA:

ACADEMIC CALENDAR:
{cal_text}

WEEKLY TIMETABLE:
{tt_text}

CALENDAR EVENTS:
{ev_text}
    """.strip()

    return prompt



def call_gemini_schedule(calendar: AcademicCalendar, timetable: list[WeeklyTimeTable], events: list[CalendarEvent], country: str = "Ghana"):
    # STEP 1: Build the AI prompt
    prompt = build_gemini_prompt(calendar, timetable, events, country)

    # STEP 2: Set up Gemini client
    genai.configure(settings.API_KEY)  # Replace with env var or config


    model = genai.GenerativeModel("gemini-1.5-flash")

    try:
        # STEP 3: Send prompt
        response = model.generate_content(prompt)

        # STEP 4: Extract JSON
        text = response.text.strip()

        # Some responses may wrap JSON in triple backticks, remove them
        if text.startswith("```json"):
            text = text.removeprefix("```json").removesuffix("```").strip()
        elif text.startswith("```"):
            text = text.removeprefix("```").removesuffix("```").strip()

        # Parse the JSON
        parsed = json.loads(text)

        return parsed["class_sessions"], parsed["planner_events"]

    except Exception as e:
        print("❌ Gemini Error:", e)
        return [], []

