import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, date
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, ForeignKey, func, text, inspect, ARRAY, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import Enum
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from fuzzywuzzy import fuzz, process

from .db_model import Base, User, Client, Goal, Project, Task, Milestone, Asset, Briefing, MeetingTranscript, SessionLocal
from .utils import get_session, serialize_record, parse_date_string, parse_array_field, validate_field_value, MODEL_MAP, VALID_STATUS

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Models for Tool Inputs/Outputs
# ──────────────────────────────────────────────────────────────────────────────

class CreateRecordInput(BaseModel):
    table: Literal["users", "clients", "goals", "projects", "tasks", "milestones", "assets", "briefings", "meeting_transcripts"] = Field(description="Database table name")
    data: Dict[str, Any] = Field(description="Record data as key-value pairs")

class CreateRecordOutput(BaseModel):
    success: bool = Field(description="Operation success status")
    record_id: Optional[int] = Field(description="Created record ID")
    message: str = Field(description="Operation result message")
    error: Optional[str] = Field(description="Error message if failed")

class ReadRecordInput(BaseModel):
    table: Literal["users", "clients", "goals", "projects", "tasks", "milestones", "assets", "briefings", "meeting_transcripts"] = Field(description="Database table name")
    record_id: int = Field(description="Record ID to retrieve")

class ReadRecordOutput(BaseModel):
    success: bool = Field(description="Operation success status")
    record: Optional[Dict[str, Any]] = Field(description="Retrieved record data")
    message: str = Field(description="Operation result message")
    error: Optional[str] = Field(description="Error message if failed")

class UpdateRecordInput(BaseModel):
    table: Literal["users", "clients", "goals", "projects", "tasks", "milestones", "assets", "briefings", "meeting_transcripts"] = Field(description="Database table name")
    record_id: int = Field(description="Record ID to update")
    data: Dict[str, Any] = Field(description="Updated data as key-value pairs")

class ListRecordsInput(BaseModel):
    table: Literal["users", "clients", "goals", "projects", "tasks", "milestones", "assets", "briefings", "meeting_transcripts"] = Field(description="Database table name")
    limit: int = Field(default=10, description="Maximum records to return")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Filter conditions")

class ListRecordsOutput(BaseModel):
    success: bool = Field(description="Operation success status")
    records: List[Dict[str, Any]] = Field(description="List of records")
    count: int = Field(description="Number of records returned")
    message: str = Field(description="Operation result message")

class DeleteRecordInput(BaseModel):
    table: Literal["users", "clients", "goals", "projects", "tasks", "milestones", "assets", "briefings", "meeting_transcripts"] = Field(description="Database table name")
    record_id: int = Field(description="Record ID to delete")

class SearchRecordsInput(BaseModel):
    table: Literal["users", "clients", "goals", "projects", "tasks", "milestones", "assets", "briefings", "meeting_transcripts"] = Field(description="Database table name")
    name_query: str = Field(description="Name to search for (case-insensitive, supports partial matching)")
    limit: int = Field(default=10, description="Maximum records to return")
    min_similarity: int = Field(default=60, description="Minimum similarity score (0-100) for fuzzy matching")

class SearchRecordsOutput(BaseModel):
    success: bool = Field(description="Operation success status")
    records: List[Dict[str, Any]] = Field(description="List of matching records")
    count: int = Field(description="Number of records returned")
    message: str = Field(description="Operation result message")
    suggestions: Optional[List[Dict[str, Any]]] = Field(description="Similar name suggestions if no exact matches")

# ──────────────────────────────────────────────────────────────────────────────
# Database Tools
# ──────────────────────────────────────────────────────────────────────────────

