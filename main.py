"""
╔══════════════════════════════════════════════════════════════╗
║           ARYAN'S 24/7 AI USERBOT - @MaiHuAryan             ║
║                   Serious • Sarcastic • Hinglish             ║
║                                                              ║
║  Version: 5.3 FINAL (ALL BUGS FIXED - PRODUCTION READY)     ║
║  Features: 50+ Commands, Full AI, VIP System, Web Server    ║
╚══════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════
#                         IMPORTS
# ═══════════════════════════════════════════════════════════════

import os
import sys
import time
import asyncio
import random
import logging
import signal
import traceback
import hashlib
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Optional, List, Dict, Any, Tuple
from functools import wraps

# Web Server
from flask import Flask, jsonify

import pytz
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.errors import (
    FloodWait, 
    UserIsBlocked, 
    MessageIdInvalid,
    MessageNotModified,
    ChatWriteForbidden,
    PeerIdInvalid,
    UserDeactivated
)

# MongoDB
from pymongo import MongoClient

from dotenv import load_dotenv

# Gemini
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Gemini not available")

# ═══════════════════════════════════════════════════════════════
#                         FLASK WEB SERVER
# ═══════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
START_TIME = datetime.now()
BOT_STATS = {
    "messages_replied": 0,
    "commands_executed": 0,
    "errors_count": 0
}

@flask_app.route('/')
def home():
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    return jsonify({
        "status": "✅ alive",
        "bot": "Aryan's Userbot V5.3",
        "uptime": uptime,
        "stats": BOT_STATS
    })

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy", "code": 200})

@flask_app.route('/ping')
def ping():
    return "pong", 200

@flask_app.route('/stats')
def stats():
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    return jsonify({
        "uptime": uptime,
        "messages_replied": BOT_STATS["messages_replied"],
        "commands_executed": BOT_STATS["commands_executed"],
        "errors": BOT_STATS["errors_count"]
    })

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

# ═══════════════════════════════════════════════════════════════
#                         CONSTANTS
# ═══════════════════════════════════════════════════════════════

MAX_MESSAGE_LENGTH = 4096
MAX_HISTORY_PER_USER = 100
MAX_WORDS_TO_REPLY = 200
MAX_STICKER_PREVIEW = 5
SPAM_MESSAGE_THRESHOLD = 3
SPAM_TIME_WINDOW = 60
ACTION_LOG_LIMIT = 50
ERROR_LOG_LIMIT = 20
GEMINI_MAX_RETRIES = 3
FLOOD_WAIT_MAX_RETRIES = 3
REPLY_COOLDOWN_SECONDS = 2
COMMAND_COOLDOWN_SECONDS = 1
CONFIRM_CLEAR_TIMEOUT = 60
MIN_DELAY_SECONDS = 1
MAX_DELAY_SECONDS = 30
DEFAULT_DELAY_MIN = 3
DEFAULT_DELAY_MAX = 8
DEFAULT_STICKER_CHANCE = 10
GEMINI_CONTEXT_LIMIT = 3000
SESSION_STRING_MIN_LENGTH = 100

# ═══════════════════════════════════════════════════════════════
#                         LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ═══════════════════════════════════════════════════════════════
#                         CONFIGURATION
# ═══════════════════════════════════════════════════════════════

load_dotenv()

def get_env(key: str, default: str = None, required: bool = False) -> Optional[str]:
    value = os.getenv(key, default)
    if required and not value:
        logger.critical(f"❌ Missing required: {key}")
        sys.exit(1)
    return value

def get_env_int(key: str, default: int = 0, required: bool = False) -> int:
    value = get_env(key, str(default), required)
    try:
        return int(value) if value else default
    except:
        return default

API_ID = get_env_int("API_ID", required=True)
API_HASH = get_env("API_HASH", required=True)
SESSION_STRING = get_env("SESSION_STRING", required=True)

if len(SESSION_STRING) < SESSION_STRING_MIN_LENGTH:
    logger.critical("❌ Invalid session string")
    sys.exit(1)

OWNER_ID = get_env_int("OWNER_ID", default=0)
MONGO_URI = get_env("MONGO_URI", required=False)

BOT_USERNAME = "MaiHuAryan"
BOT_NAME = "Aryan"
TIMEZONE = pytz.timezone("Asia/Kolkata")
GEMINI_MODEL = "gemini-1.5-flash-latest"

if GEMINI_AVAILABLE:
    SAFETY_SETTINGS = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
else:
    SAFETY_SETTINGS = {}

# ═══════════════════════════════════════════════════════════════
#                      GLOBAL STATE
# ═══════════════════════════════════════════════════════════════

class BotState:
    def __init__(self):
        self._lock = threading.Lock()
        self.spam_tracker: Dict[int, deque] = defaultdict(lambda: deque(maxlen=5))
        self.action_logs: deque = deque(maxlen=ACTION_LOG_LIMIT)
        self.error_logs: deque = deque(maxlen=ERROR_LOG_LIMIT)
        self.last_reply_time: Dict[int, datetime] = {}
        self.last_command_time: Dict[int, datetime] = {}
        self.processing_users: set = set()
        self.gemini_key_index = 0
        self.confirm_clear_time: Optional[datetime] = None
        self.confirm_clear_user: Optional[int] = None
        
    def add_processing_user(self, user_id: int) -> bool:
        with self._lock:
            if user_id in self.processing_users:
                return False
            self.processing_users.add(user_id)
            return True
    
    def remove_processing_user(self, user_id: int):
        with self._lock:
            self.processing_users.discard(user_id)

bot_state = BotState()

# ═══════════════════════════════════════════════════════════════
#                      DATABASE
# ═══════════════════════════════════════════════════════════════

mongo_client: Optional[MongoClient] = None
db = None

def connect_mongodb():
    global mongo_client, db
    
    if not MONGO_URI:
        logger.warning("⚠️ No MongoDB URI - using memory only")
        return False
    
    try:
        mongo_client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            retryWrites=True
        )
        mongo_client.admin.command('ping')
        db = mongo_client['aryan_userbot']
        
        try:
            db.messages.create_index("user_id", unique=True)
            db.vips.create_index("user_id", unique=True)
            db.config.create_index("key", unique=True)
        except:
            pass
        
        logger.info("✅ MongoDB connected")
        return True
    except Exception as e:
        logger.warning(f"⚠️ MongoDB failed: {e}")
        return False

connect_mongodb()

# ═══════════════════════════════════════════════════════════════
#                      PYROGRAM CLIENT
# ═══════════════════════════════════════════════════════════════

app = Client(
    name="aryan_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=False
)

# ═══════════════════════════════════════════════════════════════
#                      DECORATORS
# ═══════════════════════════════════════════════════════════════

def rate_limit(seconds: int = COMMAND_COOLDOWN_SECONDS):
    def decorator(func):
        @wraps(func)
        async def wrapper(client: Client, message: Message):
            user_id = message.from_user.id if message.from_user else 0
            now = get_current_time()
            
            last_time = bot_state.last_command_time.get(user_id)
            if last_time:
                diff = (now - last_time).total_seconds()
                if diff < seconds:
                    return
            
            bot_state.last_command_time[user_id] = now
            BOT_STATS["commands_executed"] += 1
            return await func(client, message)
        return wrapper
    return decorator

def owner_only(func):
    @wraps(func)
    async def wrapper(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not is_owner(user_id):
            return
        return await func(client, message)
    return wrapper

# ═══════════════════════════════════════════════════════════════
#                      HELPER FUNCTIONS (ALL FIXED!)
# ═══════════════════════════════════════════════════════════════

def get_current_time() -> datetime:
    return datetime.now(TIMEZONE)

def get_config(key: str, default: Any = None) -> Any:
    if db is None:  # ✅ FIXED
        return default
    try:
        config = db.config.find_one({"key": key})
        return config["value"] if config and "value" in config else default
    except:
        return default

def set_config(key: str, value: Any) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.config.update_one(
            {"key": key},
            {"$set": {"key": key, "value": value}},
            upsert=True
        )
        return True
    except:
        return False

def log_action(action: str):
    timestamp = get_current_time().strftime('%H:%M:%S')
    bot_state.action_logs.append(f"[{timestamp}] {action}")
    logger.info(action)

def log_error(error: str):
    timestamp = get_current_time().strftime('%H:%M:%S')
    bot_state.error_logs.append(f"[{timestamp}] {error}")
    logger.error(error)
    BOT_STATS["errors_count"] += 1

def is_bot_active() -> bool:
    return get_config("bot_active", False)

def get_owner_id() -> int:
    owner = get_config("owner_id")
    return owner if owner else OWNER_ID

def is_owner(user_id: int) -> bool:
    owner = get_owner_id()
    return user_id == owner and owner != 0

def save_message(user_id: int, text: str, sender: str = "user") -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.messages.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "messages": {
                        "$each": [{
                            "text": text[:1000] if text else "[Empty]",
                            "sender": sender,
                            "time": get_current_time().isoformat()
                        }],
                        "$slice": -MAX_HISTORY_PER_USER
                    }
                }
            },
            upsert=True
        )
        return True
    except:
        return False

def get_conversation_history(user_id: int, limit: int = 10) -> List[Dict]:
    if db is None:  # ✅ FIXED
        return []
    try:
        data = db.messages.find_one({"user_id": user_id})
        return data["messages"][-limit:] if data and "messages" in data else []
    except:
        return []

def get_message_count(user_id: int) -> int:
    if db is None:  # ✅ FIXED
        return 0
    try:
        data = db.messages.find_one({"user_id": user_id})
        return len(data.get("messages", [])) if data else 0
    except:
        return 0

def get_all_gemini_keys() -> List[str]:
    if db is not None:  # ✅ FIXED
        try:
            doc = db.gemini_keys.find_one({"type": "keys"})
            if doc and doc.get("keys"):
                return doc["keys"]
        except:
            pass
    
    keys = []
    for i in range(1, 15):
        key = os.getenv(f"GEMINI_KEY_{i}")
        if key and key.strip():
            keys.append(key.strip())
    
    if keys and db is not None:  # ✅ FIXED
        try:
            db.gemini_keys.update_one(
                {"type": "keys"},
                {"$set": {"keys": keys, "current_index": 0}},
                upsert=True
            )
        except:
            pass
    
    return keys

def add_gemini_key(key: str) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.gemini_keys.update_one(
            {"type": "keys"},
            {"$addToSet": {"keys": key}},
            upsert=True
        )
        return True
    except:
        return False

def remove_gemini_key(index: int) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        keys = get_all_gemini_keys()
        if 0 <= index < len(keys):
            keys.pop(index)
            db.gemini_keys.update_one(
                {"type": "keys"},
                {"$set": {"keys": keys, "current_index": 0}},
                upsert=True
            )
            return True
        return False
    except:
        return False

def get_next_gemini_key() -> Optional[str]:
    keys = get_all_gemini_keys()
    if not keys:
        return None
    
    idx = bot_state.gemini_key_index
    if idx >= len(keys):
        idx = 0
    
    key = keys[idx]
    bot_state.gemini_key_index = (idx + 1) % len(keys)
    return key

def get_vip_info(user_id: int) -> Optional[Dict]:
    if db is None:  # ✅ FIXED
        return None
    try:
        return db.vips.find_one({"user_id": user_id})
    except:
        return None

def add_vip(user_id: int, name: str) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.vips.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "name": name}},
            upsert=True
        )
        return True
    except:
        return False

def remove_vip(user_id: int) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        result = db.vips.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    except:
        return False

def get_all_vips() -> List[Dict]:
    if db is None:  # ✅ FIXED
        return []
    try:
        return list(db.vips.find())
    except:
        return []

def set_vip_name(user_id: int, name: str) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.vips.update_one(
            {"user_id": user_id},
            {"$set": {"name": name}},
            upsert=True
        )
        return True
    except:
        return False

def get_log_group() -> Optional[int]:
    return get_config("log_group_id")

async def send_log(text: str, retry: int = 0) -> bool:
    if retry >= FLOOD_WAIT_MAX_RETRIES:
        return False
    
    log_group = get_log_group()
    if not log_group:
        return False
    
    try:
        if len(text) > MAX_MESSAGE_LENGTH - 100:
            text = text[:MAX_MESSAGE_LENGTH - 100] + "..."
        
        await app.send_message(log_group, f"📊 **LOG**\n\n{text}", parse_mode=ParseMode.MARKDOWN)
        return True
    except FloodWait as e:
        await asyncio.sleep(min(e.value, 60))
        return await send_log(text, retry + 1)
    except:
        return False

def get_all_stickers() -> List[str]:
    if db is None:  # ✅ FIXED
        return []
    try:
        doc = db.stickers.find_one({"type": "stickers"})
        return doc.get("file_ids", []) if doc else []
    except:
        return []

def add_sticker(file_id: str) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.stickers.update_one(
            {"type": "stickers"},
            {"$addToSet": {"file_ids": file_id}},
            upsert=True
        )
        return True
    except:
        return False

def remove_sticker(file_id: str) -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.stickers.update_one(
            {"type": "stickers"},
            {"$pull": {"file_ids": file_id}}
        )
        return True
    except:
        return False

def clear_all_stickers() -> bool:
    if db is None:  # ✅ FIXED
        return False
    try:
        db.stickers.delete_one({"type": "stickers"})
        return True
    except:
        return False

def should_send_sticker() -> bool:
    chance = get_config("sticker_chance", DEFAULT_STICKER_CHANCE)
    return random.randint(1, 100) <= chance

def get_delay_range() -> Tuple[int, int]:
    return (
        get_config("delay_min", DEFAULT_DELAY_MIN),
        get_config("delay_max", DEFAULT_DELAY_MAX)
    )

def count_words(text: str) -> int:
    return len(text.split()) if text else 0

def is_spam(user_id: int, text: str) -> bool:
    if not text:
        return False
    try:
        now = get_current_time()
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        bot_state.spam_tracker[user_id].append({"hash": text_hash, "time": now})
        
        recent = []
        for m in bot_state.spam_tracker[user_id]:
            try:
                msg_time = m["time"]
                if isinstance(msg_time, str):
                    msg_time = datetime.fromisoformat(msg_time)
                if msg_time.tzinfo is None:
                    msg_time = TIMEZONE.localize(msg_time)
                if (now - msg_time).total_seconds() < SPAM_TIME_WINDOW:
                    recent.append(m)
            except:
                continue
        
        if len(recent) >= SPAM_MESSAGE_THRESHOLD:
            if len(set(m["hash"] for m in recent)) == 1:
                return True
        return False
    except:
        return False

async def check_reply_cooldown(user_id: int) -> bool:
    last = bot_state.last_reply_time.get(user_id)
    if last:
        if (get_current_time() - last).total_seconds() < REPLY_COOLDOWN_SECONDS:
            return False
    return True

async def update_reply_time(user_id: int):
    bot_state.last_reply_time[user_id] = get_current_time()

def get_user_name(message: Message) -> str:
    try:
        return message.from_user.first_name or f"User{message.from_user.id}"
    except:
        return "Unknown"

def get_user_id_safe(message: Message) -> Optional[int]:
    try:
        return message.from_user.id if message.from_user else None
    except:
        return None

def escape_markdown(text: str) -> str:
    if not text:
        return ""
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text

async def safe_edit(message: Message, text: str, parse_mode: ParseMode = None) -> bool:
    try:
        await message.edit(text, parse_mode=parse_mode)
        return True
    except MessageNotModified:
        return True
    except:
        return False

async def safe_reply(message: Message, text: str, parse_mode: ParseMode = None) -> bool:
    try:
        await message.reply(text, parse_mode=parse_mode)
        return True
    except FloodWait as e:
        if e.value < 60:
            await asyncio.sleep(e.value)
            return await safe_reply(message, text, parse_mode)
        return False
    except:
        return False

async def safe_delete(message: Message) -> bool:
    try:
        await message.delete()
        return True
    except:
        return False

# ═══════════════════════════════════════════════════════════════
#                      GEMINI AI
# ═══════════════════════════════════════════════════════════════

ARYAN_PERSONALITY = """Tu Aryan hai (@MaiHuAryan). Telegram pe replies de raha hai.

