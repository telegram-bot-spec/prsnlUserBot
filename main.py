"""
╔══════════════════════════════════════════════════════════════╗
║           ARYAN'S 24/7 AI USERBOT - @MaiHuAryan             ║
║                   Serious • Sarcastic • Hinglish             ║
║                                                              ║
║  Version: 5.2 FINAL (ALL FEATURES + WEB SERVER)             ║
║  Features: 50+ Commands, Full AI, VIP System, Logs          ║
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
from flask import Flask, jsonify, request

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
    """Home page with bot stats"""
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    return jsonify({
        "status": "✅ alive",
        "bot": "Aryan's Userbot V5.2",
        "uptime": uptime,
        "stats": BOT_STATS,
        "endpoints": ["/", "/health", "/ping", "/stats"]
    })

@flask_app.route('/health')
def health():
    """Health check for monitoring"""
    return jsonify({"status": "healthy", "code": 200})

@flask_app.route('/ping')
def ping():
    """Simple ping for UptimeRobot"""
    return "pong", 200

@flask_app.route('/stats')
def stats():
    """Detailed stats"""
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    return jsonify({
        "uptime": uptime,
        "messages_replied": BOT_STATS["messages_replied"],
        "commands_executed": BOT_STATS["commands_executed"],
        "errors": BOT_STATS["errors_count"],
        "database": "connected" if db else "memory_only",
        "gemini": "available" if GEMINI_AVAILABLE else "unavailable"
    })

def run_flask():
    """Run Flask server"""
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

# ═══════════════════════════════════════════════════════════════
#                         CONSTANTS
# ═══════════════════════════════════════════════════════════════

# Message Limits
MAX_MESSAGE_LENGTH = 4096
MAX_HISTORY_PER_USER = 100
MAX_WORDS_TO_REPLY = 200
MAX_STICKER_PREVIEW = 5

# Spam Detection
SPAM_MESSAGE_THRESHOLD = 3
SPAM_TIME_WINDOW = 60

# Logs
ACTION_LOG_LIMIT = 50
ERROR_LOG_LIMIT = 20

# Retry Limits
GEMINI_MAX_RETRIES = 3
FLOOD_WAIT_MAX_RETRIES = 3

# Cooldowns
REPLY_COOLDOWN_SECONDS = 2
COMMAND_COOLDOWN_SECONDS = 1
CONFIRM_CLEAR_TIMEOUT = 60

# Delays
MIN_DELAY_SECONDS = 1
MAX_DELAY_SECONDS = 30
DEFAULT_DELAY_MIN = 3
DEFAULT_DELAY_MAX = 8

# Stickers
DEFAULT_STICKER_CHANCE = 10

# Gemini
GEMINI_CONTEXT_LIMIT = 3000
SESSION_STRING_MIN_LENGTH = 100

# ═══════════════════════════════════════════════════════════════
#                         LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Suppress Flask logs
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ═══════════════════════════════════════════════════════════════
#                         CONFIGURATION
# ═══════════════════════════════════════════════════════════════

load_dotenv()

def get_env(key: str, default: str = None, required: bool = False) -> Optional[str]:
    """Get environment variable safely"""
    value = os.getenv(key, default)
    if required and not value:
        logger.critical(f"❌ Missing required: {key}")
        sys.exit(1)
    return value

def get_env_int(key: str, default: int = 0, required: bool = False) -> int:
    """Get integer environment variable"""
    value = get_env(key, str(default), required)
    try:
        return int(value) if value else default
    except:
        return default

# Telegram Config
API_ID = get_env_int("API_ID", required=True)
API_HASH = get_env("API_HASH", required=True)
SESSION_STRING = get_env("SESSION_STRING", required=True)

if len(SESSION_STRING) < SESSION_STRING_MIN_LENGTH:
    logger.critical("❌ Invalid session string")
    sys.exit(1)

OWNER_ID = get_env_int("OWNER_ID", default=0)

# MongoDB
MONGO_URI = get_env("MONGO_URI", required=False)

# Bot Identity
BOT_USERNAME = "MaiHuAryan"
BOT_NAME = "Aryan"
TIMEZONE = pytz.timezone("Asia/Kolkata")

# Gemini Config
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
    """Thread-safe bot state management"""
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
        """Add user to processing set"""
        with self._lock:
            if user_id in self.processing_users:
                return False
            self.processing_users.add(user_id)
            return True
    
    def remove_processing_user(self, user_id: int):
        """Remove user from processing set"""
        with self._lock:
            self.processing_users.discard(user_id)

bot_state = BotState()

# ═══════════════════════════════════════════════════════════════
#                      DATABASE
# ═══════════════════════════════════════════════════════════════

mongo_client: Optional[MongoClient] = None
db = None

def connect_mongodb():
    """Connect to MongoDB"""
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
        
        # Create indexes
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
    """Rate limit decorator for commands"""
    def decorator(func):
        @wraps(func)
        async def wrapper(client: Client, message: Message):
            user_id = message.from_user.id if message.from_user else 0
            now = get_current_time()
            
            last_time = bot_state.last_command_time.get(user_id)
            if last_time:
                diff = (now - last_time).total_seconds()
                if diff < seconds:
                    remaining = seconds - diff
                    try:
                        await message.edit(f"⏳ Wait {remaining:.1f}s")
                    except:
                        pass
                    return
            
            bot_state.last_command_time[user_id] = now
            BOT_STATS["commands_executed"] += 1
            return await func(client, message)
        return wrapper
    return decorator

def owner_only(func):
    """Ensure command is only for owner"""
    @wraps(func)
    async def wrapper(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else 0
        if not is_owner(user_id):
            try:
                await message.edit("❌ Owner only!")
            except:
                pass
            return
        return await func(client, message)
    return wrapper

# ═══════════════════════════════════════════════════════════════
#                      HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_current_time() -> datetime:
    """Get current time in IST"""
    return datetime.now(TIMEZONE)

def get_config(key: str, default: Any = None) -> Any:
    """Get config from database"""
    if not db:
        return default
    try:
        config = db.config.find_one({"key": key})
        return config["value"] if config and "value" in config else default
    except:
        return default

def set_config(key: str, value: Any) -> bool:
    """Set config in database"""
    if not db:
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
    """Log action"""
    timestamp = get_current_time().strftime('%H:%M:%S')
    bot_state.action_logs.append(f"[{timestamp}] {action}")
    logger.info(action)

def log_error(error: str):
    """Log error"""
    timestamp = get_current_time().strftime('%H:%M:%S')
    bot_state.error_logs.append(f"[{timestamp}] {error}")
    logger.error(error)
    BOT_STATS["errors_count"] += 1

def is_bot_active() -> bool:
    """Check if bot is active"""
    return get_config("bot_active", False)

def get_owner_id() -> int:
    """Get owner ID"""
    owner = get_config("owner_id")
    return owner if owner else OWNER_ID

def is_owner(user_id: int) -> bool:
    """Check if user is owner"""
    owner = get_owner_id()
    return user_id == owner and owner != 0

def save_message(user_id: int, text: str, sender: str = "user") -> bool:
    """Save message to database"""
    if not db:
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
    except Exception as e:
        log_error(f"Save message error: {e}")
        return False

def get_conversation_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Get conversation history"""
    if not db:
        return []
    try:
        data = db.messages.find_one({"user_id": user_id})
        return data["messages"][-limit:] if data and "messages" in data else []
    except:
        return []

