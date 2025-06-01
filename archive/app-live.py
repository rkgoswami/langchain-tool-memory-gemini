from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, join_room, emit
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from memory_agent.agent_with_memory import  add, get_user_details, multiply_numbers
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain.memory import ChatMessageHistory

from langchain.chains.conversation.base import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.agents import initialize_agent, AgentType
from langchain.agents import load_tools

app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

chat_agent = None


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
    print(f"[DEBUG] Received message for room {room}: {user_msg}")
    
    # Get AI response
    try:
        messages = chat_agent.invoke({"input": user_msg})
        print(f"[DEBUG] AI response: {messages}")
        ai_response = messages["output"]
    except Exception as e:
        ai_response = f"An error occurred: {e}"
    
    print(f"[DEBUG] AI response: {ai_response}")
    emit('ai_message', {'message': ai_response}, room=room)

if __name__ == '__main__':
    
    # Set your Gemini API key as an environment variable before running
    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: Set GOOGLE_API_KEY environment variable for Gemini access.")
        
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            """
                You are a helpful assistant that can use tools to answer questions.     
                Format your responses in Markdown.
            """
        ),
        MessagesPlaceholder(variable_name="chat_history"),
    ])
    
    # Augment the LLM with tools
    
    tool_names = ["llm-math"]
    tools = load_tools(tool_names, llm=llm)
    
    tools.append(get_user_details)
    llm_with_tools = llm.bind_tools(tools)
       
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    chat_agent = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, verbose=True, memory=memory)

    socketio.run(app, debug=True)
