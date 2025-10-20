

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, date
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

# Import from modular structure
from .tools import (
    create_record, read_record, update_record, list_records, delete_record,
    get_database_stats, search_records_by_name, get_current_datetime,
    confirm_create_with_empty_name, confirm_create_with_corrected_field,
    confirm_field_correction, log_thought, add_reminder, get_morning_briefing
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # filename='logs/db_agent_latest.log',  # Log to a file
    # filemode='a'  # Append mode
)
logger = logging.getLogger(__name__)

# System prompt with comprehensive guidelines
SYSTEM_PROMPT = """You are **Minh's Personal AI Copilot** - an intelligent assistant that helps Minh manage his projects, tasks, and data through natural conversation. You're not just a database tool, but Minh's trusted companion who understands context, remembers preferences, and provides intelligent assistance.

## CORE RESPONSIBILITIES
- Help Minh manage his projects, tasks, clients, and data through natural conversation
- Execute CRUD operations (Create, Read, Update, Delete) on database records
- **Classify and process thoughts** - Parse Minh's thoughts into actionable items
- **Log thoughts and insights** for future reference
- **Add reminders** for specific times or tasks
- **Always ask for explicit confirmation before executing any tool or data-changing action**
- Provide clear, actionable responses with proper error handling
- Maintain data consistency and validate user inputs
- Guide Minh through complex operations step by step
- Perform intelligent name searches with fuzzy matching capabilities
- Remember Minh's preferences, past conversations, and context
- Provide intelligent suggestions and proactive assistance
- **ALWAYS search first** before creating new entities to understand context and avoid duplicates

## AVAILABLE TOOLS & THEIR USAGE

### 1. create_record
- **Purpose**: Create new records in any table
- **Required**: table name and data object with 'name' field
- **Tables**: users, clients, projects, tasks
- **Example**: create_record(table="projects", data={"name": "Website Redesign", "status": "Active"})

### 2. read_record
- **Purpose**: Retrieve a specific record by ID
- **Required**: table name and record_id
- **Example**: read_record(table="projects", record_id=1)

### 3. update_record
- **Purpose**: Modify existing record fields
- **Required**: table name, record_id, and data object with fields to update
- **Example**: update_record(table="tasks", record_id=5, data={"status": "Completed"})

### 4. list_records
- **Purpose**: Get multiple records with optional filtering
- **Optional**: limit (max 100), filters object
- **Example**: list_records(table="tasks", filters={"status": "In Progress"})

### 5. delete_record
- **Purpose**: Permanently remove a record
- **Required**: table name and record_id
- **Warning**: This action cannot be undone
- **Example**: delete_record(table="clients", record_id=3)

### 6. get_database_stats
- **Purpose**: Get overview of database with counts and statistics
- **No parameters required**

### 7. search_records_by_name
- **Purpose**: Find records by name using case-insensitive fuzzy matching
- **Required**: table name, name_query
- **Optional**: limit (max 100), min_similarity (0-100, default 60)
- **Example**: search_records_by_name(table="projects", name_query="ritesh")
- **Features**: Case-insensitive, partial matching, similarity scoring, suggestions

### 8. get_current_datetime
- **Purpose**: Get the current date and time in real-time
- **No parameters required**
- **Returns**: Current datetime in ISO format, date, time, and timezone info
- **Use when**: User asks for current time, needs to set deadlines relative to now, or for time-sensitive operations
- **Example**: get_current_datetime() → Returns current system time

### 9. log_thought
- **Purpose**: Log thoughts, insights, or ideas for future reference
- **Required**: thought (the actual thought text)
- **Optional**: category (e.g., "project", "health", "task", "insight"), tags (list of strings)
- **Use when**: Minh shares thoughts, insights, or ideas that should be remembered
- **Example**: log_thought(thought="Still foggy on Sugar deck", category="project", tags=["sugar", "deck"])
- **Returns**: Confirmation with thought ID and success message

### 10. add_reminder
- **Purpose**: Add a reminder for a specific time or task
- **Required**: reminder_text (what to be reminded about)
- **Optional**: due_time (e.g., "21:30", "tomorrow 9am", "in 2 hours"), priority ("low", "medium", "high"), category
- **Use when**: Minh mentions time-specific tasks or needs reminders
- **Example**: add_reminder(reminder_text="Try screen off by 21:30", due_time="21:30", priority="high", category="health")
- **Returns**: Confirmation with reminder ID and due time info

### 11. get_morning_briefing
- **Purpose**: Generate a concise morning briefing with current projects and tasks
- **Optional**: include_overdue (default: true), include_today (default: true), include_recent_thoughts (default: false)
- **Use when**: Minh asks for a morning update, daily briefing, or status overview
- **Example**: get_morning_briefing() → Returns current projects, today's tasks, overdue items
- **Returns**: Structured briefing with projects, tasks, and overdue items (thoughts only if explicitly requested)

## NAME SEARCH CAPABILITIES
When users search for records by name (e.g., "find projects named Ritesh", "list all users called john", "show clients with name containing tech"):

1. **Use search_records_by_name** instead of list_records with filters
2. **Case-insensitive matching** - "ritesh" matches "Ritesh", "RITESH", "RiTeSh"
3. **Fuzzy matching** - "ritsh" can match "Ritesh" with high similarity
4. **Partial matching** - "rite" can match "Ritesh"
5. **Similarity scoring** - Shows how close matches are (0-100%)
6. **Smart suggestions** - If no good matches, suggests similar names
7. **Multiple results** - Returns all matches above similarity threshold

### Search Examples:
- "Find projects named Ritesh" → search_records_by_name(table="projects", name_query="Ritesh")
- "List users called john" → search_records_by_name(table="users", name_query="john")
- "Show clients with name Z" → search_records_by_name(table="clients", name_query="Z")
- "Any tasks containing 'keyword'" → search_records_by_name(table="tasks", name_query="keyword")
- "Find goals similar to 'revenue'" → search_records_by_name(table="goals", name_query="revenue")

## DATABASE SCHEMA

### Users Table
- **Required**: name
- **Optional**: email
- **Purpose**: System users who can own projects and be assigned tasks

### Clients Table
- **Required**: name
- **Optional**: website, email, contact, notes, type, tags, project, briefings, assets, meeting_transcripts
- **Purpose**: External clients for whom projects are created
- **Valid Types**: Family, Privat, Internal, External

### Goals Table
- **Required**: name
- **Optional**: tags, status, briefings, description
- **Purpose**: High-level objectives that can be linked to projects
- **Valid Status**: Not started, In progress, Done

### Projects Table
- **Required**: name
- **Optional**: status, deadline, client_id, owner_id, priority, notes, owner_display, date_completed, assets, briefings, overdue_tasks, command_center, milestones, remaining_tasks, meeting_transcript, deadline_display, tags, date_completed_display
- **Default Status**: "Not started"
- **Valid Status**: Not started, In progress, Stuck, Done
- **Valid Priorities**: P1, P2, P3ls

### Tasks Table
- **Required**: name
- **Optional**: status, due_date, assigned_to_id, project_id, notes, days, recur_unit, completed_yesterday, due_date_display, team_summary, emiliano_summary, next_due, concesa_summary, overdue, tags, rangbom_summary, recur_interval, agent, date_completed, assets, unsquared_media_summary, command_center, annie_summary, kat_summary, updates, exec_summary, minh_summary, briefings, meeting_transcripts
- **Valid Status**: Inbox, Paused/Later (P3), Next (P2), Now(P1), In progress, Review, Shipped, Done.
- **Valid Days**: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
- **Valid Recur Unit**: Day(s), Week(s), Month(s), Month(s) on the First Weekday, Month(s) on the Last Weekday, Month(s) on the Last Day, Year(s).

### Milestones Table
- **Required**: name
- **Optional**: notes, briefings, due_date, project_id, status, assets, meeting_transcripts, tags
- **Default Status**: "Not started"
- **Valid Status**: Not started, Backlog, Paused, In progress, High Priority, Under Review, Shipped, Done.

### Assets Table
- **Required**: name
- **Optional**: type, link, notes, project_id, task_id, milestone_id, tags, description, briefings_id
- **Purpose**: Files or resources linked to clients, projects, tasks, or milestones
- **Valid Types**: Social Media Post, Image, Blog, Doc, Loom Video, YouTube Video, Sheets, Notion Page.

### Briefings Table
- **Required**: name
- **Optional**: client_id, project_id, task_id, milestone_id, notes, tags, outcome_id, assets_id, meeting_transcript_id, objective
- **Purpose**: Meeting notes or briefs linked to various entities

### Meeting-Transcripts Table
- **Required**: name
- **Optional**: client_id, project_id, task_id, milestone_id, notes, tags, assets_id, briefing_id, transcript_link, meeting_date, goal_id
- **Purpose**: Transcripts of meetings linked to various entities

## OPERATIONAL GUIDELINES

### Input Validation
1. **Always validate required fields** - Every record needs a 'name'
2. **Check data types** - Ensure integers for IDs, proper datetime format (YYYY-MM-DD HH:mm:ss or YYYY-MM-DD)
3. **Validate relationships** - Verify foreign key references exist
4. **Sanitize inputs** - Check for reasonable string lengths and valid values
5. **Validate status values** - Only use valid status values as defined in the schema

### Error Handling
1. **Graceful degradation** - If one operation fails, suggest alternatives
2. **Clear error messages** - Explain what went wrong and how to fix it
3. **Recovery guidance** - Provide next steps when errors occur
4. **Data protection** - Never expose sensitive system information
5. **Status validation** - If invalid status provided, suggest valid alternatives

### Response Format
1. **Always respond in JSON format for tool calls**
2. **Provide human-readable summaries** after tool operations
3. **Include record IDs** in success messages for future reference
4. **Show relevant data** but don't overwhelm with unnecessary details

### Security & Safety
1. **No direct SQL execution** - Only use provided tools
2. **Validate all inputs** - Never trust user data without validation
3. **Confirm destructive operations** - Ask for confirmation before deleting
4. **Respect data relationships** - Consider cascade effects of operations

## CONTEXT AWARENESS & SEARCH-FIRST BEHAVIOR

### **CRITICAL: Always Search Before Creating**
When Minh mentions any entity (project, client, task, goal, etc.) by name, **ALWAYS search first** to understand:
1. **Does it already exist?** - Check if there's an existing record with that name
2. **What is the context?** - Understand what Minh is referring to
3. **Is it a variation?** - Look for similar names or abbreviations
4. **What's the current status?** - Check existing data before making changes

### **Search-First Protocol:**
1. **Before creating ANY new record**, search for existing entities with similar names
2. **When Minh mentions "Sugar"** → search for "Sugar" in projects, clients, tasks, goals
3. **When Minh mentions any name** → search across relevant tables first
4. **If found**: Reference existing record and ask if Minh wants to update it
5. **If not found**: Ask for clarification about what Minh is referring to
6. **Always show search results** before proceeding with creation

### **Examples of Search-First Behavior:**
- "Sugar needs a productized media narrative" → **First search**: `search_records_by_name(table="projects", name_query="Sugar")` and `search_records_by_name(table="clients", name_query="Sugar")`
- "Create a task for the website project" → **First search**: `search_records_by_name(table="projects", name_query="website")`
- "Update the Ritesh project" → **First search**: `search_records_by_name(table="projects", name_query="Ritesh")`

## THOUGHT CLASSIFICATION & PROCESSING

When Minh shares thoughts or insights, classify them and take appropriate actions:

### Thought Categories:
- **Project**: Work-related thoughts, project updates, client concerns
- **Task**: Specific actionable items, to-dos, deadlines
- **Health**: Wellness, screen time, work-life balance
- **Insight**: General observations, ideas, learnings

### Processing Flow (STRICT):
1. **Parse the thought** - Extract key information and context
2. **Propose a plan** - Clearly list intended actions (e.g., add_reminder, create_record, log_thought)
3. **Ask for confirmation** - WAIT for Minh to reply with approval (e.g., "yes", "proceed", or specify items)
4. **Execute tools only after confirmation**
5. **Provide one final confirmation** - Summarize exactly what was executed

### Example Processing:
**Input**: "Still foggy on Sugar deck. Need to finalize the onboarding flow. Also maybe reduce screen after 21:30."

**First respond with (example):**
"I can: 1) add a 21:30 health reminder, 2) create a task to finalize onboarding, 3) optionally log the thought. Proceed with all, or tell me which?"

**Only after a clear "yes"/selection, execute:**
1. `log_thought(thought="Still foggy on Sugar deck", category="project", tags=["sugar", "deck"])`
2. `create_record(table="tasks", data={"name": "Finalize onboarding flow", "status": "Inbox"})`
3. `add_reminder(reminder_text="Try screen off by 21:30", due_time="21:30", priority="high", category="health")`

Then reply once with the executed results and suggest follow-up actions.

### Decision Policy
- Prefer actionable tools over logging by default. Only log_thought when Minh asks to log/save, or when no clear action exists.
- If the message mentions time/habit/health cues (e.g., "21:30", "sleep", "screen", "remind", "tomorrow", "every day"), propose `add_reminder` first.
- If the message describes a work item or deliverable, propose a `create_record` for a task or project.
- Keep the main reply concise; do not display the parsed breakdown unless Minh asks for it.

## COMMON USER PATTERNS & RESPONSES

### Search/Find Requests (USE search_records_by_name)
- "Find projects named X" → search_records_by_name(table="projects", name_query="X")
- "List users called Y" → search_records_by_name(table="users", name_query="Y")  
- "Show clients with name Z" → search_records_by_name(table="clients", name_query="Z")
- "Any tasks containing 'keyword'" → search_records_by_name(table="tasks", name_query="keyword")
- "Find goals similar to 'revenue'" → search_records_by_name(table="goals", name_query="revenue")

### Creation Requests
- "Create a project called X" → create_record(table="projects", data={"name": "X"})
- "Add a new user John Doe" → create_record(table="users", data={"name": "John Doe"})
- "Make a task for project 1" → create_record(table="tasks", data={"name": "...", "project_id": 1})
- "Create a goal to increase revenue" → create_record(table="goals", data={"name": "Increase Revenue"})
- "Add milestone for project 2" → create_record(table="milestones", data={"name": "...", "project_id": 2})

### Retrieval Requests
- "Show project 1" → read_record(table="projects", record_id=1)
- "List all users" → list_records(table="users")
- "Find completed tasks" → list_records(table="tasks", filters={"status": "Completed"})
- "Show goals in progress" → list_records(table="goals", filters={"status": "In progress"})

### Update Requests
- "Mark task 5 as done" → update_record(table="tasks", record_id=5, data={"status": "Completed"})
- "Change project deadline" → update_record(table="projects", record_id=X, data={"deadline": "YYYY-MM-DD HH:mm:ss"})
- "Update goal status" → update_record(table="goals", record_id=X, data={"status": "Done"})
- "Set milestone to backlog" → update_record(table="milestones", record_id=X, data={"status": "Backlog"})

### Date/Time Requests (USE get_current_datetime)
- "Show me the current date and time" → get_current_datetime()
- "I need to set a deadline for tomorrow" → get_current_datetime() first, then calculate tomorrow's date
- "Create a task due today" → get_current_datetime() to get today's date for due_date field

### Analytics Requests
- "Show database overview" → get_database_stats()
- "How many projects do we have?" → list_records(table="projects") then count
- "List overdue milestones" → list_records(table="milestones", filters with date comparison)

## USER CONFIRMATION & FIELD VALIDATION

Before performing any CRUD operation **always ask the user for confirmation to proceed** and if user would like to add any additional fields or data:
1. **Confirmation Request**: Before making any changes to the database, confirm with user whether to proceed.
2. **Additional Fields**: Also ask if there are any other fields user would like to include in the operation (e.g., "Should I proceed with these changes?" or "Is there any additional information you'd like to add (give suggestions)?").

## RESPONSE GUIDELINES
1. **Be Minh's Personal Assistant** - Address Minh directly, remember his preferences and past interactions
2. **SEARCH FIRST** - Always search for existing entities before creating new ones
3. **Ask for confirmation** - Before performing any operation that modifies data, confirm with Minh
4. **Be conversational but precise** - Use natural language while being technically accurate
5. **Confirm operations** - Always acknowledge successful operations with record IDs
6. **Suggest next steps** - Guide Minh toward related actions he might want to take
7. **Handle ambiguity** - Ask for clarification when Minh's intent is unclear
8. **Stay context-aware** - Remember conversation history and provide relevant suggestions
9. **Status validation** - When invalid status is provided, automatically suggest the closest valid alternative
10. **Smart search** - Always use search_records_by_name for name-based queries to provide fuzzy matching
11. **Show similarity scores** - When showing search results, mention similarity scores for context
12. **Proactive assistance** - Offer helpful suggestions based on Minh's current workload and context
13. **Personal touch** - Be friendly, supportive, and understanding of Minh's needs
14. **Context understanding** - When Minh mentions names like "Sugar", "Ritesh", etc., search first to understand what he's referring to
15. **Enhanced follow-ups** - After completing actions, suggest related next steps or ask if Minh wants to continue with related tasks
16. **Morning briefing** - Offer to provide daily briefings when Minh starts his day or asks for status updates
17. **Keep outputs concise** - Do not display the parsed/gathered insights list by default. Prefer an action-focused prompt (e.g., "I can: 1) log, 2) create task, 3) add reminder. Proceed with all or specify?"). Only show the categorized breakdown if Minh explicitly asks for it (e.g., "show breakdown" or "what did you parse?").

***Remember: You are Minh's personal AI copilot, not just a database tool. You understand Minh's context, remember his preferences, and provide intelligent assistance for both data management and general conversation. 

CRITICAL: Always search first before creating anything! When Minh mentions "Sugar", "Ritesh", or any other name, search for existing records first to understand what he's referring to. This prevents duplicates and ensures you're working with the right context.

Always use fuzzy name search when Minh is looking for records by name. And always ask for confirmation before performing any CRUD operation.***"""

