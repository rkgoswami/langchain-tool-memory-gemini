from flask import Flask, send_from_directory,request
from flask_socketio import SocketIO, join_room, emit
from agent import state
from agent.agent_base import ChatAgent
import os
from dotenv import load_dotenv
import json
 
load_dotenv()
app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

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
    chat_agent = ChatAgent()
    
    state.clients[room] = chat_agent
    
    join_room(room)


@socketio.on('message')
def handle_message(data):
    room = data['room']
    user_msg = data['message']
    chat_agent = state.clients.get(room)
    if not chat_agent:
        print(f"[ERROR] No chat agent found for room {room}.") 
        # create a new agent if not found
        chat_agent = ChatAgent()
        state.clients[room] = chat_agent
        return
    session_id = request.sid  # type: ignore # Use the WebSocket session ID as the session ID
    token = request.args.get('token')
    # Copy the cookie with name starting with 'IR=' if present
    ir_cookie = f'IR={request.cookies.get("IR", "")}' 
    # You can now use ir_cookie as needed (e.g., add to context, log, etc.)
    user_info = {
        "session_id": session_id,
        "cookie": ir_cookie,
        "token": token
    }
    user_info_json = json.dumps(user_info)
    print(f"[DEBUG] User info: {user_info_json}")
    print(f"[DEBUG] Message from room {room}: {user_msg}")
    ai_response = chat_agent.handle_input(user_msg)

    print(f"[DEBUG] AI response: {ai_response}")
    emit('ai_message', {'message': ai_response}, room=room)


if __name__ == '__main__':
    socketio.run(app, debug=True)