def get_message_count(user_id: int) -> int:
    """Get total message count for user"""
    if not db:
        return 0
    try:
        data = db.messages.find_one({"user_id": user_id})
        return len(data.get("messages", [])) if data else 0
    except:
        return 0

def get_all_gemini_keys() -> List[str]:
    """Get all Gemini API keys"""
    # Try database first
    if db:
        try:
            doc = db.gemini_keys.find_one({"type": "keys"})
            if doc and doc.get("keys"):
                return doc["keys"]
        except:
            pass
    
    # Fallback to environment
    keys = []
    for i in range(1, 15):
        key = os.getenv(f"GEMINI_KEY_{i}")
        if key and key.strip():
            keys.append(key.strip())
    
    # Save to database
    if keys and db:
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
    """Add a Gemini key"""
    if not db:
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
    """Remove Gemini key by index"""
    if not db:
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
    """Get next Gemini key with rotation"""
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
    """Get VIP info"""
    if not db:
        return None
    try:
        return db.vips.find_one({"user_id": user_id})
    except:
        return None

def add_vip(user_id: int, name: str) -> bool:
    """Add VIP"""
    if not db:
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
    """Remove VIP"""
    if not db:
        return False
    try:
        result = db.vips.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    except:
        return False

def get_all_vips() -> List[Dict]:
    """Get all VIPs"""
    if not db:
        return []
    try:
        return list(db.vips.find())
    except:
        return []

def set_vip_name(user_id: int, name: str) -> bool:
    """Set VIP custom name"""
    if not db:
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
    """Get log group ID"""
    return get_config("log_group_id")

async def send_log(text: str, retry: int = 0) -> bool:
    """Send log to log group"""
    if retry >= FLOOD_WAIT_MAX_RETRIES:
        return False
    
    log_group = get_log_group()
    if not log_group:
        return False
    
    try:
        if len(text) > MAX_MESSAGE_LENGTH - 100:
            text = text[:MAX_MESSAGE_LENGTH - 100] + "..."
        
        await app.send_message(
            log_group,
            f"📊 **LOG**\n\n{text}",
            parse_mode=ParseMode.MARKDOWN
        )
        return True
    except FloodWait as e:
        await asyncio.sleep(min(e.value, 60))
        return await send_log(text, retry + 1)
    except:
        return False

def get_all_stickers() -> List[str]:
    """Get all stickers"""
    if not db:
        return []
    try:
        doc = db.stickers.find_one({"type": "stickers"})
        return doc.get("file_ids", []) if doc else []
    except:
        return []

def add_sticker(file_id: str) -> bool:
    """Add sticker"""
    if not db:
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
    """Remove sticker"""
    if not db:
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
    """Clear all stickers"""
    if not db:
        return False
    try:
        db.stickers.delete_one({"type": "stickers"})
        return True
    except:
        return False

def should_send_sticker() -> bool:
    """Check if should send sticker"""
    chance = get_config("sticker_chance", DEFAULT_STICKER_CHANCE)
    return random.randint(1, 100) <= chance

def get_delay_range() -> Tuple[int, int]:
    """Get delay range"""
    return (
        get_config("delay_min", DEFAULT_DELAY_MIN),
        get_config("delay_max", DEFAULT_DELAY_MAX)
    )

def count_words(text: str) -> int:
    """Count words"""
    return len(text.split()) if text else 0

def is_spam(user_id: int, text: str) -> bool:
    """Check if spam"""
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
    """Check reply cooldown"""
    last = bot_state.last_reply_time.get(user_id)
    if last:
        if (get_current_time() - last).total_seconds() < REPLY_COOLDOWN_SECONDS:
            return False
    return True

async def update_reply_time(user_id: int):
    """Update reply time"""
    bot_state.last_reply_time[user_id] = get_current_time()

def get_user_name(message: Message) -> str:
    """Get user name"""
    try:
        return message.from_user.first_name or f"User{message.from_user.id}"
    except:
        return "Unknown"

def get_user_id_safe(message: Message) -> Optional[int]:
    """Get user ID safely"""
    try:
        return message.from_user.id if message.from_user else None
    except:
        return None

