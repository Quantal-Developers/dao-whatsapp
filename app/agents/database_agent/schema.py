from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field

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
