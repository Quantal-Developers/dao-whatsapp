# main.py
import os
import sys
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
import uuid

# Add the app directory to the path
current_dir = Path(__file__).parent
app_dir = current_dir / "app"
sys.path.insert(0, str(app_dir))

from agents.database_agent.agent import DatabaseAgent

def main():
    """Main application entry point for Minh's personal copilot"""
    print("\n" + "="*60)
    print("🤖 Minh's Personal AI Copilot")
    print("="*60)
    print("\nFeatures:")
    print("- Personal AI assistant for Minh")
    print("- Context awareness and memory")
    print("- Handles both database and general conversation")
    print("- Natural conversation flow")
    print("- Proactive assistance and suggestions")
    print("\nYou can now interact with your personal AI copilot.")
    print("Type 'quit', 'exit', or 'bye' to stop.")
    print("Type '/reset' to clear conversation history.\n")
    
    # Initialize the database agent
    agent = DatabaseAgent()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye! 👋")
                break
            
            if not user_input:
                continue
            
            # Process message through Minh's copilot
            response = agent.process_message(user_input)
            print(f"\nMinh's Copilot: {response}\n")
                
        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