@tool("create_record", args_schema=CreateRecordInput, return_direct=False)
def create_record(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new record in the specified table"""
    try:
        # Validate table name
        if table not in MODEL_MAP:
            return {
                "success": False,
                "error": f"Invalid table name: {table}. Valid tables: {list(MODEL_MAP.keys())}"
            }
        
        # Check if name is provided and not empty
        if not data.get('name') or not str(data.get('name')).strip():
            return {
                "success": False,
                "requires_confirmation": True,
                "pending_table": table,
                "pending_data": data,
                "message": f"⚠️ The 'name' field is required but was empty. Would you like to proceed with creating the {table} record with an empty name?"
            }
        
        # Validate field values
        validation_result = validate_field_value(table, "name", data.get('name'))
        if not validation_result['is_valid']:
            return {
                "success": False,
                "requires_field_confirmation": True,
                "pending_table": table,
                "pending_data": data,
                "field": "name",
                "user_value": data.get('name'),
                "suggested_value": validation_result['suggested_value'],
                "message": f"⚠️ Invalid name value: '{data.get('name')}'. Did you mean '{validation_result['suggested_value']}'?"
            }
        
        # Process data
        processed_data = {}
        for key, value in data.items():
            if key in ['deadline', 'due_date', 'meeting_date', 'date_completed']:
                processed_data[key] = parse_date_string(str(value))
            elif key in ['tags', 'project_id', 'client_id', 'task_id', 'milestone_id', 'asset_id', 'briefing_id', 'meeting_transcript_id', 'goal_id', 'owner_id', 'assigned_to_id']:
                processed_data[key] = parse_array_field(value)
            else:
                processed_data[key] = value
        
        # Create record
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            new_record = model_class(**processed_data)
            session.add(new_record)
            session.commit()
            record_id = new_record.id
            
            return {
                "success": True,
                "record_id": record_id,
                "message": f"Successfully created {table} record with ID {record_id}"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error creating record: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to create record: {str(e)}"
        }

@tool("read_record", args_schema=ReadRecordInput, return_direct=False)
def read_record(table: str, record_id: int) -> Dict[str, Any]:
    """Read a specific record by ID"""
    try:
        if table not in MODEL_MAP:
            return {
                "success": False,
                "error": f"Invalid table name: {table}. Valid tables: {list(MODEL_MAP.keys())}"
            }
        
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            record = session.query(model_class).filter(model_class.id == record_id).first()
            
            if not record:
                return {
                    "success": False,
                    "error": f"No {table} record found with ID {record_id}"
                }
            
            return {
                "success": True,
                "record": serialize_record(record),
                "message": f"Successfully retrieved {table} record with ID {record_id}"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error reading record: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to read record: {str(e)}"
        }

@tool("update_record", args_schema=UpdateRecordInput, return_direct=False)
def update_record(table: str, record_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing record"""
    try:
        if table not in MODEL_MAP:
            return {
                "success": False,
                "error": f"Invalid table name: {table}. Valid tables: {list(MODEL_MAP.keys())}"
            }
        
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            record = session.query(model_class).filter(model_class.id == record_id).first()
            
            if not record:
                return {
                    "success": False,
                    "error": f"No {table} record found with ID {record_id}"
                }
            
            # Validate field values
            for field, value in data.items():
                validation_result = validate_field_value(table, field, str(value))
                if not validation_result['is_valid']:
                    return {
                        "success": False,
                        "requires_field_confirmation": True,
                        "pending_table": table,
                        "pending_record_id": record_id,
                        "pending_data": data,
                        "field": field,
                        "user_value": str(value),
                        "suggested_value": validation_result['suggested_value'],
                        "message": f"⚠️ Invalid {field} value: '{value}'. Did you mean '{validation_result['suggested_value']}'?"
                    }
            
            # Process data
            processed_data = {}
            for key, value in data.items():
                if key in ['deadline', 'due_date', 'meeting_date', 'date_completed']:
                    processed_data[key] = parse_date_string(str(value))
                elif key in ['tags', 'project_id', 'client_id', 'task_id', 'milestone_id', 'asset_id', 'briefing_id', 'meeting_transcript_id', 'goal_id', 'owner_id', 'assigned_to_id']:
                    processed_data[key] = parse_array_field(value)
                else:
                    processed_data[key] = value
            
            # Update record
            for key, value in processed_data.items():
                setattr(record, key, value)
            
            session.commit()
            
            return {
                "success": True,
                "message": f"Successfully updated {table} record with ID {record_id}"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error updating record: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to update record: {str(e)}"
        }

@tool("list_records", args_schema=ListRecordsInput, return_direct=False)
def list_records(table: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List records with optional filtering"""
    try:
        if table not in MODEL_MAP:
            return {
                "success": False,
                "error": f"Invalid table name: {table}. Valid tables: {list(MODEL_MAP.keys())}"
            }
        
        if limit > 100:
            limit = 100
        
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            query = session.query(model_class)
            
            # Apply filters
            if filters:
                for key, value in filters.items():
                    if hasattr(model_class, key):
                        if isinstance(value, str) and key in ['deadline', 'due_date', 'meeting_date', 'date_completed']:
                            # Handle date filtering
                            date_value = parse_date_string(value)
                            if date_value:
                                query = query.filter(getattr(model_class, key) == date_value)
                        else:
                            query = query.filter(getattr(model_class, key) == value)
            
            records = query.limit(limit).all()
            serialized_records = [serialize_record(record) for record in records]
            
            return {
                "success": True,
                "records": serialized_records,
                "count": len(serialized_records),
                "message": f"Retrieved {len(serialized_records)} {table} records"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error listing records: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to list records: {str(e)}"
        }

@tool("delete_record", args_schema=DeleteRecordInput, return_direct=False)
def delete_record(table: str, record_id: int) -> Dict[str, Any]:
    """Delete a record by ID"""
    try:
        if table not in MODEL_MAP:
            return {
                "success": False,
                "error": f"Invalid table name: {table}. Valid tables: {list(MODEL_MAP.keys())}"
            }
        
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            record = session.query(model_class).filter(model_class.id == record_id).first()
            
            if not record:
                return {
                    "success": False,
                    "error": f"No {table} record found with ID {record_id}"
                }
            
            session.delete(record)
            session.commit()
            
            return {
                "success": True,
                "message": f"Successfully deleted {table} record with ID {record_id}"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error deleting record: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to delete record: {str(e)}"
        }

@tool("get_database_stats", return_direct=False)
def get_database_stats() -> Dict[str, Any]:
    """Get database statistics and overview"""
    try:
        session = get_session()
        try:
            stats = {}
            for table_name, model_class in MODEL_MAP.items():
                count = session.query(model_class).count()
                stats[table_name] = count
            
            total_records = sum(stats.values())
            
            return {
                "success": True,
                "stats": stats,
                "total_records": total_records,
                "message": f"Database contains {total_records} total records across {len(MODEL_MAP)} tables"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to get database stats: {str(e)}"
        }

@tool("search_records_by_name", args_schema=SearchRecordsInput, return_direct=False)
def search_records_by_name(table: str, name_query: str, limit: int = 10, min_similarity: int = 60) -> Dict[str, Any]:
    """Search records by name using fuzzy matching"""
    try:
        if table not in MODEL_MAP:
            return {
                "success": False,
                "error": f"Invalid table name: {table}. Valid tables: {list(MODEL_MAP.keys())}"
            }
        
        if limit > 100:
            limit = 100
        
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            all_records = session.query(model_class).all()
            
            # Perform fuzzy matching
            matches = []
            for record in all_records:
                if hasattr(record, 'name') and record.name:
                    similarity = fuzz.partial_ratio(name_query.lower(), record.name.lower())
                    if similarity >= min_similarity:
                        matches.append({
                            'record': serialize_record(record),
                            'similarity': similarity
                        })
            
            # Sort by similarity score
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Limit results
            limited_matches = matches[:limit]
            records = [match['record'] for match in limited_matches]
            
            # Generate suggestions if no good matches
            suggestions = []
            if not records and all_records:
                all_names = [record.name for record in all_records if hasattr(record, 'name') and record.name]
                if all_names:
                    suggestions = process.extract(name_query, all_names, limit=5)
                    suggestions = [{'name': name, 'similarity': score} for name, score in suggestions]
            
            return {
                "success": True,
                "records": records,
                "count": len(records),
                "suggestions": suggestions if suggestions else None,
                "message": f"Found {len(records)} {table} records matching '{name_query}'"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error searching records: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to search records: {str(e)}"
        }

@tool("get_current_datetime", return_direct=False)
def get_current_datetime() -> Dict[str, Any]:
    """Get the current date and time"""
    try:
        now = datetime.now()
        return {
            "success": True,
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": str(now.astimezone().tzinfo),
            "message": f"Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        }
    except Exception as e:
        logger.error(f"Error getting current datetime: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to get current datetime: {str(e)}"
        }

# ──────────────────────────────────────────────────────────────────────────────
# Confirmation Tools
# ──────────────────────────────────────────────────────────────────────────────

@tool("confirm_create_with_empty_name", return_direct=False)
def confirm_create_with_empty_name(table: str, **data) -> Dict[str, Any]:
    """Confirm creation of record with empty name"""
    try:
        session = get_session()
        try:
            model_class = MODEL_MAP[table]
            new_record = model_class(**data)
            session.add(new_record)
            session.commit()
            record_id = new_record.id
            
            return {
                "success": True,
                "record_id": record_id,
                "message": f"Successfully created {table} record with ID {record_id} (empty name)"
            }
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error creating record with empty name: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to create record: {str(e)}"
        }

@tool("confirm_create_with_corrected_field", return_direct=False)
def confirm_create_with_corrected_field(table: str, data: Dict[str, Any], field: str, corrected_value: str) -> Dict[str, Any]:
    """Confirm creation with corrected field value"""
    try:
        data[field] = corrected_value
        return create_record(table, data)
    except Exception as e:
        logger.error(f"Error creating record with corrected field: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to create record: {str(e)}"
        }

@tool("confirm_field_correction", return_direct=False)
def confirm_field_correction(table: str, record_id: int, field: str, corrected_value: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Confirm field correction for update operation"""
    try:
        data[field] = corrected_value
        return update_record(table, record_id, data)
    except Exception as e:
        logger.error(f"Error updating record with corrected field: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to update record: {str(e)}"
        }