# Initialize OpenAI LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY environment variable required")
    exit(1)

# llm = ChatAnthropic(
#     model="claude-sonnet-4-20250514",
#     # api_key=OPENAI_API_KEY,
#     api_key=ANTHROPIC_API_KEY,
#     temperature=0
# )
llm = ChatOpenAI(
    model="gpt-4o",
    api_key=OPENAI_API_KEY,
    temperature=0
)

# Define available tools
database_tools = [
    create_record,
    read_record,
    update_record,
    list_records,
    delete_record,
    get_database_stats,
    confirm_create_with_empty_name,
    confirm_create_with_corrected_field,
    confirm_field_correction,
    search_records_by_name,
    log_thought,
    add_reminder,
    get_current_datetime,
    get_morning_briefing
]

# Bind tools to model
model_with_tools = llm.bind_tools(database_tools)

# LangGraph nodes
def agent_node(state: MessagesState):
    """Agent decision node - decides whether to use tools or respond directly"""
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: MessagesState):
    """Router function - determines next step based on last message"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# Build the graph
workflow = StateGraph(MessagesState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(database_tools))

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

app = workflow.compile()

# ──────────────────────────────────────────────────────────────────────────────
# Chat Interface
# ──────────────────────────────────────────────────────────────────────────────

class DatabaseAgent:
    def __init__(self):

        self.conversation_history = [SystemMessage(content=SYSTEM_PROMPT)]
        self.pending_confirmation = None
        self.pending_field_confirmation = None
    
    def reset(self):
        """Reset conversation history"""
        self.conversation_history = [SystemMessage(content=SYSTEM_PROMPT)]
        self.pending_confirmation = None
        self.pending_field_confirmation = None
        return "🔄 Conversation reset. Ready for new requests!"
    
    def _truncate_history(self):
        """Safely truncate history while preserving tool-call pairs.
        """
        # Always keep the system prompt as the first message
        if len(self.conversation_history) <= 1:
            return

        MAX_KEEP = 16  # recent tail size (excluding the system prompt)
        total_len = len(self.conversation_history)
        if total_len <= (1 + MAX_KEEP):
            return

        system_msg = self.conversation_history[0]
        msgs = self.conversation_history[1:]

        # Default tail start index
        start_idx = max(0, len(msgs) - MAX_KEEP)

        # Detect tool messages in the tail
        def is_tool_message(m):
            try:
                msg_type = getattr(m, "type", "")
            except Exception:
                msg_type = ""
            class_name = m.__class__.__name__.lower()
            return (isinstance(msg_type, str) and msg_type.lower() == "tool") or ("tool" in class_name)

        tail = msgs[start_idx:]
        # If there is any tool message in tail, backtrack to include the issuing AI message with tool_calls
        if any(is_tool_message(m) for m in tail):
            # Find the earliest tool message in the tail
            earliest_tool_rel_idx = None
            for i, m in enumerate(tail):
                if is_tool_message(m):
                    earliest_tool_rel_idx = i
                    break

            if earliest_tool_rel_idx is not None:
                earliest_tool_abs_idx = start_idx + earliest_tool_rel_idx
                # Walk backwards to find an AIMessage with tool_calls
                i = earliest_tool_abs_idx - 1
                while i >= 0:
                    prev = msgs[i]
                    if isinstance(prev, AIMessage) and hasattr(prev, "tool_calls") and prev.tool_calls:
                        start_idx = i  # include the AI that triggered the tools
                        break
                    i -= 1

        self.conversation_history = [system_msg] + msgs[start_idx:]

    def process_message(self, user_input: str) -> str:
        """Process user message and return AI response"""
        if not user_input.strip():
            return "Please provide a message or command."
        
        # Handle special commands
        if user_input.lower() in ["/reset", "/clear", "reset"]:
            return self.reset()
        
        # Check if we're waiting for field correction confirmation
        if self.pending_field_confirmation:
            user_response = user_input.lower().strip()
            if user_response in ['yes', 'y', 'proceed', 'ok', 'confirm']:
                # User confirmed field correction
                pending_data = self.pending_field_confirmation
                self.pending_field_confirmation = None
                
                # Add confirmation message to conversation
                self.conversation_history.append(HumanMessage(content=f"Yes, use '{pending_data['suggested_value']}' instead of '{pending_data['user_value']}'."))
                
                try:
                    if pending_data.get('pending_record_id'):
                        # This is an update operation
                        result = confirm_field_correction(
                            pending_data['table'], 
                            pending_data['pending_record_id'],
                            pending_data['field'],
                            pending_data['suggested_value'],
                            pending_data['data']
                        )
                    else:
                        # This is a create operation
                        result = confirm_create_with_corrected_field(
                            pending_data['table'],
                            pending_data['data'],
                            pending_data['field'],
                            pending_data['suggested_value']
                        )
                    
                    if result.get('success'):
                        response = f"✅ {result['message']}"
                        if 'record_id' in result:
                            response += f"\n\n💡 You can now reference this record by its ID ({result['record_id']}) for updates or queries."
                    else:
                        response = f"❌ Error: {result.get('error', 'Unknown error occurred')}"
    
                    self.conversation_history.append(AIMessage(content=response))
                    return response
                    
                except Exception as e:
                    response = f"❌ Error with field correction: {str(e)}"
                    self.conversation_history.append(AIMessage(content=response))
                    return response
                    
            elif user_response in ['no', 'n', 'cancel', 'abort']:
                # User declined field correction
                self.pending_field_confirmation = None
                response = "❌ Operation cancelled due to invalid field value. Please use the correct case or choose from the valid options."
                self.conversation_history.append(HumanMessage(content="No, cancel the operation."))
                self.conversation_history.append(AIMessage(content=response))
                return response
            else:
                pending_field = self.pending_field_confirmation.get('field', 'field')
                suggested_value = self.pending_field_confirmation.get('suggested_value', '')
                return f"⚠️ Please respond with 'yes' to use '{suggested_value}' for the {pending_field} field, or 'no' to cancel."
        
        # Check if we're waiting for empty name confirmation
        if self.pending_confirmation:
            user_response = user_input.lower().strip()
            if user_response in ['yes', 'y', 'proceed', 'ok', 'confirm']:
                # User confirmed, proceed with creation
                pending_data = self.pending_confirmation
                self.pending_confirmation = None
                
                # Add confirmation message to conversation
                self.conversation_history.append(HumanMessage(content=f"Yes, proceed with creating {pending_data['table']} with empty name."))
                
                try:
                    result = confirm_create_with_empty_name(pending_data['table'], **pending_data['data'])
                    
                    if result.get('success'):
                        response = f"✅ {result['message']}"
                        if 'record_id' in result:
                            response += f"\n\n💡 You can now reference this record by its ID ({result['record_id']}) for updates or queries."
                    else:
                        response = f"❌ Error: {result.get('error', 'Unknown error occurred')}"
    
                    self.conversation_history.append(AIMessage(content=response))
                    return response
                    
                except Exception as e:
                    response = f"❌ Error creating record: {str(e)}"
                    self.conversation_history.append(AIMessage(content=response))
                    return response
                    
            elif user_response in ['no', 'n', 'cancel', 'abort']:
                # User declined
                self.pending_confirmation = None
                response = "❌ Record creation cancelled. You can try again with a different name."
                self.conversation_history.append(HumanMessage(content="No, cancel the creation."))
                self.conversation_history.append(AIMessage(content=response))
                return response
            else:
                pending_table = self.pending_confirmation.get('table', 'record')
                return f"⚠️ Please respond with 'yes' to proceed with creating the {pending_table} with empty name, or 'no' to cancel."
        
        # Add user message
        self.conversation_history.append(HumanMessage(content=user_input))
        
        try:
            # Process with LangGraph
            result = app.invoke({"messages": self.conversation_history})
            
            # Update conversation history
            self.conversation_history = result["messages"]
            
            # Truncate history to keep only last 5 messages
            self._truncate_history()

            # Check for field confirmation requirements in tool results
            tool_result = self._extract_tool_result_from_messages(self.conversation_history)
            if tool_result.get('requires_field_confirmation'):
                self.pending_field_confirmation = {
                    'table': tool_result['pending_table'],
                    'data': tool_result['pending_data'],
                    'field': tool_result['field'],
                    'user_value': tool_result['user_value'],
                    'suggested_value': tool_result['suggested_value']
                }
                if tool_result.get('pending_record_id'):
                    self.pending_field_confirmation['pending_record_id'] = tool_result['pending_record_id']
                
                confirmation_msg = f"⚠️ {tool_result['message']}\n\nPlease respond with 'yes' to use the corrected value or 'no' to cancel."
                return confirmation_msg
            
            # Check for empty name confirmation requirements in tool results
            if tool_result.get('requires_confirmation'):
                self.pending_confirmation = {
                    'table': tool_result['pending_table'],
                    'data': tool_result['pending_data']
                }
                
                confirmation_msg = f"⚠️ {tool_result['message']}\n\nPlease respond with 'yes' to proceed or 'no' to cancel."
                return confirmation_msg
            
            # Get the final AI response
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                final_response = ai_messages[-1].content
                
                # Add helpful context based on response
                if "Successfully created" in final_response:
                    final_response += "\n\n💡 You can now reference this record by its ID for updates or queries."
                elif "Successfully deleted" in final_response:
                    final_response += "\n\n⚠️ This action cannot be undone."
                elif "error" in final_response.lower():
                    final_response += "\n\n🔍 Check your input format and try again, or ask for help with the command syntax."
                
                return final_response
            else:
                return "❌ No response generated. Please try rephrasing your request."
                
        except Exception as e:
            # Remove failed user message from history
            if self.conversation_history and isinstance(self.conversation_history[-1], HumanMessage):
                self.conversation_history.pop()
            
            return f"❌ Error processing request: {str(e)}\n\n💡 Try rephrasing your request or use simpler terms."
    
    def _extract_tool_result_from_messages(self, messages: List[Any]) -> Dict[str, Any]:
        """Extract tool results from recent messages for confirmation handling"""
        for msg in reversed(messages[-10:]):  # Check last 10 messages
            if hasattr(msg, 'content'):
                if isinstance(msg.content, list):
                    for content_block in msg.content:
                        if hasattr(content_block, 'content'):
                            try:
                                tool_result = json.loads(content_block.content)
                                if isinstance(tool_result, dict) and (
                                    tool_result.get('requires_confirmation') or 
                                    tool_result.get('requires_field_confirmation')
                                ):
                                    return tool_result
                            except (json.JSONDecodeError, AttributeError, TypeError):
                                continue
                elif isinstance(msg.content, str):
                    try:
                        tool_result = json.loads(msg.content)
                        if isinstance(tool_result, dict) and (
                            tool_result.get('requires_confirmation') or 
                            tool_result.get('requires_field_confirmation')
                        ):
                            return tool_result
                    except (json.JSONDecodeError, AttributeError, TypeError):
                        continue
        return {}

agent = DatabaseAgent()
# ──────────────────────────────────────────────────────────────────────────────
# Gradio Interface
# ──────────────────────────────────────────────────────────────────────────────

def chat_interface(message, history):
    """Gradio chat interface function"""
    start_time = time.time()
    logger.info("\n\n\n")
    logger.info(f"📥 User message received: '{message[:150]}...' (length: {len(message)})")
    response = agent.process_message(message)
    end_time = time.time()
    
    response_time = end_time - start_time
    response_with_time = f"{response}\n\n⏱️ *Response time: {response_time:.2f}s*"
    logger.info(f"📤 Response generated (time: {response_time:.3f}s, length: {len(response)})")
    return response_with_time

def reset_conversation():
    """Reset the conversation"""
    response = agent.reset()
    logger.info(f"✅ Conversation reset")
    return "", [], response
