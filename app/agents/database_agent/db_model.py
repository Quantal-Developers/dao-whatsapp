import os
import json
import time  # Add this import
import logging
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Date, DateTime, 
    ForeignKey, func, text, inspect, ARRAY,CheckConstraint,Boolean
)
from sqlalchemy.dialects.postgresql import ARRAY # For PostgreSQL-specific array types
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import Enum
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

# Create the declarative base
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    email = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Client(Base):
    __tablename__ = 'clients'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True) # text by default is nullable in PostgreSQL
    
    # Using Enum for type, creating a native ENUM type in PostgreSQL, defined inline
    type = Column(
        Enum('Family', 'Privat', 'Internal', 'External', name='client_type_enum', create_type=True),
        default=None,
        nullable=True
    )
    
    email = Column(Text, default=None, nullable=True)
    contact = Column(Text, default=None, nullable=True)
    website = Column(Text)

    # For array types (integer[] and TEXT[]), use ARRAY from sqlalchemy.dialects.postgresql
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True)

    asset_id = Column(ARRAY(Integer), default=None, nullable=True)
    # asset = Column(ARRAY(Text), default=None, nullable=True)
    
    tags = Column(Text, nullable=True) 

    briefing_id = Column(ARRAY(Integer), default=None, nullable=True)
    # briefing = Column(ARRAY(Text), default=None, nullable=True)

    meeting_transcript_id = Column(ARRAY(Integer), default=None, nullable=True)
    # meeting_transcript = Column(ARRAY(Text), default=None, nullable=True)

    notes = Column(Text, nullable=True) 

    milestone_id = Column(ARRAY(Integer), default=None, nullable=True)
    # milestone = Column(ARRAY(Text), default=None, nullable=True)

    cover = Column(Text, nullable=True) # Stores image URL or path

    goal_id = Column(ARRAY(Integer), default=None, nullable=True)
    # goal = Column(ARRAY(Text), default=None, nullable=True)

    # Using Enum for status, defined inline
    status = Column(
        Enum('Active', 'Archive', name='client_status_enum', create_type=True),
        nullable=True
    )

    task_id = Column(ARRAY(Integer), default=None, nullable=True)
    # task = Column(ARRAY(Text), default=None, nullable=True)

    # TIMESTAMP WITH TIME ZONE defaults to NOW()
    created_at = Column(DateTime(timezone=True), default=func.now())
    # updated_at defaults to NOW() on insert, and updates to NOW() on every update
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