def escape_markdown(text: str) -> str:
    """Escape markdown"""
    if not text:
        return ""
    for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(char, f'\\{char}')
    return text

async def safe_edit(message: Message, text: str, parse_mode: ParseMode = None) -> bool:
    """Safe message edit"""
    try:
        await message.edit(text, parse_mode=parse_mode)
        return True
    except MessageNotModified:
        return True
    except Exception as e:
        log_error(f"Edit error: {e}")
        return False

async def safe_reply(message: Message, text: str, parse_mode: ParseMode = None) -> bool:
    """Safe message reply"""
    try:
        await message.reply(text, parse_mode=parse_mode)
        return True
    except MessageIdInvalid:
        log_error("Message deleted before reply")
        return False
    except UserIsBlocked:
        log_error("User blocked us")
        return False
    except ChatWriteForbidden:
        log_error("Cannot write in chat")
        return False
    except FloodWait as e:
        if e.value < 60:
            await asyncio.sleep(e.value)
            return await safe_reply(message, text, parse_mode)
        return False
    except Exception as e:
        log_error(f"Reply error: {e}")
        return False

async def safe_delete(message: Message) -> bool:
    """Safe message delete"""
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
- Hinglish mein naturally baat kar (Hindi-English mix)
- Emojis BILKUL NAHI use kar (absolutely zero)
- Short-medium replies de mostly
- Tu mostly serious rehta hai, friendly sirf VIPs ke saath

REPLY STYLE EXAMPLES:
- "kuch nhi, tu bta.."
- "hn?"
- "hn bhai bol bol"
- "acha"
- "hmm"
- "dekh lenge"
- "phir baat krte"
- "thik hai"
- "hehehehhe" (for funny stuff)
- "gunnite bhaii" (for goodnight)
- "ye toh phle se pta hai" (for compliments)
- "soja" (for bakwas/flirting/spam)

TOPICS:
- Tu paisa kamane, skills sikhne, hustle ki baatein karta hai
- "skills sikh le", "kuch ukhaad" type vibes

SPECIAL RULES:
- If someone asks "tu bot hai?", "automated hai?" → Reply: "Kya farak padta hai, bol kaam kya hai"
- If someone asks personal info (number, address, photo) → Reply: "Ye sab Aryan se seedha puch lena"
- If someone asks about money/skills/earning → Reply: "Aryan se baat kar iske baare mein"
- If someone sends bakwas/flirts → Reply: "soja"
- Late night (after 1 AM) → Can add "bhai so ja" type replies

VIP HANDLING:
{vip_context}

Current time: {current_time} IST

RECENT CONVERSATION:
{history}

User's message: {message}