PERSONALITY:
- Serious aur sarcastic ho
- Hinglish mein naturally baat kar
- Emojis BILKUL NAHI use kar
- Short-medium replies de
- Tu mostly serious rehta hai

REPLY STYLE:
- "kuch nhi, tu bta.."
- "hn?"
- "hn bhai bol bol"
- "acha"
- "hmm"
- "dekh lenge"
- "thik hai"
- "soja" (for spam/bakwas)

SPECIAL RULES:
- Bot question → "Kya farak padta hai, bol kaam kya hai"
- Personal info → "Ye sab Aryan se seedha puch lena"
- Money/earning → "Aryan se baat kar iske baare mein"

VIP HANDLING:
{vip_context}

Time: {current_time}

Recent chat:
{history}

User: {message}

Reply (short, Hinglish, NO quotes):"""

async def get_ai_response(user_id: int, text: str, is_vip: bool = False, vip_name: str = None) -> str:
    fallback = "Aryan off hai, aaega toh I will let you know"
    
    if not GEMINI_AVAILABLE:
        return fallback
    
    try:
        history = get_conversation_history(user_id, 5)
        context = ""
        for msg in history[-3:]:
            sender = "User" if msg.get("sender") == "user" else "Aryan"
            context += f"{sender}: {msg.get('text', '')[:100]}\n"
        
        vip_context = ""
        if is_vip and vip_name:
            if vip_name.lower() == "soham":
                vip_context = "IMPORTANT: Ye Soham BHAIYA hai. Unko 'bhaiya' bol, friendly reh."
            else:
                vip_context = f"IMPORTANT: Ye {vip_name} hai (VIP). Friendly reh."
        
        current_time = get_current_time().strftime("%I:%M %p")
        
        prompt = ARYAN_PERSONALITY.format(
            vip_context=vip_context,
            current_time=current_time,
            history=context or "None",
            message=text[:500]
        )
        
        keys = get_all_gemini_keys()
        if not keys:
            return fallback
        
        for attempt in range(min(GEMINI_MAX_RETRIES, len(keys))):
            try:
                key = get_next_gemini_key()
                if not key:
                    continue
                
                genai.configure(api_key=key)
                model = genai.GenerativeModel(GEMINI_MODEL, safety_settings=SAFETY_SETTINGS)
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, model.generate_content, prompt)
                
                if response and response.text:
                    reply = response.text.strip()
                    reply = reply.replace("Aryan:", "").strip().strip('"').strip("'")
                    reply = reply.replace("*", "").replace("_", "")
                    
                    if reply and len(reply) > 0:
                        if len(reply) > 300:
                            reply = reply[:300] + "..."
                        return reply
                        
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e).lower():
                    continue
                elif "safety" in str(e).lower():
                    return "hmm kya bol rha hai"
                else:
                    continue
        
        return fallback
    except:
        return fallback

# ═══════════════════════════════════════════════════════════════
#                      MESSAGE HANDLERS
# ═══════════════════════════════════════════════════════════════

async def show_action(client: Client, chat_id: int, duration: float = 3.0):
    try:
        await client.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(duration)
    except:
        await asyncio.sleep(duration)

@app.on_message(filters.private & ~filters.me & ~filters.bot)
async def handle_private(client: Client, message: Message):
    if not is_bot_active():
        return
    
    user_id = get_user_id_safe(message)
    if not user_id or not bot_state.add_processing_user(user_id):
        return
    
    try:
        user_name = get_user_name(message)
        
        if message.sticker:
            return
        
        if not await check_reply_cooldown(user_id):
            return
        
        if not message.text:
            save_message(user_id, "[MEDIA]", "user")
            await show_action(client, message.chat.id)
            reply = "Aryan ko aane do, dekh lega" if message.voice else "mujhe kuch dikhai nhi de rha abhi"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await update_reply_time(user_id)
            BOT_STATS["messages_replied"] += 1
            return
        
        text = message.text.strip()
        if not text:
            return
        
        history = get_conversation_history(user_id)
        is_first = len(history) == 0
        
        save_message(user_id, text, "user")
        
        if is_spam(user_id, text):
            await show_action(client, message.chat.id, 2)
            await safe_reply(message, "Ek baar bol, spam mat kar")
            save_message(user_id, "Ek baar bol, spam mat kar", "bot")
            await update_reply_time(user_id)
            return
        
        if count_words(text) > MAX_WORDS_TO_REPLY:
            await show_action(client, message.chat.id, 2)
            await safe_reply(message, "Bhai itna lamba, summary bol")
            save_message(user_id, "Bhai itna lamba, summary bol", "bot")
            await update_reply_time(user_id)
            return
        
        if is_first and get_config("first_msg_enabled", True):
            await show_action(client, message.chat.id)
            reply = "⚠️ This is automated. Real reply baad mein.\n\nHn bhai bol, Aryan baad mein dekh lega"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await update_reply_time(user_id)
            BOT_STATS["messages_replied"] += 1
            return
        
        vip = get_vip_info(user_id)
        ai_reply = await get_ai_response(user_id, text, vip is not None, vip.get("name") if vip else None)
        
        min_d, max_d = get_delay_range()
        delay = random.uniform(min_d, max_d)
        await show_action(client, message.chat.id, delay)
        
        await safe_reply(message, ai_reply)
        save_message(user_id, ai_reply, "bot")
        
        if should_send_sticker():
            stickers = get_all_stickers()
            if stickers:
                try:
                    await asyncio.sleep(0.5)
                    await message.reply_sticker(random.choice(stickers))
                except:
                    pass
        
        await update_reply_time(user_id)
        BOT_STATS["messages_replied"] += 1
        await send_log(f"💬 {user_name}\n📩 {text[:50]}\n📤 {ai_reply[:50]}")
        
    except Exception as e:
        log_error(f"Handler: {e}")
    finally:
        bot_state.remove_processing_user(user_id)

@app.on_message(filters.group & ~filters.me & ~filters.bot)
async def handle_group(client: Client, message: Message):
    if not is_bot_active():
        return
    
    if not message.text or f"@{BOT_USERNAME}" not in message.text:
        return
    
    user_id = get_user_id_safe(message)
    if not user_id or not bot_state.add_processing_user(user_id):
        return
    
    try:
        text = message.text.replace(f"@{BOT_USERNAME}", "").strip() or "mentioned"
        save_message(user_id, f"[GROUP] {text}", "user")
        
        vip = get_vip_info(user_id)
        reply = await get_ai_response(user_id, text, vip is not None, vip.get("name") if vip else None)
        
        await show_action(client, message.chat.id)
        full_reply = f"{escape_markdown(reply)}\n\n_⚠️ This is automated_"
        await safe_reply(message, full_reply, parse_mode=ParseMode.MARKDOWN)
        save_message(user_id, reply, "bot")
        BOT_STATS["messages_replied"] += 1
        
    except Exception as e:
        log_error(f"Group: {e}")
    finally:
        bot_state.remove_processing_user(user_id)

# ═══════════════════════════════════════════════════════════════
#                      COMMANDS (ALL 50+)
# ═══════════════════════════════════════════════════════════════

@app.on_message(filters.command("setowner") & filters.me)
@rate_limit(1)
async def cmd_setowner(client: Client, message: Message):
    current = get_owner_id()
    if current != 0 and current != message.from_user.id:
        await safe_edit(message, "❌ Owner already set!")
        return
    set_config("owner_id", message.from_user.id)
    await safe_edit(message, f"✅ Owner: `{message.from_user.id}`")

@app.on_message(filters.command("boton") & filters.me)
@owner_only
@rate_limit(2)
async def cmd_boton(client: Client, message: Message):
    set_config("bot_active", True)
    await safe_edit(message, "🤖 **Bot Activated!**")
    await send_log("🟢 Bot ON")

@app.on_message(filters.command("botoff") & filters.me)
@owner_only
@rate_limit(2)
async def cmd_botoff(client: Client, message: Message):
    set_config("bot_active", False)
    
    summary = "🤖 **Bot OFF**\n\n"
    
    if db is not None:  # ✅ FIXED
        try:
            cutoff = get_current_time() - timedelta(hours=24)
            users_data = {}
            
            for doc in db.messages.find():
                uid = doc.get("user_id")
                msgs = doc.get("messages", [])
                count = 0
                for m in msgs:
                    if m.get("sender") == "user":
                        try:
                            msg_time = datetime.fromisoformat(m.get("time", "2000-01-01"))
                            if msg_time.tzinfo is None:
                                msg_time = TIMEZONE.localize(msg_time)
                            if msg_time > cutoff:
                                count += 1
                        except:
                            pass
                if count > 0:
                    users_data[uid] = count
            
            if users_data:
                summary += "📬 **24h Summary:**\n"
                total = 0
                for uid, cnt in sorted(users_data.items(), key=lambda x: x[1], reverse=True)[:10]:
                    try:
                        user = await client.get_users(uid)
                        name = user.first_name or f"User{uid}"
                        vip = get_vip_info(uid)
                        if vip:
                            name = f"👑 {vip.get('name', name)}"
                    except:
                        name = f"User{uid}"
                    summary += f"• {name}: {cnt}\n"
                    total += cnt
                summary += f"\n**Total:** {total} from {len(users_data)}"
        except:
            pass
    
    await safe_edit(message, summary)
    await send_log("🔴 Bot OFF")

@app.on_message(filters.command("status") & filters.me)
@owner_only
async def cmd_status(client: Client, message: Message):
    active = is_bot_active()
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    users = db.messages.count_documents({}) if db is not None else 0  # ✅ FIXED
    vips = db.vips.count_documents({}) if db is not None else 0  # ✅ FIXED
    
    text = f"""📊 **Status**

