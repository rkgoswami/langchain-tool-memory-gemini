from flask import Flask, send_from_directory,request
from flask_socketio import SocketIO, join_room, emit
from agent import state
from agent.agent_base import ChatAgent
import os
from dotenv import load_dotenv
import json
from markdown_it import MarkdownIt
load_dotenv()
app = Flask(__name__, static_folder="static")
socketio = SocketIO(
    app,
    path="/ilmagent",
    cors_allowed_origins="*"
)


# Initialize agent


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@socketio.on('join')
def handle_join(data):
    room = data['room']
    token = request.args.get('token')
    # Copy the cookie with name starting with 'IR=' if present
    ir_cookie = f'IR={request.cookies.get("IR", "")}' 
    chat_agent = ChatAgent(cookie=ir_cookie, token=token)
    
    state.clients[room] = chat_agent
    
    join_room(room)

def format_content_as_markdown(content: str) -> str:
    """
    Intelligently formats a string into Markdown.

    - If the content looks like XML, JSON, Python, or SQL, it's wrapped in a
      syntax-highlighted code block.
    - If the content already looks like a Markdown table, it's left as is.
    - Otherwise, it's treated as plain text and returned unchanged.
    """
    # If content is empty or just whitespace, do nothing.
    if not content or not content.strip():
        return ""

    # Trim leading/trailing whitespace for accurate detection.
    trimmed_content = content.strip()
    
    lang = None
    # 1. Detect XML: Starts with < and ends with >.
    if trimmed_content.startswith('<') and trimmed_content.endswith('>'):
        lang = "xml"
        
    # 2. Detect JSON: Starts with { or [ and ends with } or ].
    elif (trimmed_content.startswith('{') and trimmed_content.endswith('}')) or \
         (trimmed_content.startswith('[') and trimmed_content.endswith(']')):
        lang = "json"

    # 3. Detect Python: Contains common keywords.
    elif 'def ' in trimmed_content or 'import ' in trimmed_content or 'class ' in trimmed_content:
        lang = "python"
        
    # 4. Detect SQL: Starts with common SQL commands.
    elif trimmed_content.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'CREATE', 'DELETE')):
        lang = "sql"
        
    # 5. Detect if it's ALREADY a Markdown table. If so, don't touch it.
    # A simple check: contains newlines and pipe characters in multiple lines.
    elif '\n' in trimmed_content and all('|' in line for line in trimmed_content.splitlines() if line.strip()):
        return content # Return as is, it's already Markdown.

    # If a language was detected, wrap the content in a code block
    if lang:
        return f"```{lang}\n{trimmed_content}\n```"
    
    # Otherwise, return the original content as plain text.
    return content

@socketio.on('message')
def handle_message(data):
    room = data['room']
    user_msg = data['message']
    chat_agent = state.clients.get(room)
    session_id = request.sid  # type: ignore # Use the WebSocket session ID as the session ID
    
    # You can now use ir_cookie as needed (e.g., add to context, log, etc.)
    # user_info = {
    #     "session_id": session_id,
    #     "cookie": ir_cookie,
    #     "token": token
    # }
    if not chat_agent:
        print(f"[ERROR] No chat agent found for room {room}.") 
        # create a new agent if not found
        chat_agent = ChatAgent()
        state.clients[room] = chat_agent
        return
   
    # user_info_json = json.dumps(user_info)
    print(f"[DEBUG] Message from room {room}: {user_msg}")
    ai_response = chat_agent.handle_input(user_msg)
    
    # Initialize the parser
    # md = MarkdownIt()

    # Convert the Markdown response to an HTML string
    html_output = format_content_as_markdown(ai_response)

    print(f"[DEBUG] AI response: {html_output}")
    emit('ai_message', {'message': html_output}, room=room)


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=4100, allow_unsafe_werkzeug=True)