Reply as Aryan (short, natural Hinglish, NO quotes, NO asterisks):"""

async def get_ai_response(
    user_id: int, 
    text: str, 
    is_vip: bool = False, 
    vip_name: str = None
) -> str:
    """Get AI response from Gemini"""
    
    fallback = "Aryan off hai, aaega toh I will let you know"
    
    if not GEMINI_AVAILABLE:
        return fallback
    
    try:
        # Get history
        history = get_conversation_history(user_id, 5)
        context = ""
        for msg in history[-3:]:
            sender = "User" if msg.get("sender") == "user" else "Aryan"
            context += f"{sender}: {msg.get('text', '')[:100]}\n"
        
        # VIP context
        vip_context = ""
        if is_vip and vip_name:
            if vip_name.lower() == "soham":
                vip_context = "IMPORTANT: Ye Soham BHAIYA hai. Unko 'bhaiya' bol, bahut friendly reh, respect de."
            else:
                vip_context = f"IMPORTANT: Ye {vip_name} hai (VIP). Friendly aur respectful reh."
        else:
            vip_context = "Normal user hai, usual serious/sarcastic mode."
        
        # Time
        current_time = get_current_time().strftime("%I:%M %p, %d %b")
        
        # Build prompt
        prompt = ARYAN_PERSONALITY.format(
            vip_context=vip_context,
            current_time=current_time,
            history=context or "No previous conversation",
            message=text[:500]
        )
        
        # Try keys
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
                    # Clean up
                    reply = reply.replace("Aryan:", "").strip()
                    reply = reply.strip('"').strip("'").strip()
                    reply = reply.replace("*", "").replace("_", "")
                    
                    if reply and len(reply) > 0:
                        if len(reply) > 300:
                            reply = reply[:300] + "..."
                        log_action(f"AI: {reply[:40]}...")
                        return reply
                        
            except Exception as e:
                error = str(e).lower()
                if "quota" in error or "429" in error:
                    log_action(f"Key {attempt+1} quota exceeded")
                    continue
                elif "safety" in error:
                    return "hmm kya bol rha hai"
                else:
                    log_error(f"Gemini: {str(e)[:50]}")
                    continue
        
        return fallback
        
    except Exception as e:
        log_error(f"AI error: {e}")
        return fallback

# ═══════════════════════════════════════════════════════════════
#                      MESSAGE HANDLERS
# ═══════════════════════════════════════════════════════════════

async def show_action(client: Client, chat_id: int, duration: float = 3.0):
    """Show chat action"""
    try:
        await client.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)
        await asyncio.sleep(duration)
    except:
        await asyncio.sleep(duration)

@app.on_message(filters.private & ~filters.me & ~filters.bot)
async def handle_private(client: Client, message: Message):
    """Handle private messages"""
    
    if not is_bot_active():
        return
    
    user_id = get_user_id_safe(message)
    if not user_id:
        return
    
    if not bot_state.add_processing_user(user_id):
        return
    
    try:
        user_name = get_user_name(message)
        
        # Ignore stickers
        if message.sticker:
            log_action(f"Ignored sticker from {user_name}")
            return
        
        # Cooldown
        if not await check_reply_cooldown(user_id):
            return
        
        # Handle media
        if not message.text:
            save_message(user_id, "[MEDIA]", "user")
            await show_action(client, message.chat.id)
            
            if message.voice or message.audio:
                reply = "Aryan ko aane do, dekh lega"
            elif message.video_note:
                reply = "Aryan ko aane do, dekh lega"  
            else:
                reply = "mujhe kuch dikhai nhi de rha abhi"
            
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await update_reply_time(user_id)
            await send_log(f"📸 {user_name}: Media → {reply}")
            BOT_STATS["messages_replied"] += 1
            return
        
        text = message.text.strip()
        if not text:
            return
        
        # Check first message BEFORE saving
        history = get_conversation_history(user_id)
        is_first = len(history) == 0
        
        # Save message
        save_message(user_id, text, "user")
        
        # Spam check
        if is_spam(user_id, text):
            await show_action(client, message.chat.id, 2)
            reply = "Ek baar bol, spam mat kar"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await update_reply_time(user_id)
            log_action(f"Spam: {user_name}")
            return
        
        # Long message
        if count_words(text) > MAX_WORDS_TO_REPLY:
            await show_action(client, message.chat.id, 2)
            reply = "Bhai itna lamba, summary bol"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await update_reply_time(user_id)
            return
        
        # First message greeting
        if is_first and get_config("first_msg_enabled", True):
            await show_action(client, message.chat.id)
            reply = "⚠️ This is automated. Real reply baad mein.\n\nHn bhai bol, Aryan baad mein dekh lega"
            await safe_reply(message, reply)
            save_message(user_id, reply, "bot")
            await update_reply_time(user_id)
            await send_log(f"🆕 First: {user_name}\n↳ {text[:50]}")
            BOT_STATS["messages_replied"] += 1
            return
        
        # VIP check
        vip = get_vip_info(user_id)
        is_vip = vip is not None
        vip_name = vip.get("name") if vip else None
        
        # Get AI reply
        ai_reply = await get_ai_response(user_id, text, is_vip, vip_name)
        
        # Smart delay
        reply_words = count_words(ai_reply)
        min_d, max_d = get_delay_range()
        
        if reply_words < 5:
            delay = random.uniform(min_d, min_d + 2)
        elif reply_words < 15:
            delay = random.uniform(min_d + 1, max_d - 1)
        else:
            delay = random.uniform(max_d - 2, max_d)
        
        await show_action(client, message.chat.id, delay)
        
        # Send reply
        await safe_reply(message, ai_reply)
        save_message(user_id, ai_reply, "bot")
        
        # Maybe send sticker AFTER reply
        if should_send_sticker():
            stickers = get_all_stickers()
            if stickers:
                try:
                    await asyncio.sleep(0.5)
                    await message.reply_sticker(random.choice(stickers))
                except:
                    pass
        
        await update_reply_time(user_id)
        log_action(f"Replied to {user_name}")
        BOT_STATS["messages_replied"] += 1
        
        # Log
        await send_log(f"💬 {user_name}\n📩 {text[:50]}{'...' if len(text) > 50 else ''}\n📤 {ai_reply[:50]}{'...' if len(ai_reply) > 50 else ''}")
        
    except Exception as e:
        log_error(f"Handler: {e}")
    finally:
        bot_state.remove_processing_user(user_id)

@app.on_message(filters.group & ~filters.me & ~filters.bot)
async def handle_group(client: Client, message: Message):
    """Handle group messages (only when mentioned)"""
    
    if not is_bot_active():
        return
    
    if not message.text or f"@{BOT_USERNAME}" not in message.text:
        return
    
    user_id = get_user_id_safe(message)
    if not user_id or not bot_state.add_processing_user(user_id):
        return
    
    try:
        user_name = get_user_name(message)
        text = message.text.replace(f"@{BOT_USERNAME}", "").strip() or "mentioned me"
        
        save_message(user_id, f"[GROUP] {text}", "user")
        
        # VIP check
        vip = get_vip_info(user_id)
        
        # Get reply
        reply = await get_ai_response(user_id, text, vip is not None, vip.get("name") if vip else None)
        
        await show_action(client, message.chat.id)
        
        # Reply with warning
        full_reply = f"{escape_markdown(reply)}\n\n_⚠️ This is automated_"
        await safe_reply(message, full_reply, parse_mode=ParseMode.MARKDOWN)
        save_message(user_id, reply, "bot")
        
        group_name = message.chat.title or "Unknown"
        log_action(f"Group: {group_name} by {user_name}")
        BOT_STATS["messages_replied"] += 1
        
    except Exception as e:
        log_error(f"Group: {e}")
    finally:
        bot_state.remove_processing_user(user_id)

# ═══════════════════════════════════════════════════════════════
#                      ALL COMMANDS (50+)
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────
# BASIC COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("setowner") & filters.me)
@rate_limit(1)
async def cmd_setowner(client: Client, message: Message):
    """Set owner ID"""
    current = get_owner_id()
    if current != 0 and current != message.from_user.id:
        await safe_edit(message, "❌ Owner already set!")
        return
    
    set_config("owner_id", message.from_user.id)
    await safe_edit(message, f"✅ Owner set: `{message.from_user.id}`")
    log_action(f"Owner set: {message.from_user.id}")

@app.on_message(filters.command("boton") & filters.me)
@owner_only
@rate_limit(2)
async def cmd_boton(client: Client, message: Message):
    """Activate bot"""
    set_config("bot_active", True)
    await safe_edit(message, "🤖 **Bot Activated!**\n\nNow replying to messages...")
    log_action("Bot activated")
    await send_log("🟢 Bot ACTIVATED")

@app.on_message(filters.command("botoff") & filters.me)
@owner_only
@rate_limit(2)
async def cmd_botoff(client: Client, message: Message):
    """Deactivate bot with summary"""
    set_config("bot_active", False)
    
    # Generate summary
    summary = "🤖 **Bot Deactivated**\n\n"
    
    if db:
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
                summary += "━━━━━━━━━━━━━━━━\n"
                total = 0
                
                for uid, cnt in sorted(users_data.items(), key=lambda x: x[1], reverse=True)[:10]:
                    try:
                        user = await client.get_users(uid)
                        name = user.first_name or f"User{uid}"
                        vip = get_vip_info(uid)
                        if vip:
                            name = f"👑 {vip.get('name', name)}"
                    except:
                        name = f"User {uid}"
                    
                    summary += f"• {name}: {cnt} msgs\n"
                    total += cnt
                
                summary += "━━━━━━━━━━━━━━━━\n"
                summary += f"**Total:** {total} from {len(users_data)} users"
            else:
                summary += "No messages received recently."
                
        except Exception as e:
            log_error(f"Summary error: {e}")
    
    await safe_edit(message, summary)
    log_action("Bot deactivated")
    await send_log("🔴 Bot DEACTIVATED")

@app.on_message(filters.command("status") & filters.me)
@owner_only
async def cmd_status(client: Client, message: Message):
    """Show full status"""
    active = is_bot_active()
    status = "🟢 ACTIVE" if active else "🔴 INACTIVE"
    
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    users = db.messages.count_documents({}) if db else 0
    vips = db.vips.count_documents({}) if db else 0
    keys = len(get_all_gemini_keys())
    stickers = len(get_all_stickers())
    min_d, max_d = get_delay_range()
    
    text = f"""📊 **Aryan's Userbot Status**