class Goal(Base):
    __tablename__ = 'goals'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True) # Matches 'name text' in SQL, which is nullable

    # Array fields with default NULL and nullable True, matching SQL
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True) # Added based on SQL

    description = Column(Text, default=None, nullable=True)

    # Using Enum for status, defined inline with default
    status = Column(
        Enum('Not started', 'In progress', 'Done', name='goal_status_enum', create_type=True),
        default='Not started',
        nullable=True # 'DEFAULT NULL' is implicit for ENUMs without NOT NULL, but it can also be provided.
                      # Since 'Not started' is a default, it's not strictly nullable in practice,
                      # but the SQL definition allows it to be NULL if no default was set.
                      # However, with a DEFAULT, it will always have a value on insert.
                      # Let's keep it nullable=True as per original 'text' type.
    )

    milestone_id = Column(ARRAY(Integer), default=None, nullable=True)
    # milestone = Column(ARRAY(Text), default=None, nullable=True) # Added based on SQL

    tags = Column(Text, nullable=True) # Matches 'tags text'

    meeting_transcript_id = Column(ARRAY(Integer), default=None, nullable=True)
    # meeting_transcript = Column(ARRAY(Text), default=None, nullable=True) # Added based on SQL

    briefing_id = Column(ARRAY(Integer), default=None, nullable=True) # Added based on SQL
    # briefing = Column(ARRAY(Text), default=None, nullable=True) # Replaced 'briefings = Column(Text)'

    client_id = Column(ARRAY(Integer), default=None, nullable=True)
    # client = Column(ARRAY(Text), default=None, nullable=True) # Added based on SQL

    circus_sync = Column(Boolean, default=False, nullable=False) # Matches 'boolean default false not null'

    corresponding_id = Column(Text, nullable=True)
    current = Column(Integer, default=None, nullable=True)
    goal = Column(Integer, default=None, nullable=True) # This refers to the 'goal' integer column in SQL
    id_pull = Column(Text, nullable=True) # SQL comment indicates formula, but it's a 'text' column
    progress = Column(Text, nullable=True) # SQL comment indicates formula, but it's a 'text' column

    # TIMESTAMP WITH TIME ZONE defaults to NOW() on creation and update
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Table arguments for CHECK constraints on array lengths
    __table_args__ = (
        CheckConstraint('project_id IS NULL OR array_length(project_id, 1) = 1', name='goals_project_id_len_check'),
        CheckConstraint('project IS NULL OR array_length(project, 1) = 1', name='goals_project_len_check'),
        CheckConstraint('meeting_transcript_id IS NULL OR array_length(meeting_transcript_id, 1) = 1', name='goals_mt_id_len_check'),
        CheckConstraint('meeting_transcript IS NULL OR array_length(meeting_transcript, 1) = 1', name='goals_mt_len_check'),
        CheckConstraint('client_id IS NULL OR array_length(client_id, 1) = 1', name='goals_client_id_len_check'),
        CheckConstraint('client IS NULL OR array_length(client, 1) = 1', name='goals_client_len_check'),
    )

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True) # text in PG is nullable by default

    # Priority Enum
    priority = Column(
        Enum('P1', 'P2', 'P3', name='project_priority_enum', create_type=True),
        nullable=True
    )

    # Status Enum with default
    status = Column(
        Enum('Not started', 'In progress', 'Stuck', 'Done', name='project_status_enum', create_type=True),
        default='Not started',
        nullable=True # SQL default doesn't make it NOT NULL automatically
    )
    
    deadline = Column(DateTime(timezone=True), nullable=True)

    command_center = Column(Text, default=None, nullable=True) # Based on final SQL

    # Client relation arrays with length constraint
    client_id = Column(ARRAY(Integer), default=None, nullable=True)
    # client = Column(ARRAY(Text), default=None, nullable=True)
    
    # Briefing relation arrays with length constraint
    briefing_id = Column(ARRAY(Integer), default=None, nullable=True)
    # briefing = Column(ARRAY(Text), default=None, nullable=True)
    
    # Goal relation arrays (no limit)
    goal_id = Column(ARRAY(Integer), default=None, nullable=True)
    # goal = Column(ARRAY(Text), default=None, nullable=True)

    # Milestone array (based on final SQL)
    milestone = Column(ARRAY(Text), default=None, nullable=True) 

    # Task relation arrays (no limit)
    task_id = Column(ARRAY(Integer), default=None, nullable=True)
    # task = Column(ARRAY(Text), default=None, nullable=True)

    # Asset relation arrays (no limit)
    asset_id = Column(ARRAY(Integer), default=None, nullable=True)
    # asset = Column(ARRAY(Text), default=None, nullable=True)
    
    tags = Column(Text, nullable=True)

    # Meeting Transcript relation arrays (no limit)
    meeting_transcript_id = Column(ARRAY(Integer), default=None, nullable=True)
    # meeting_transcript = Column(ARRAY(Text), default=None, nullable=True)

    notes = Column(Text, nullable=True)

    client_display = Column(Text, nullable=True) # Formula field
    date_completed = Column(DateTime(timezone=True), nullable=True)
    date_completed_display = Column(Text, nullable=True) # Formula field
    deadline_display = Column(Text, nullable=True) # Formula field
    overdue_tasks = Column(Text, nullable=True) # Formula field

    # Owner relation arrays (no limit)
    owner_id = Column(ARRAY(Integer), default=None, nullable=True)
    # owner = Column(ARRAY(Text), default=None, nullable=True)

    owner_display = Column(Text, nullable=True) # Formula field
    progress = Column(Text, nullable=True) # Formula field
    remaining_tasks = Column(Text, nullable=True) # Formula field
    space = Column(Text, nullable=True) # Formula field
    summary = Column(Text, nullable=True) # Formula field
    circus_sync = Column(Boolean, default=False, nullable=False)

    # Client_v2 Enum
    client_v2 = Column(
        Enum(
            'Mama Hanh', 'Ms Hanh', 'Circus Group', 'Fully AI', 'Gastrofüsterer', 
            'DAO OS', 'Mama Le Bao', 'Asia Hung', 'Clinic OS', 'Internal', 
            name='project_client_v2_enum', create_type=True
        ),
        nullable=True
    )

    corresponding_id = Column(Text, nullable=True)
    id_pull = Column(Text, nullable=True) # Formula field

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Table arguments for CHECK constraints on array lengths
    __table_args__ = (
        CheckConstraint('client_id IS NULL OR array_length(client_id, 1) = 1', name='projects_client_id_len_check'),
        CheckConstraint('client IS NULL OR array_length(client, 1) = 1', name='projects_client_len_check'),
        CheckConstraint('briefing_id IS NULL OR array_length(briefing_id, 1) = 1', name='projects_briefing_id_len_check'),
        CheckConstraint('briefing IS NULL OR array_length(briefing, 1) = 1', name='projects_briefing_len_check'),
    )

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True) # TEXT null maps to nullable=True

    # Project relation arrays (no limit explicitly in SQL)
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True)

    # Status Enum with default 'Inbox'
    status = Column(
        Enum(
            'Inbox', 'Paused/Later (P3)', 'Next (P2)', 'Now (P1)',
            'In progress', 'Draft Review', 'Waiting for Feedback', 'Done',
            name='task_status_enum', create_type=True
        ),
        default='Inbox',
        nullable=True # As the original type was TEXT, which is nullable
    )
    
    due_date = Column(DateTime(timezone=True), default=None, nullable=True)
    date_completed = Column(DateTime(timezone=True), default=None, nullable=True)

    # Assigned To relation arrays (no limit)
    assigned_to_id = Column(ARRAY(Integer), default=None, nullable=True)
    # assigned_to = Column(ARRAY(Text), default=None, nullable=True)

    command_center = Column(Text, default=None, nullable=True)
    agent = Column(Text, default=None, nullable=True)

    # Milestone array (rollup, so just text array as per your comment)
    milestone = Column(ARRAY(Text), default=None, nullable=True) 

    # Briefing relation arrays (no limit)
    briefing_id = Column(ARRAY(Integer), default=None, nullable=True)
    # briefing = Column(ARRAY(Text), default=None, nullable=True)

    # Asset relation arrays (no limit)
    asset_id = Column(ARRAY(Integer), default=None, nullable=True)
    # asset = Column(ARRAY(Text), default=None, nullable=True)

    tags = Column(Text, default=None, nullable=True) # default null explicitly stated

    # Meeting Transcript relation arrays (no limit)
    meeting_transcript_id = Column(ARRAY(Integer), default=None, nullable=True)
    # meeting_transcript = Column(ARRAY(Text), default=None, nullable=True) 

    notes = Column(Text, default=None, nullable=True) # default null explicitly stated

    exec_summary = Column(Text, default=None, nullable=True)

    completed_today = Column(Text, default=None, nullable=True) # Formula, often maps to TEXT or Boolean in app
    completed_yesterday = Column(Text, default=None, nullable=True) # Formula
    overdue = Column(Text, default=None, nullable=True) # Formula

    annie_summary = Column(Text, default=None, nullable=True)
    
    # Client array (rollup, so just text array as per your comment)
    client = Column(ARRAY(Text), default=None, nullable=True) 
    
    concesa_summary = Column(Text, default=None, nullable=True)

    # Days Enum
    days = Column(
        Enum(
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
            name='task_days_enum', create_type=True
        ),
        nullable=True # No default, so nullable
    )

    due_date_display = Column(Text, nullable=True) # Formula

    emiliano_summary = Column(Text, default=None, nullable=True)

    kat_summary = Column(Text, default=None, nullable=True)

    localization_key = Column(Text, nullable=True) # Formula

    minh_summary = Column(Text, default=None, nullable=True)

    next_due = Column(Text, nullable=True) # Formula

    # Occurences relation arrays (no limit)
    occurences_id = Column(ARRAY(Integer), default=None, nullable=True)
    # occurences = Column(ARRAY(Text), default=None, nullable=True) 

    # Project Priority array (rollup, so just text array as per your comment)
    project_priority = Column(ARRAY(Text), default=None, nullable=True) 

    rangbom_summary = Column(Text, default=None, nullable=True) 

    recur_interval = Column(Integer, default=None, nullable=True)
    
    # Recur Unit Enum
    recur_unit = Column(
        Enum(
            'Day(s)', 'Week(s)', 'Month(s)', 'Month(s) on the First Weekday',
            'Month(s) on the Last Weekday', 'Month(s) on the Last Day', 'Year(s)',
            name='task_recur_unit_enum', create_type=True
        ),
        nullable=True # No default, so nullable
    )
    
    team_summary = Column(Text, default=None, nullable=True)

    unsquared_media_summary = Column(Text, default=None, nullable=True) 

    updates = Column(Text, default=None, nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
class Milestone(Base):
    __tablename__ = 'milestones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True)

    # Status Enum with default 'Not started'
    status = Column(
        Enum(
            'Not started', 'Backlog', 'Paused', 'High Priority',
            'Under Review', 'In progress', 'Shipped', 'Done',
            name='milestone_status_enum', create_type=True
        ),
        default='Not started',
        nullable=True # As original TEXT type is nullable
    )
    
    due_date = Column(DateTime(timezone=True), default=None, nullable=True)

    # Project relation arrays with length constraint
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True)

    # Task relation arrays (no limit)
    task_id = Column(ARRAY(Integer), default=None, nullable=True)
    # task = Column(ARRAY(Text), default=None, nullable=True)

    tags = Column(Text, nullable=True)
    
    # Client relation arrays (no limit)
    client_id = Column(ARRAY(Integer), default=None, nullable=True)
    # client = Column(ARRAY(Text), default=None, nullable=True)

    # Meeting Transcript relation arrays (no limit)
    meeting_transcript_id = Column(ARRAY(Integer), default=None, nullable=True)
    # meeting_transcript = Column(ARRAY(Text), default=None, nullable=True)

    notes = Column(Text, nullable=True)

    project_type = Column(Text, nullable=True) # Formula column

    # Briefing relation arrays with length constraint
    briefing_id = Column(ARRAY(Integer), default=None, nullable=True)
    # briefing = Column(ARRAY(Text), default=None, nullable=True)

    project_owner = Column(Text, nullable=True) # Formula column

    # Asset relation arrays (no limit)
    asset_id = Column(ARRAY(Integer), default=None, nullable=True)
    # asset = Column(ARRAY(Text), default=None, nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Table arguments for CHECK constraints on array lengths
    __table_args__ = (
        CheckConstraint('project_id IS NULL OR array_length(project_id, 1) = 1', name='milestones_project_id_len_check'),
        CheckConstraint('project IS NULL OR array_length(project, 1) = 1', name='milestones_project_len_check'),
        CheckConstraint('briefing_id IS NULL OR array_length(briefing_id, 1) = 1', name='milestones_briefing_id_len_check'),
        CheckConstraint('briefing IS NULL OR array_length(briefing, 1) = 1', name='milestones_briefing_len_check'),
    )
