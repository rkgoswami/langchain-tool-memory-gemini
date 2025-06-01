from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, join_room, emit
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from agent import agent, get_user_details, multiply_numbers
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, HumanMessage

app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory chat history per session (room)
chat_histories = {}

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# def initAgent():
#     # decalare an agent
#     llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.3)
    
#     # Augment the LLM with tools
#     tools = [multiply_numbers, get_user_details]
#     pre_built_agent = create_react_agent(llm, tools=tools)

@socketio.on('join')
def handle_join(data):
    room = data['room']
    join_room(room)
    if room not in chat_histories:
        chat_histories[room] = []
    emit('history', chat_histories[room], room=room)
    # initAgent()


@socketio.on('message')
def handle_message(data):
    room = data['room']
    user_msg = data['message']
    print(f"[DEBUG] Received message for room {room}: {user_msg}")
    history = chat_histories.get(room, [])
    # Add user message to history
    history.append({'user': user_msg, 'ai': None})
    
    
    # Get AI response
    transfromed_messages = [HumanMessage(content=f"{user_msg}")]
    messages = pre_built_agent.invoke({"messages": transfromed_messages})
    ai_response = messages["messages"][-1].content
    print(f"[DEBUG] AI response: {ai_response}")
    # Add AI response to history
    history[-1]['ai'] = ai_response
    chat_histories[room] = history
    emit('ai_message', {'message': ai_response}, room=room)

if __name__ == '__main__':
    # Set your Gemini API key as an environment variable before running
    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: Set GOOGLE_API_KEY environment variable for Gemini access.")
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", temperature=0.3)
    
    # Augment the LLM with tools
    tools = [multiply_numbers, get_user_details]
    llm_with_tools = llm.bind_tools(tools)
    pre_built_agent = create_react_agent(llm, tools=tools)
    
    socketio.run(app, debug=True)