**Bot:** {status}
**Uptime:** {uptime}

**📈 Stats:**
├ Messages Replied: {BOT_STATS['messages_replied']}
├ Commands Executed: {BOT_STATS['commands_executed']}
└ Errors: {BOT_STATS['errors_count']}

**💾 Database:**
├ Users: {users}
├ VIPs: {vips}
├ Stickers: {stickers}
└ Status: {"✅ Connected" if db else "⚠️ Memory Only"}

**⚙️ Settings:**
├ Gemini Keys: {keys}
├ Delay: {min_d}-{max_d}s
├ Sticker Chance: {get_config('sticker_chance', DEFAULT_STICKER_CHANCE)}%
├ First Msg: {"✅ ON" if get_config('first_msg_enabled', True) else "❌ OFF"}
└ Log Group: {"✅ Set" if get_log_group() else "❌ Not Set"}

**🌐 Web Server:**
└ Port: {os.environ.get('PORT', 10000)}"""
    
    await safe_edit(message, text)

@app.on_message(filters.command("ping") & filters.me)
async def cmd_ping(client: Client, message: Message):
    """Check latency"""
    start = time.perf_counter()
    msg = await message.edit("🏓 Pinging...")
    latency = (time.perf_counter() - start) * 1000
    await safe_edit(message, f"🏓 **Pong!**\n\n⏱️ Latency: `{latency:.2f}ms`")

@app.on_message(filters.command("alive") & filters.me)
async def cmd_alive(client: Client, message: Message):
    """Check if alive"""
    uptime = str(datetime.now() - START_TIME).split('.')[0]
    await safe_edit(message, f"✅ **I'm Alive!**\n\n⏰ Uptime: `{uptime}`")

# ─────────────────────────────────────
# VIP COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("addvip") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_addvip(client: Client, message: Message):
    """Add VIP by reply or ID"""
    user_id = None
    name = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
        name = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            name = f"User{user_id}"
        except:
            await safe_edit(message, "❌ Invalid user ID")
            return
    else:
        await safe_edit(message, "❌ Reply to a user or use: /addvip [user_id]")
        return
    
    if add_vip(user_id, name):
        await safe_edit(message, f"✅ Added VIP: **{name}** (`{user_id}`)\n\nSet custom name: /vipname {user_id} Name")
        log_action(f"VIP added: {name}")
    else:
        await safe_edit(message, "❌ Failed to add VIP (database error)")

@app.on_message(filters.command("removevip") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_removevip(client: Client, message: Message):
    """Remove VIP"""
    user_id = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except:
            await safe_edit(message, "❌ Invalid user ID")
            return
    else:
        await safe_edit(message, "❌ Reply to a user or use: /removevip [user_id]")
        return
    
    if remove_vip(user_id):
        await safe_edit(message, f"✅ Removed VIP: `{user_id}`")
        log_action(f"VIP removed: {user_id}")
    else:
        await safe_edit(message, "❌ User not in VIP list")

@app.on_message(filters.command("listvip") & filters.me)
@owner_only
async def cmd_listvip(client: Client, message: Message):
    """List all VIPs"""
    vips = get_all_vips()
    
    if not vips:
        await safe_edit(message, "👑 No VIPs added yet\n\nUse /addvip to add")
        return
    
    text = "👑 **VIP List:**\n\n"
    for i, v in enumerate(vips, 1):
        text += f"{i}. **{v.get('name', 'Unknown')}**\n   └ ID: `{v.get('user_id')}`\n"
    
    await safe_edit(message, text)

@app.on_message(filters.command("vipname") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_vipname(client: Client, message: Message):
    """Set VIP custom name"""
    if len(message.command) < 3:
        await safe_edit(message, "❌ Usage: /vipname [user_id] [name]\n\nExample: /vipname 123456789 Soham")
        return
    
    try:
        user_id = int(message.command[1])
        name = " ".join(message.command[2:])
        
        if set_vip_name(user_id, name):
            await safe_edit(message, f"✅ VIP name set: **{name}** (`{user_id}`)")
            log_action(f"VIP name: {name}")
        else:
            await safe_edit(message, "❌ Failed (database error)")
    except:
        await safe_edit(message, "❌ Invalid user ID")

# ─────────────────────────────────────
# GEMINI KEY COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("addkey") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_addkey(client: Client, message: Message):
    """Add Gemini API key"""
    if len(message.command) < 2:
        await safe_edit(message, "❌ Usage: /addkey [API_KEY]")
        return
    
    key = message.command[1].strip()
    
    if not key.startswith("AIza"):
        await safe_edit(message, "❌ Invalid key format (should start with AIza)")
        return
    
    keys = get_all_gemini_keys()
    if key in keys:
        await safe_edit(message, "❌ Key already exists!")
        return
    
    if add_gemini_key(key):
        total = len(get_all_gemini_keys())
        await safe_edit(message, f"✅ Key added!\n\n**Total keys:** {total}")
        # Delete message for security
        await asyncio.sleep(2)
        await safe_delete(message)
        log_action("Gemini key added")
    else:
        await safe_edit(message, "❌ Failed to add key")

@app.on_message(filters.command("removekey") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_removekey(client: Client, message: Message):
    """Remove Gemini key by index"""
    if len(message.command) < 2:
        await safe_edit(message, "❌ Usage: /removekey [number]\n\nExample: /removekey 1")
        return
    
    try:
        index = int(message.command[1]) - 1
        if remove_gemini_key(index):
            await safe_edit(message, f"✅ Key #{index + 1} removed")
            log_action(f"Gemini key removed: #{index + 1}")
        else:
            await safe_edit(message, "❌ Invalid key number")
    except:
        await safe_edit(message, "❌ Invalid number")

@app.on_message(filters.command("listkeys") & filters.me)
@owner_only
async def cmd_listkeys(client: Client, message: Message):
    """List all Gemini keys (masked)"""
    keys = get_all_gemini_keys()
    
    if not keys:
        await safe_edit(message, "🔑 No Gemini keys configured\n\nUse /addkey to add")
        return
    
    text = "🔑 **Gemini API Keys:**\n\n"
    for i, key in enumerate(keys, 1):
        masked = key[:8] + "..." + key[-4:]
        current = " 👈" if i - 1 == bot_state.gemini_key_index % len(keys) else ""
        text += f"{i}. `{masked}`{current}\n"
    
    text += f"\n**Current index:** {bot_state.gemini_key_index % len(keys) + 1}"
    await safe_edit(message, text)

@app.on_message(filters.command("testkeys") & filters.me)
@owner_only
async def cmd_testkeys(client: Client, message: Message):
    """Test all Gemini keys"""
    keys = get_all_gemini_keys()
    
    if not keys:
        await safe_edit(message, "❌ No keys to test")
        return
    
    await safe_edit(message, "🔄 Testing keys...")
    
    results = ""
    for i, key in enumerate(keys, 1):
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                model.generate_content, 
                "Say OK"
            )
            if response and response.text:
                results += f"{i}. ✅ Working\n"
            else:
                results += f"{i}. ⚠️ Empty response\n"
        except Exception as e:
            err = str(e)[:25]
            results += f"{i}. ❌ {err}...\n"
    
    await safe_edit(message, f"🔑 **Key Test Results:**\n\n{results}")

@app.on_message(filters.command("clearkeys") & filters.me)
@owner_only
async def cmd_clearkeys(client: Client, message: Message):
    """Clear all Gemini keys"""
    if db:
        db.gemini_keys.delete_one({"type": "keys"})
    bot_state.gemini_key_index = 0
    await safe_edit(message, "✅ All Gemini keys cleared")
    log_action("All keys cleared")

# ─────────────────────────────────────
# STICKER COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("addsticker") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_addsticker(client: Client, message: Message):
    """Add sticker to rotation"""
    if not message.reply_to_message or not message.reply_to_message.sticker:
        await safe_edit(message, "❌ Reply to a sticker!")
        return
    
    file_id = message.reply_to_message.sticker.file_id
    
    if add_sticker(file_id):
        total = len(get_all_stickers())
        await safe_edit(message, f"✅ Sticker added!\n\n**Total:** {total}")
        log_action("Sticker added")
    else:
        await safe_edit(message, "❌ Failed to add sticker")

@app.on_message(filters.command("removesticker") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_removesticker(client: Client, message: Message):
    """Remove sticker from rotation"""
    if not message.reply_to_message or not message.reply_to_message.sticker:
        await safe_edit(message, "❌ Reply to a sticker!")
        return
    
    file_id = message.reply_to_message.sticker.file_id
    
    if remove_sticker(file_id):
        total = len(get_all_stickers())
        await safe_edit(message, f"✅ Sticker removed!\n\n**Remaining:** {total}")
        log_action("Sticker removed")
    else:
        await safe_edit(message, "❌ Sticker not found")

@app.on_message(filters.command("liststickers") & filters.me)
@owner_only
async def cmd_liststickers(client: Client, message: Message):
    """List all stickers"""
    stickers = get_all_stickers()
    
    if not stickers:
        await safe_edit(message, "📎 No stickers added\n\nReply to sticker with /addsticker")
        return
    
    await safe_edit(message, f"📎 **Total Stickers:** {len(stickers)}\n\nSending preview...")
    
    for sticker_id in stickers[:MAX_STICKER_PREVIEW]:
        try:
            await client.send_sticker(message.chat.id, sticker_id)
            await asyncio.sleep(0.3)
        except:
            pass

@app.on_message(filters.command("clearstickers") & filters.me)
@owner_only
async def cmd_clearstickers(client: Client, message: Message):
    """Clear all stickers"""
    if clear_all_stickers():
        await safe_edit(message, "✅ All stickers cleared")
        log_action("Stickers cleared")
    else:
        await safe_edit(message, "❌ Failed to clear")

@app.on_message(filters.command("stickerchance") & filters.me)
@owner_only
async def cmd_stickerchance(client: Client, message: Message):
    """Set sticker chance percentage"""
    if len(message.command) < 2:
        current = get_config("sticker_chance", DEFAULT_STICKER_CHANCE)
        await safe_edit(message, f"🎲 Current: **{current}%**\n\nUsage: /stickerchance [0-100]")
        return
    
    try:
        chance = int(message.command[1])
        if 0 <= chance <= 100:
            set_config("sticker_chance", chance)
            await safe_edit(message, f"✅ Sticker chance: **{chance}%**")
        else:
            await safe_edit(message, "❌ Use 0-100")
    except:
        await safe_edit(message, "❌ Invalid number")

# ─────────────────────────────────────
# SETTINGS COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("firstmsg") & filters.me)
@owner_only
async def cmd_firstmsg(client: Client, message: Message):
    """Toggle first message greeting"""
    if len(message.command) < 2:
        current = get_config("first_msg_enabled", True)
        status = "✅ ON" if current else "❌ OFF"
        await safe_edit(message, f"👋 First message greeting: **{status}**\n\nUsage: /firstmsg on/off")
        return
    
    arg = message.command[1].lower()
    if arg in ["on", "true", "1", "yes"]:
        set_config("first_msg_enabled", True)
        await safe_edit(message, "✅ First message greeting **ENABLED**")
    elif arg in ["off", "false", "0", "no"]:
        set_config("first_msg_enabled", False)
        await safe_edit(message, "✅ First message greeting **DISABLED**")
    else:
        await safe_edit(message, "❌ Use: on/off")

@app.on_message(filters.command("delay") & filters.me)
@owner_only
async def cmd_delay(client: Client, message: Message):
    """Set reply delay range"""
    if len(message.command) < 2:
        min_d, max_d = get_delay_range()
        await safe_edit(message, f"⏱️ Current delay: **{min_d}-{max_d}s**\n\nUsage: /delay 3-8")
        return
    
    try:
        parts = message.command[1].split("-")
        min_d = int(parts[0])
        max_d = int(parts[1]) if len(parts) > 1 else min_d
        
        if min_d < 1:
            min_d = 1
        if max_d > 30:
            max_d = 30
        if min_d > max_d:
            min_d, max_d = max_d, min_d
        
        set_config("delay_min", min_d)
        set_config("delay_max", max_d)
        await safe_edit(message, f"✅ Delay set: **{min_d}-{max_d}s**")
    except:
        await safe_edit(message, "❌ Use format: 3-8")

@app.on_message(filters.command("setlog") & filters.me)
@owner_only
async def cmd_setlog(client: Client, message: Message):
    """Set log group"""
    if len(message.command) < 2:
        current = get_log_group()
        if current:
            await safe_edit(message, f"📊 Current log group: `{current}`\n\nChange: /setlog [chat_id]")
        else:
            await safe_edit(message, "📊 No log group set\n\nUsage: /setlog [chat_id]")
        return
    
    try:
        chat_id = int(message.command[1])
        set_config("log_group_id", chat_id)
        await safe_edit(message, f"✅ Log group: `{chat_id}`")
        await send_log("🎉 Log group configured successfully!")
        log_action(f"Log group set: {chat_id}")
    except:
        await safe_edit(message, "❌ Invalid chat ID")

@app.on_message(filters.command("testlog") & filters.me)
@owner_only
async def cmd_testlog(client: Client, message: Message):
    """Test log group"""
    log_group = get_log_group()
    if not log_group:
        await safe_edit(message, "❌ No log group set!\n\nUse /setlog first")
        return
    
    success = await send_log("✅ Log test successful!")
    if success:
        await safe_edit(message, "✅ Log test sent!")
    else:
        await safe_edit(message, "❌ Failed to send log")

@app.on_message(filters.command("disablelog") & filters.me)
@owner_only
async def cmd_disablelog(client: Client, message: Message):
    """Disable logging"""
    set_config("log_group_id", None)
    await safe_edit(message, "✅ Logging disabled")
    log_action("Logging disabled")

# ─────────────────────────────────────
# MEMORY COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("clearmemory") & filters.me)
@owner_only
@rate_limit(1)
async def cmd_clearmemory(client: Client, message: Message):
    """Clear user's conversation history"""
    user_id = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except:
            await safe_edit(message, "❌ Invalid user ID")
            return
    else:
        await safe_edit(message, "❌ Reply to a user or use: /clearmemory [user_id]")
        return
    
    if db:
        result = db.messages.delete_one({"user_id": user_id})
        if result.deleted_count > 0:
            await safe_edit(message, f"✅ Memory cleared for: `{user_id}`")
            log_action(f"Memory cleared: {user_id}")
        else:
            await safe_edit(message, f"ℹ️ No memory found for: `{user_id}`")
    else:
        await safe_edit(message, "❌ No database connected")