class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True)

    # Type Enum with inline definition
    type = Column(
        Enum(
            'Social Media Post', 'Image', 'Blog', 'Doc', 'Loom Video',
            'YouTube Video', 'Sheets', 'Notion Page',
            name='asset_type_enum', create_type=True
        ),
        default=None,
        nullable=True
    )
    
    link = Column(Text, default=None, nullable=True)

    # Client array (formula, so just text array as per your comment)
    client = Column(ARRAY(Text), default=None, nullable=True) 
    
    display = Column(Text, default=None, nullable=True) # Formula column

    tags = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)

    # Briefing relation arrays (no limit)
    briefing_id = Column(ARRAY(Integer), default=None, nullable=True)
    # briefing = Column(ARRAY(Text), default=None, nullable=True)

    # Milestone relation arrays (no limit)
    milestone_id = Column(ARRAY(Integer), default=None, nullable=True)
    # milestone = Column(ARRAY(Text), default=None, nullable=True) 

    # Project relation arrays (no limit)
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True)

    # Task relation arrays (no limit)
    task_id = Column(ARRAY(Integer), default=None, nullable=True)
    # task = Column(ARRAY(Text), default=None, nullable=True) 

    description = Column(Text, default=None, nullable=True)
    created_date = Column(Date, default=func.current_date()) # Maps to DATE DEFAULT CURRENT_DATE

    circus_sync = Column(Boolean, default=False, nullable=False)

    corresponding_id = Column(Text, nullable=True)
    id_pull = Column(Text, nullable=True) # Formula column

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


