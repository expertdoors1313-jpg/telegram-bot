from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, json, os, yt_dlp, asyncio
from flask import Flask, request, render_template_string, redirect
import threading

# === CONFIGURATION ===
API_TOKEN = '1225837141:AAFv8u-823rLHEJBHOaEM9yt6GrWIhdnld0'
ADMIN_ID = 1092173352  # O'zingizning Telegram ID'ingizni kiriting
CONFIG_FILE = 'config.json'

# === TELEGRAM BOT SETUP ===
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# === DATABASE FUNCTIONS ===
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, full_name, username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, full_name, username)
        VALUES (?, ?, ?)
    ''', (user_id, full_name, username))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return [u[0] for u in users]

def get_user_count():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# === CONFIG FUNCTIONS ===
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"required_channel": ""}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# === TELEGRAM HANDLERS ===
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    config = load_config()
    channel = config.get("required_channel")
    if channel:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=message.from_user.id)
            if member.status not in ['member', 'creator', 'administrator']:
                raise Exception()
        except:
            join_button = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Kanalga a'zo bo'lish", url=f"https://t.me/{channel.replace('@', '')}"),
                InlineKeyboardButton("♻️ Tekshirish", callback_data="check_sub")
            )
            await message.answer("👋 Botdan foydalanish uchun kanalga a'zo bo'ling!", reply_markup=join_button)
            return
    await message.answer("🎯 Link yuboring (YouTube, Instagram, TikTok, Pinterest)...")

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    config = load_config()
    channel = config.get("required_channel")
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=call.from_user.id)
        if member.status in ['member', 'creator', 'administrator']:
            await call.message.delete()
            await call.message.answer("✅ Rahmat! Endi botdan foydalanishingiz mumkin.")
        else:
            raise Exception()
    except:
        await call.answer("❗ Hali a'zo emassiz!", show_alert=True)

@dp.message_handler(commands=["setchannel"])
async def set_channel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ Siz admin emassiz.")
    try:
        _, channel = message.text.split(maxsplit=1)
        config = load_config()
        config["required_channel"] = channel
        save_config(config)
        await message.reply(f"✅ Majburiy kanal o'rnatildi: {channel}")
    except:
        await message.reply("❗ Foydalanish: /setchannel @kanal_username")

@dp.message_handler(commands=["broadcast"])
async def broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("❌ Siz admin emassiz.")
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await message.reply("❗ Xabar matnini yozing: /broadcast matn")
    users = get_all_users()
    sent = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.1)
        except:
            continue
    await message.reply(f"✅ {sent} foydalanuvchiga yuborildi.")

@dp.message_handler()
async def downloader(message: types.Message):
    url = message.text.strip()
    await message.reply("⏳ Yuklab olinmoqda...")
    try:
        ydl_opts = {
            'outtmpl': 'media.%(ext)s',
            'format': 'best',
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            filename = f'media.{ext}'
            caption = info.get("title", "")
            if info.get("thumbnails"):
                await message.reply_video(open(filename, "rb"), caption=caption)
            else:
                await message.reply_document(open(filename, "rb"))
            os.remove(filename)
    except Exception as e:
        await message.reply("❌ Xatolik: " + str(e))

# === FLASK WEB ADMIN PANEL ===
app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Bot Admin Panel</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        input[type="text"], textarea { width: 100%; padding: 8px; margin: 5px 0; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h2>📊 Bot Admin Panel</h2>
    <p><strong>👥 Foydalanuvchilar soni:</strong> {{ user_count }}</p>

    <form method="POST" action="/setchannel">
        <h3>🔧 Majburiy kanalni sozlash</h3>
        <input type="text" name="channel" placeholder="@kanal_username" value="{{ current_channel }}">
        <button type="submit">Saqlash</button>
    </form>

    <form method="POST" action="/broadcast">
        <h3>📤 Xabar yuborish (broadcast)</h3>
        <textarea name="message" rows="5" placeholder="Xabar matnini kiriting..."></textarea>
        <button type="submit">Yuborish</button>
    </form>
</body>
</html>
'''

@app.route("/", methods=["GET"])
def index():
    config = load_config()
    return render_template_string(HTML, user_count=get_user_count(), current_channel=config.get("required_channel", ""))

@app.route("/setchannel", methods=["POST"])
def set_channel_web():
    channel = request.form.get("channel")
    config = load_config()
    config["required_channel"] = channel
    save_config(config)
    return redirect("/")

@app.route("/broadcast", methods=["POST"])
def broadcast_web():
    message = request.form.get("message")
    if not message:
        return redirect("/")
    users = get_all_users()
    async def send_broadcast():
        for user_id in users:
            try:
                await bot.send_message(user_id, message)
                await asyncio.sleep(0.1)
            except:
                continue
    asyncio.run(send_broadcast())
    return redirect("/")

def start_flask():
    app.run(port=8080)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=start_flask).start()
    executor.start_polling(dp)