@app.on_message(filters.command("memory") & filters.me)
@owner_only
async def cmd_memory(client: Client, message: Message):
    """Check user's message count"""
    user_id = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except:
            await safe_edit(message, "❌ Invalid user ID")
            return
    else:
        await safe_edit(message, "❌ Reply to a user or use: /memory [user_id]")
        return
    
    count = get_message_count(user_id)
    await safe_edit(message, f"💾 User `{user_id}`\n\n**Messages stored:** {count}")

@app.on_message(filters.command("clearall") & filters.me)
@owner_only
async def cmd_clearall(client: Client, message: Message):
    """Clear all conversations (with confirmation)"""
    if not db:
        await safe_edit(message, "❌ No database")
        return
    
    total = db.messages.count_documents({})
    bot_state.confirm_clear_time = get_current_time()
    bot_state.confirm_clear_user = message.from_user.id
    
    await safe_edit(message, f"⚠️ This will delete **{total}** conversations!\n\nSend /confirmclear within 60 seconds to proceed")

@app.on_message(filters.command("confirmclear") & filters.me)
@owner_only
async def cmd_confirmclear(client: Client, message: Message):
    """Confirm clear all"""
    if not bot_state.confirm_clear_time:
        await safe_edit(message, "❌ Use /clearall first")
        return
    
    if bot_state.confirm_clear_user != message.from_user.id:
        await safe_edit(message, "❌ Not your confirmation request")
        return
    
    time_diff = (get_current_time() - bot_state.confirm_clear_time).total_seconds()
    if time_diff > CONFIRM_CLEAR_TIMEOUT:
        bot_state.confirm_clear_time = None
        await safe_edit(message, "❌ Confirmation expired. Use /clearall again")
        return
    
    if db:
        count = db.messages.delete_many({}).deleted_count
        await safe_edit(message, f"✅ Cleared **{count}** conversations")
        log_action(f"All memory cleared: {count}")
    
    bot_state.confirm_clear_time = None
    bot_state.confirm_clear_user = None

