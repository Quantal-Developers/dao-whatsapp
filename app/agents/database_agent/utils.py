from .db_model import User, Client, Goal, Project, Task, Milestone, Asset, Briefing, MeetingTranscript
from datetime import datetime, date
from typing import Optional, List, Any
import json

from .db_model import SessionLocal

MODEL_MAP = {
    "users": User,
    "clients": Client,
    "goals": Goal,
    "projects": Project,
    "tasks": Task,
    "milestones": Milestone,
    "assets": Asset,
    "briefings": Briefing,
    "meeting_transcripts": MeetingTranscript
}

# Valid status values for each table (case-sensitive)
VALID_STATUS = {
    "clients": {
        "type": ["Family", "Privat", "Internal", "External"],
        "status": ["Active", "Archive"]
    },
    "goals": {
        "status": ["Not started", "In progress", "Done"]
    },
    "projects": {
        "status": ["Not started", "In progress", "Stuck", "Done"],
        "priority": ["P1", "P2", "P3"],
        "client_v2": ["Mama Hanh", "Ms Hanh", "Circus Group", "Fully AI", "Gastrofüsterer", "DAO OS", "Mama Le Bao", "Asia Hung", "Clinic OS", "Internal"]
    },
    "tasks": {
        "status": ["Inbox", "Paused/Later (P3)", "Next (P2)", "Now (P1)", "In progress", "Draft Review", "Waiting for Feedback", "Done"],
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "recur_unit": ["Day(s)", "Week(s)", "Month(s)", "Month(s) on the First Weekday", "Month(s) on the Last Weekday", "Month(s) on the Last Day", "Year(s)"]
    },
    "milestones": {
        "status": ["Not started", "Backlog", "Paused", "In progress", "High Priority", "Under Review", "Shipped", "Done"]
    },
    "assets": {
        "type": ["Social Media Post", "Image", "Blog", "Doc", "Loom Video", "YouTube Video", "Sheets", "Notion Page"]
    },
    "briefings": {
        "client_type": ["Family", "Privat", "Internal", "External"]
    }
}

def get_session():
    return SessionLocal()

def serialize_record(obj):
    """Convert SQLAlchemy object to dictionary with proper JSON serialization"""
    if obj is None:
        return None
    
    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, list):
            # Handle array fields - ensure proper JSON serialization
            value = value if value is not None else []
        result[column.name] = value
    return result

def parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime object"""
    if not date_str:
        return None
    try:
        # Try parsing as full datetime first (YYYY-MM-DD HH:MM:SS format)
        if 'T' in date_str or ' ' in date_str:
            # Handle ISO format with T separator or space separator
            for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%d %H:%M:%S.%f']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        # Try parsing as date only (YYYY-MM-DD format) and convert to datetime
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj  # This will be datetime at midnight
        except ValueError:
            pass
        return None
    except Exception:
        return None

def parse_array_field(value: Any) -> Optional[List]:
    """Parse array field input to proper list format"""
    if value is None:
        return None
    
    if isinstance(value, list):
        return value
    elif isinstance(value, str):
        try:
            # Try parsing as JSON array
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            else:
                # Single value, wrap in list
                return [parsed]
        except json.JSONDecodeError:
            # Treat as comma-separated values
            return [item.strip() for item in value.split(',') if item.strip()]
    else:
        # Single value, wrap in list
        return [value]

def validate_field_value(table: str, field: str, value: str) -> dict:
    """Validate field value against valid options"""
    if table not in VALID_STATUS:
        return {"is_valid": True, "suggested_value": value}
    
    table_validations = VALID_STATUS[table]
    
    # Check if field has validation rules
    if field not in table_validations:
        return {"is_valid": True, "suggested_value": value}
    
    valid_values = table_validations[field]
    value_lower = value.lower()
    
    # Check for exact match (case-insensitive)
    for valid_value in valid_values:
        if value_lower == valid_value.lower():
            return {"is_valid": True, "suggested_value": valid_value}
    
    # Find closest match using fuzzy matching
    best_match = None
    best_score = 0
    
    for valid_value in valid_values:
        score = fuzz.ratio(value_lower, valid_value.lower())
        if score > best_score:
            best_score = score
            best_match = valid_value
    
    # If similarity is high enough, suggest the match
    if best_score >= 60:
        return {
            "is_valid": False,
            "suggested_value": best_match,
            "similarity": best_score
        }
    
    # No good match found
    return {
        "is_valid": False,
        "suggested_value": valid_values[0],  # Default to first valid option
        "similarity": best_score
    }