# Minh's Personal AI Copilot

An intelligent personal AI assistant that helps Minh manage his projects, tasks, and data through natural conversation. Built with advanced database capabilities and context awareness.

## 🚀 Features

- **Personal AI Assistant**: Direct interaction with Minh's personal copilot
- **Database Operations**: Full CRUD operations on projects, tasks, clients, users, etc.
- **Context Awareness**: Remembers conversations, preferences, and past interactions
- **Natural Flow**: Maintains conversational continuity
- **Proactive Assistance**: Offers intelligent suggestions and help
- **Web Interface**: Beautiful chat interface with real-time responses

## 🏃‍♂️ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file with:
```
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=your_database_url
```

### 3. Run the Application

#### Option A: Command Line Interface
```bash
python main.py
```

#### Option B: Web Interface
```bash
python server.py
```
Then open http://localhost:8000 in your browser

## 🎯 Usage Examples

### Project Management
- "Create a new project called 'Q1 Planning' with high priority"
- "Show me all my active projects"
- "Update the status of project 5 to 'In Progress'"

### Task Organization
- "Add a task to call investors tomorrow"
- "List all overdue tasks"
- "Mark task 10 as completed"

### Client Management
- "Find clients with 'tech' in their name"
- "Create a new client called 'TechCorp Solutions'"
- "Show me all clients and their projects"

### General Conversation
- "What's the current date and time?"
- "I'm feeling overwhelmed with my workload"
- "Help me plan my week"

## 🏗️ Architecture

```
User Message → Supervisor Agent → Decision:
├── Database Operations → Database Agent → Response
└── General Response → Direct Response → Response
```

### Key Components
- **Supervisor Agent**: Intelligent routing using LangGraph
- **Database Agent**: Specialized for data operations
- **Memory System**: Maintains conversation history
- **Web Interface**: Modern chat UI with real-time updates

## 🔧 Configuration

The system automatically detects when to use database operations vs direct responses based on:
- Keywords and context
- User intent analysis
- Conversation history
- Request complexity

## 📁 File Structure

```
├── main.py              # Main application with enhanced copilot
├── server.py            # Web server for chat interface
├── templates/
│   └── chat.html        # Beautiful chat interface
├── app/
│   └── agents/
│       └── database_agent/  # Database operations
└── requirements.txt     # Dependencies
```

## 🎉 Benefits

- **No Hardcoded Rules**: Uses intelligent LLM decision making
- **Context Awareness**: Remembers past conversations
- **Natural Flow**: Maintains conversational continuity
- **Smart Delegation**: Knows when to use database vs direct responses
- **Easy to Extend**: Add new capabilities easily

## 🚨 Important Notes

- Always asks for confirmation before database operations
- Maintains conversation memory across sessions
- Provides intelligent suggestions based on context
- Handles complex multi-step requests naturally

## 🔄 Migration from Old System

This enhanced version replaces the hardcoded `langgraph_supervisor.py` with:
- Intelligent decision making instead of keyword matching
- Better context handling
- More natural conversation flow
- Easier maintenance and extension

Ready to use! Just run `python main.py` or `python server.py` and start chatting with your enhanced AI copilot! 🚀