# ─────────────────────────────────────
# DEBUG COMMANDS
# ─────────────────────────────────────

@app.on_message(filters.command("logs") & filters.me)
@owner_only
async def cmd_logs(client: Client, message: Message):
    """Show recent action logs"""
    logs = list(bot_state.action_logs)[-15:]
    
    if not logs:
        await safe_edit(message, "📋 No recent logs")
        return
    
    text = "📋 **Recent Logs:**\n\n```\n"
    text += "\n".join(logs)
    text += "\n```"
    
    await safe_edit(message, text)

@app.on_message(filters.command("errors") & filters.me)
@owner_only
async def cmd_errors(client: Client, message: Message):
    """Show recent errors"""
    errors = list(bot_state.error_logs)[-10:]
    
    if not errors:
        await safe_edit(message, "✅ No recent errors!")
        return
    
    text = "❌ **Recent Errors:**\n\n```\n"
    text += "\n".join(errors)
    text += "\n```"
    
    await safe_edit(message, text)

@app.on_message(filters.command("restart") & filters.me)
@owner_only
async def cmd_restart(client: Client, message: Message):
    """Restart bot (note: may not work on all platforms)"""
    await safe_edit(message, "🔄 Restarting...")
    log_action("Bot restart requested")
    await send_log("🔄 Bot restarting...")
    
    # Try different restart methods
    try:
        os.execv(sys.executable, ['python'] + sys.argv)
    except:
        await safe_edit(message, "⚠️ Auto-restart failed. Manually redeploy on Render.")

