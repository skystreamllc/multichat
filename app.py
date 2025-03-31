from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import sqlite3
from openai import OpenAI
import logging
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret!')
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def init_db():
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id TEXT PRIMARY KEY, language TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, message TEXT, language TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Инициализация базы при импорте
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_messages')
def get_messages():
    user_id = request.args.get('user_id')
    target_lang = request.args.get('lang')
    logger.debug(f"Fetching messages for user {user_id} with lang {target_lang}")
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute("SELECT user_id, message, language FROM messages ORDER BY timestamp")
    messages = c.fetchall()
    logger.debug(f"Raw messages from DB: {messages}")
    conn.close()

    translated_messages = []
    for msg_user_id, msg, msg_lang in messages:
        if msg_user_id == user_id:
            translated_msg = msg
        elif msg_lang == target_lang:
            translated_msg = msg
        else:
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": f"Translate the following message into {target_lang}: {msg}"},
                        {"role": "user", "content": msg}
                    ],
                    max_tokens=500
                )
                translated_msg = response.choices[0].message.content
            except Exception as e:
                logger.error(f"Translation error: {e}")
                translated_msg = msg
        translated_messages.append({"user_id": msg_user_id, "message": translated_msg})
    
    logger.debug(f"Returning messages: {translated_messages}")
    return jsonify(translated_messages)

@socketio.on('join')
def on_join(data):
    user_id = data['user_id']
    logger.info(f"User joined: {user_id}")
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, language) VALUES (?, 'en')", (user_id,))
    conn.commit()
    conn.close()

@socketio.on('set_language')
def set_language(data):
    user_id = data['user_id']
    language = data['language']
    logger.info(f"Setting language for {user_id} to {language}")
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
    conn.commit()
    conn.close()

@socketio.on('chat_message')
def handle_message(data):
    user_id = data['user_id']
    message = data['message']
    logger.info(f"Message from {user_id}: {message}")
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    
    c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        user_lang = result[0]
    else:
        user_lang = 'en'
        c.execute("INSERT INTO users (user_id, language) VALUES (?, ?)", (user_id, user_lang))
    
    c.execute("INSERT INTO messages (user_id, message, language) VALUES (?, ?, ?)", (user_id, message, user_lang))
    conn.commit()
    logger.debug(f"Message saved: {user_id}, {message}, {user_lang}")
    conn.close()
    
    logger.debug("Broadcasting message")
    emit('message_broadcast', broadcast=True)

if __name__ == '__main__':
    # Для отладки на localhost
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)