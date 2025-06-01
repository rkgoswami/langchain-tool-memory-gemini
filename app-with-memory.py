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

app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory chat history per session (room)
chat_histories = {}
# conversation_agent = {}
chat_agent = {}
chat_agent = None


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
    # transformed_user_msg = [HumanMessage(content=f"{user_msg}")]
    history.append(user_msg)
    
    
    # Get AI response
    # messages = conversation_agent.invoke(input=f"{user_msg} and also give output in markdown format")
    # ai_response = messages['response']
    
    # Get AI response
    try:
        messages = chat_agent.invoke({"input": user_msg})
        print(f"[DEBUG] AI response: {messages}")
        ai_response = messages["output"]
    except Exception as e:
        ai_response = f"An error occurred: {e}"
    
    
    print(f"[DEBUG] AI response: {ai_response}")
    # Add AI response to history
    #history[-1]['ai'] = ai_response
    chat_histories[room] = history
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
    tools = [multiply_numbers, get_user_details]
    llm_with_tools = llm.bind_tools(tools)
    # pre_built_agent = create_react_agent(llm, tools=tools)
    
    
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    # Initialize the agent
    # chat_agent = create_react_agent(llm, tools=tools, memory=memory, verbose=True, prompt=prompt)
    
    chat_agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
        memory=memory,
        verbose=True,
    )
    # conversation_agent = ConversationChain(
    #     llm=llm, verbose=True, memory=memory
    # )

    socketio.run(app, debug=True)