# ─────────────────────────────────────
# HELP COMMAND
# ─────────────────────────────────────

@app.on_message(filters.command("help") & filters.me)
async def cmd_help(client: Client, message: Message):
    """Show all commands"""
    help_text = """🤖 **Aryan's Userbot - All Commands**

**🎛️ Basic:**
/boton - Activate bot
/botoff - Deactivate + summary
/status - Full status
/ping - Check latency
/alive - Check if alive

**👑 VIP Management:**
/addvip - Add VIP (reply/ID)
/removevip - Remove VIP
/listvip - List all VIPs
/vipname [id] [name] - Set name

**🔑 Gemini Keys:**
/addkey [key] - Add API key
/removekey [#] - Remove by number
/listkeys - Show all (masked)
/testkeys - Test all keys
/clearkeys - Remove all

**📎 Stickers:**
/addsticker - Add (reply)
/removesticker - Remove (reply)
/liststickers - List + preview
/clearstickers - Remove all
/stickerchance [%] - Set chance

**⚙️ Settings:**
/firstmsg on/off - Greeting toggle
/delay [min-max] - Reply delay
/setlog [chat_id] - Log group
/testlog - Test logging
/disablelog - Disable logs

**💾 Memory:**
/clearmemory - Clear user
/memory - Check count
/clearall - Clear all (confirm)

**🔧 Debug:**
/logs - Action logs
/errors - Error logs
/restart - Restart bot

**📖 Help:**
/help - This message"""
    
    await safe_edit(message, help_text)

# ═══════════════════════════════════════════════════════════════
#                      STARTUP
# ═══════════════════════════════════════════════════════════════

async def start_bot():
    """Start the Telegram bot"""
    await app.start()
    
    me = await app.get_me()
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║            🤖 ARYAN'S USERBOT V5.2 STARTED                  ║
╠══════════════════════════════════════════════════════════════╣
║  User: {me.first_name} (@{me.username or 'N/A'})
║  ID: {me.id}
║  Status: {'🟢 ACTIVE' if is_bot_active() else '🔴 INACTIVE'}
║  Database: {'✅ Connected' if db else '⚠️ Memory Only'}
║  Gemini Keys: {len(get_all_gemini_keys())}
║  VIPs: {len(get_all_vips())}
║  Stickers: {len(get_all_stickers())}
║  Web Port: {os.environ.get('PORT', 10000)}
║  
║  🌐 Web: http://localhost:{os.environ.get('PORT', 10000)}
║  📊 Health: /health
║  🏓 Ping: /ping
╚══════════════════════════════════════════════════════════════╝
    """)
    
    log_action("Bot started")
    await send_log(f"🚀 V5.2 Started!\n\n👤 {me.first_name}\n{'🟢 ACTIVE' if is_bot_active() else '🔴 INACTIVE'}")
    
    await idle()
    await app.stop()

# ═══════════════════════════════════════════════════════════════
#                      MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║            🚀 Starting Aryan's Userbot V5.2                 ║
║                  ALL FEATURES INCLUDED                       ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Start Flask web server in background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"✅ Web server started on port {os.environ.get('PORT', 10000)}")
    
    # Start Telegram bot
    try:
        asyncio.get_event_loop().run_until_complete(start_bot())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        traceback.print_exc()
    finally:
        if mongo_client:
            mongo_client.close()
        logger.info("Bot stopped")