class Briefing(Base):
    __tablename__ = 'briefings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True) # TEXT null by default in PG
    
    # Client relation arrays with length constraint
    client_id = Column(ARRAY(Integer), default=None, nullable=True)
    # client = Column(ARRAY(Text), default=None, nullable=True)
    
    # Project relation arrays with length constraint
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True)
    
    objective = Column(Text, nullable=True) # TEXT null by default

    # Outcome (goals) relation arrays (no limit)
    outcome_id = Column(ARRAY(Integer), default=None, nullable=True)
    # outcome = Column(ARRAY(Text), default=None, nullable=True)

    success_criteria = Column(Text, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True) # Calculated from projects

    # Asset relation arrays (no limit)
    asset_id = Column(ARRAY(Integer), default=None, nullable=True)
    # asset = Column(ARRAY(Text), default=None, nullable=True)

    tags = Column(Text, nullable=True)

    # Task relation arrays (no limit)
    task_id = Column(ARRAY(Integer), default=None, nullable=True)
    # task = Column(ARRAY(Text), default=None, nullable=True) 

    # Meeting Transcript relation arrays (no limit)
    meeting_transcript_id = Column(ARRAY(Integer), default=None, nullable=True)
    # meeting_transcript = Column(ARRAY(Text), default=None, nullable=True) 

    notes = Column(Text, nullable=True)

    # Client_type Enum (calculated from clients)
    client_type = Column(
        Enum('Family', 'Privat', 'Internal', 'External', name='briefing_client_type_enum', create_type=True),
        nullable=True # As original TEXT type is nullable
    )
    project_owner = Column(Text, nullable=True) # Calculated from projects

    # Milestone relation arrays (no limit)
    milestone_id = Column(ARRAY(Integer), default=None, nullable=True)
    # milestone = Column(ARRAY(Text), default=None, nullable=True) 

    goals_header = Column(Text, nullable=True) # Calculated from goals

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Table arguments for CHECK constraints on array lengths
    __table_args__ = (
        CheckConstraint('client_id IS NULL OR array_length(client_id, 1) = 1', name='briefings_client_id_len_check'),
        CheckConstraint('client IS NULL OR array_length(client, 1) = 1', name='briefings_client_len_check'),
        CheckConstraint('project_id IS NULL OR array_length(project_id, 1) = 1', name='briefings_project_id_len_check'),
        CheckConstraint('project IS NULL OR array_length(project, 1) = 1', name='briefings_project_len_check'),
    )
