from flask import Flask, send_from_directory
from flask_socketio import SocketIO, join_room, emit
from agent.agent_base import ChatAgent
import os
from dotenv import load_dotenv
 
load_dotenv()
app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize agent
chat_agent = ChatAgent()


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@socketio.on('join')
def handle_join(data):
    room = data['room']
    join_room(room)


@socketio.on('message')
def handle_message(data):
    room = data['room']
    user_msg = data['message']
    print(f"[DEBUG] Message from room {room}: {user_msg}")

    ai_response = chat_agent.handle_input(user_msg)

    print(f"[DEBUG] AI response: {ai_response}")
    emit('ai_message', {'message': ai_response}, room=room)


if __name__ == '__main__':
    socketio.run(app, debug=True)