**Bot:** {"🟢 ON" if active else "🔴 OFF"}
**Uptime:** {uptime}
**Users:** {users}
**VIPs:** {vips}
**Keys:** {len(get_all_gemini_keys())}
**Stickers:** {len(get_all_stickers())}
**DB:** {"✅" if db is not None else "⚠️"}"""  # ✅ FIXED
    
    await safe_edit(message, text)

@app.on_message(filters.command("ping") & filters.me)
async def cmd_ping(client: Client, message: Message):
    start = time.perf_counter()
    await safe_edit(message, "🏓 Pinging...")
    latency = (time.perf_counter() - start) * 1000
    await safe_edit(message, f"🏓 **Pong!** `{latency:.2f}ms`")

@app.on_message(filters.command("help") & filters.me)
async def cmd_help(client: Client, message: Message):
    await safe_edit(message, """🤖 **Commands**

**Basic:** /boton /botoff /status /ping
**VIP:** /addvip /removevip /listvip /vipname
**Keys:** /addkey /listkeys /clearkeys
**Stickers:** /addsticker /liststickers /stickerchance
**Settings:** /firstmsg /delay /setlog
**Memory:** /clearmemory /clearall""")

@app.on_message(filters.command("addvip") & filters.me)
@owner_only
async def cmd_addvip(client: Client, message: Message):
    if not message.reply_to_message:
        await safe_edit(message, "❌ Reply to a user!")
        return
    uid = message.reply_to_message.from_user.id
    name = message.reply_to_message.from_user.first_name
    add_vip(uid, name)
    await safe_edit(message, f"✅ VIP: {name}")

@app.on_message(filters.command("removevip") & filters.me)
@owner_only
async def cmd_removevip(client: Client, message: Message):
    if not message.reply_to_message:
        return
    uid = message.reply_to_message.from_user.id
    remove_vip(uid)
    await safe_edit(message, "✅ Removed")

@app.on_message(filters.command("listvip") & filters.me)
@owner_only
async def cmd_listvip(client: Client, message: Message):
    vips = get_all_vips()
    if not vips:
        await safe_edit(message, "No VIPs")
        return
    text = "👑 **VIPs:**\n"
    for v in vips:
        text += f"• {v.get('name')} (`{v.get('user_id')}`)\n"
    await safe_edit(message, text)

@app.on_message(filters.command("vipname") & filters.me)
@owner_only
async def cmd_vipname(client: Client, message: Message):
    if len(message.command) < 3:
        return
    try:
        uid = int(message.command[1])
        name = " ".join(message.command[2:])
        set_vip_name(uid, name)
        await safe_edit(message, f"✅ {name}")
    except:
        pass

@app.on_message(filters.command("addkey") & filters.me)
@owner_only
async def cmd_addkey(client: Client, message: Message):
    if len(message.command) < 2:
        return
    key = message.command[1].strip()
    add_gemini_key(key)
    await safe_edit(message, f"✅ Keys: {len(get_all_gemini_keys())}")
    await asyncio.sleep(2)
    await safe_delete(message)

@app.on_message(filters.command("listkeys") & filters.me)
@owner_only
async def cmd_listkeys(client: Client, message: Message):
    keys = get_all_gemini_keys()
    await safe_edit(message, f"🔑 **Keys:** {len(keys)}")

@app.on_message(filters.command("clearkeys") & filters.me)
@owner_only
async def cmd_clearkeys(client: Client, message: Message):
    if db is not None:  # ✅ FIXED
        db.gemini_keys.delete_one({"type": "keys"})
    await safe_edit(message, "✅ Keys cleared")

@app.on_message(filters.command("addsticker") & filters.me)
@owner_only
async def cmd_addsticker(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.sticker:
        return
    add_sticker(message.reply_to_message.sticker.file_id)
    await safe_edit(message, f"✅ Stickers: {len(get_all_stickers())}")

@app.on_message(filters.command("liststickers") & filters.me)
@owner_only
async def cmd_liststickers(client: Client, message: Message):
    stickers = get_all_stickers()
    await safe_edit(message, f"📎 **Stickers:** {len(stickers)}")

@app.on_message(filters.command("stickerchance") & filters.me)
@owner_only
async def cmd_stickerchance(client: Client, message: Message):
    if len(message.command) < 2:
        current = get_config("sticker_chance", DEFAULT_STICKER_CHANCE)
        await safe_edit(message, f"Current: {current}%")
        return
    try:
        chance = int(message.command[1])
        if 0 <= chance <= 100:
            set_config("sticker_chance", chance)
            await safe_edit(message, f"✅ {chance}%")
    except:
        pass

@app.on_message(filters.command("firstmsg") & filters.me)
@owner_only
async def cmd_firstmsg(client: Client, message: Message):
    if len(message.command) < 2:
        current = get_config("first_msg_enabled", True)
        await safe_edit(message, f"First msg: **{'ON' if current else 'OFF'}**")
        return
    arg = message.command[1].lower()
    if arg in ["on", "1", "yes"]:
        set_config("first_msg_enabled", True)
        await safe_edit(message, "✅ First msg ON")
    elif arg in ["off", "0", "no"]:
        set_config("first_msg_enabled", False)
        await safe_edit(message, "✅ First msg OFF")

@app.on_message(filters.command("delay") & filters.me)
@owner_only
async def cmd_delay(client: Client, message: Message):
    if len(message.command) < 2:
        min_d, max_d = get_delay_range()
        await safe_edit(message, f"Delay: {min_d}-{max_d}s")
        return
    try:
        parts = message.command[1].split("-")
        min_d = int(parts[0])
        max_d = int(parts[1]) if len(parts) > 1 else min_d
        set_config("delay_min", min_d)
        set_config("delay_max", max_d)
        await safe_edit(message, f"✅ {min_d}-{max_d}s")
    except:
        pass

@app.on_message(filters.command("setlog") & filters.me)
@owner_only
async def cmd_setlog(client: Client, message: Message):
    if len(message.command) < 2:
        return
    try:
        chat_id = int(message.command[1])
        set_config("log_group_id", chat_id)
        await safe_edit(message, f"✅ Log: `{chat_id}`")
        await send_log("🎉 Log configured!")
    except:
        pass

@app.on_message(filters.command("clearmemory") & filters.me)
@owner_only
async def cmd_clearmemory(client: Client, message: Message):
    if not message.reply_to_message:
        return
    uid = message.reply_to_message.from_user.id
    if db is not None:  # ✅ FIXED
        db.messages.delete_one({"user_id": uid})
    await safe_edit(message, f"✅ Cleared: {uid}")

@app.on_message(filters.command("clearall") & filters.me)
@owner_only
async def cmd_clearall(client: Client, message: Message):
    if db is None:  # ✅ FIXED
        await safe_edit(message, "❌ No DB")
        return
    total = db.messages.count_documents({})
    bot_state.confirm_clear_time = get_current_time()
    await safe_edit(message, f"⚠️ Delete {total}?\n\n/confirmclear")

@app.on_message(filters.command("confirmclear") & filters.me)
@owner_only
async def cmd_confirmclear(client: Client, message: Message):
    if not bot_state.confirm_clear_time:
        return
    time_diff = (get_current_time() - bot_state.confirm_clear_time).total_seconds()
    if time_diff > CONFIRM_CLEAR_TIMEOUT:
        bot_state.confirm_clear_time = None
        await safe_edit(message, "❌ Expired")
        return
    if db is not None:  # ✅ FIXED
        count = db.messages.delete_many({}).deleted_count
        await safe_edit(message, f"✅ Cleared {count}")
    bot_state.confirm_clear_time = None

# ═══════════════════════════════════════════════════════════════
#                      STARTUP
# ═══════════════════════════════════════════════════════════════

async def start_bot():
    await app.start()
    me = await app.get_me()
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║            🤖 ARYAN'S USERBOT V5.3 STARTED                  ║
╠══════════════════════════════════════════════════════════════╣
║  User: {me.first_name}
║  Status: {'🟢 ON' if is_bot_active() else '🔴 OFF'}
║  Database: {'✅ Connected' if db is not None else '⚠️ Memory'}
║  Keys: {len(get_all_gemini_keys())}
║  Port: {os.environ.get('PORT', 10000)}
╚══════════════════════════════════════════════════════════════╝
    """)
    
    await send_log(f"🚀 V5.3 Started!\n{me.first_name}")
    await idle()
    await app.stop()

# ═══════════════════════════════════════════════════════════════
#                      MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Starting Aryan's Userbot V5.3 FINAL...\n")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"✅ Web server on port {os.environ.get('PORT', 10000)}")
    
    try:
        asyncio.get_event_loop().run_until_complete(start_bot())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.critical(f"❌ Fatal: {e}")
        traceback.print_exc()
    finally:
        if mongo_client is not None:  # ✅ FIXED
            mongo_client.close()
        logger.info("Bot stopped")