# Database setup
class MeetingTranscript(Base):
    __tablename__ = 'meeting_transcripts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=True)
    meeting_date = Column(DateTime(timezone=True), nullable=True) # No default specified in SQL
    transcript_link = Column(Text, default=None, nullable=True)

    # Client relation arrays with length constraint
    client_id = Column(ARRAY(Integer), default=None, nullable=True)
    # client = Column(ARRAY(Text), default=None, nullable=True)
    
    # Project relation arrays with length constraint
    project_id = Column(ARRAY(Integer), default=None, nullable=True)
    # project = Column(ARRAY(Text), default=None, nullable=True)
    
    # Task relation arrays with length constraint
    task_id = Column(ARRAY(Integer), default=None, nullable=True)
    # task = Column(ARRAY(Text), default=None, nullable=True)

    people = Column(Text, default=None, nullable=True) # Based on final SQL

    # Briefing relation arrays (no limit)
    briefing_id = Column(ARRAY(Integer), default=None, nullable=True)
    # briefing = Column(ARRAY(Text), default=None, nullable=True)

    # Milestone relation arrays with length constraint
    milestone_id = Column(ARRAY(Integer), default=None, nullable=True)
    # milestone = Column(ARRAY(Text), default=None, nullable=True) 

    memory_log = Column(Text, default=None, nullable=True) # Based on final SQL

    # Goal relation arrays (no limit)
    goal_id = Column(ARRAY(Integer), default=None, nullable=True)
    # goal = Column(ARRAY(Text), default=None, nullable=True)

    tags = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Table arguments for CHECK constraints on array lengths
    __table_args__ = (
        CheckConstraint('client_id IS NULL OR array_length(client_id, 1) = 1', name='mt_client_id_len_check'),
        CheckConstraint('client IS NULL OR array_length(client, 1) = 1', name='mt_client_len_check'),
        CheckConstraint('project_id IS NULL OR array_length(project_id, 1) = 1', name='mt_project_id_len_check'),
        CheckConstraint('project IS NULL OR array_length(project, 1) = 1', name='mt_project_len_check'),
        CheckConstraint('task_id IS NULL OR array_length(task_id, 1) = 1', name='mt_task_id_len_check'),
        CheckConstraint('task IS NULL OR array_length(task, 1) = 1', name='mt_task_len_check'),
        CheckConstraint('milestone_id IS NULL OR array_length(milestone_id, 1) = 1', name='mt_milestone_id_len_check'),
        CheckConstraint('milestone IS NULL OR array_length(milestone, 1) = 1', name='mt_milestone_len_check'),
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Database setup
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres")

try:
    start_time = time.time()
    engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"}, pool_size=25, max_overflow=25, pool_timeout=30, pool_recycle=3600, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db_init_time = time.time() - start_time
    logger.info(f"✅ Database connection successful! (init_time: {db_init_time:.3f}s)")
    print("✅ Database connection successful!")
except Exception as e:
    logger.error(f"❌ Database error: {e}")
    print(f"❌ Database error: {e}")
    exit(1)
