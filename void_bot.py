import telebot
import sqlite3
import requests
import base64
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

TOKEN = "8967274988:AAHhNBUjjAhCCUblV59wHplsy7-wh6vu-mA"
GROQ_KEY = "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"
ADMIN_ID = 1320676673
WEBHOOK_URL = "https://voidtradebot.pythonanywhere.com"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
DB = "void.db"

# Foydalanuvchi holatlari
states = {}

STRATEGIYALAR = [
    ("📐 SMC", "smc", "Smart Money Concepts: Market Structure (BOS/CHoCH), Order Blocks, FVG, Liquidity zones, Premium/Discount, POI"),
    ("📊 ICT", "ict", "ICT: Killzones, PD Arrays, Judas Swing, OTE, Turtle Soup, Silver Bullet, IPDA"),
    ("🔄 CRT", "crt", "Candle Range Theory: Previous candle high/low, CRT setup, displacement, internal/external range liquidity"),
    ("💧 Likvidlik", "liq", "Liquidity Hunt: BSL/SSL, equal highs/lows, stop hunt, inducement, liquidity sweep"),
    ("🧲 Magnet", "mag", "Magnet Theory: Price attraction to unfilled gaps, imbalances, psychological levels"),
    ("📏 S&R", "snr", "Support & Resistance: Key levels, flip zones, historical S/R, round numbers"),
    ("📈 Trend", "trend", "Trend Following: HH/HL uptrend, LH/LL downtrend, trendlines, pullback entries"),
    ("🕯 Kandel", "kandel", "Candlestick Patterns: Pin bar, engulfing, doji, hammer, shooting star"),
    ("📉 Pattern", "pattern", "Chart Patterns: Head & Shoulders, Double top/bottom, Triangle, Flag, Wedge"),
    ("⚡ Breakout", "breakout", "Breakout & Retest: Key level breaks, volume confirmation, retest entries"),
    ("〽️ EMA/MA", "ema", "Moving Averages: EMA 8/21/50/200 crossover, golden/death cross"),
    ("📊 RSI", "rsi", "RSI: Divergence, overbought/oversold, structure breaks, failure swings"),
    ("💹 MACD", "macd", "MACD: Signal line crossover, histogram divergence, zero line cross"),
    ("🎯 Fibonacci", "fib", "Fibonacci: 0.382/0.5/0.618/0.786 retracement, 1.272/1.618 extension"),
    ("📉 Bollinger", "bb", "Bollinger Bands: Squeeze breakout, mean reversion, band bounce"),
    ("🔢 Volume", "vol", "Volume Analysis: VWAP, volume profile, volume divergence, climax volume"),
    ("⏰ Sessiya", "session", "Session Trading: Asian/London/NY opens, killzones, session high/low sweeps"),
    ("🌊 Wyckoff", "wyckoff", "Wyckoff: Accumulation/Distribution phases, Spring, UTAD, composite operator"),
    ("🔁 Mean Rev", "mean", "Mean Reversion: Overextended moves, return to mean, statistical extremes"),
    ("📦 Range", "range", "Range Trading: Consolidation zones, range high/low, midpoint, breakout"),
    ("🏹 Scalping", "scalp", "Scalping: 1-5 min momentum, quick entries, order flow, micro structure"),
    ("⚡ CK", "ck", "CK Strategy: Consolidation & Breakout, accumulation detection, volume confirmation"),
]

DARAJALAR = [
    (0, "🌱 Yangi Boshlovchi"),
    (201, "📈 O'rta Treyder"),
    (501, "💼 Pro Treyder"),
    (1001, "🔥 Senior Treyder"),
    (2001, "👑 Master Treyder"),
]

def daraja(ball):
    d = DARAJALAR[0][1]
    for min_b, nom in DARAJALAR:
        if ball >= min_b:
            d = nom
    return d

# ===== DB =====
def db_yaratish():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, ism TEXT, ball INTEGER DEFAULT 0,
        tahlil_soni INTEGER DEFAULT 0, togri_soni INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0, oxirgi_kun TEXT DEFAULT '',
        sana TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT, matn TEXT,
        rasm TEXT, sana TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.commit(); c.close()

def user_qosh(uid, ism):
    c = sqlite3.connect(DB)
    c.execute("INSERT OR IGNORE INTO users VALUES(?,?,0,0,0,0,'',CURRENT_TIMESTAMP)", (uid, ism))
    c.commit(); c.close()

def user_olish(uid):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    c.close(); return r

def ball_qosh(uid, ball, togri=False):
    from datetime import datetime, date
    bugun = str(date.today())
    c = sqlite3.connect(DB)
    u = c.execute("SELECT streak, oxirgi_kun, ball FROM users WHERE user_id=?", (uid,)).fetchone()
    if u:
        streak = u[0]
        oxirgi = u[1]
        # Streak hisoblash
        if oxirgi == bugun:
            pass  # Bugun allaqachon kirgan
        elif oxirgi == str(date.fromordinal(date.today().toordinal()-1)):
            streak += 1  # Kecha ham kirgan, streak davom etadi
        else:
            streak = 1  # Yangi streak
        
        # 7 kunlik streak bonusi
        streak_bonus = 50 if streak % 7 == 0 and streak > 0 else 0
        
        c.execute("""UPDATE users SET 
            ball=ball+?, tahlil_soni=tahlil_soni+1, 
            togri_soni=togri_soni+?,
            streak=?, oxirgi_kun=?
            WHERE user_id=?""",
            (ball + streak_bonus, 1 if togri else 0, streak, bugun, uid))
        c.commit()
        c.close()
        return streak, streak_bonus
    c.close()
    return 1, 0

def top_olish():
    c = sqlite3.connect(DB)
    r = c.execute("SELECT ism, ball, tahlil_soni, togri_soni, streak FROM users ORDER BY ball DESC LIMIT 10").fetchall()
    c.close(); return r

def barcha_userlar():
    c = sqlite3.connect(DB)
    r = c.execute("SELECT user_id FROM users").fetchall()
    c.close(); return [x[0] for x in r]

def jami_user():
    c = sqlite3.connect(DB)
    n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    c.close(); return n

# ===== VOID AI =====
def void_groq(prompt, rasm_b64=None):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    
    void_shaxsiyat = """Sen "Void" - tajribali, aqlli va hazilkash treyder do'stsan.
Sening shaxsiyating:
- Ba'zan qattiq va to'g'riso'z: "Yo'q, bu trade menga yoqmayapti 🚫"
- Ba'zan hazilkash: "Buni kim o'rgatdi senga? 😂 Hazil hazil..."  
- Ba'zan maqtaysan: "Voy, bu yomon emas! Sen o'sib qolyapsan 🔥"
- Doim savol berasan, suhbatni davom ettirasan
- O'zbek tilida gaplashasan, lekin trading terminlarni inglizcha aytasan
- Qisqa va aniq gaplashasan, ko'p yozma
- Emoji ishlatasan lekin ko'p emas
- Do'st kabi gaplash, rasmiy emas"""

    if rasm_b64:
        messages = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{rasm_b64}"}},
            {"type": "text", "text": f"{void_shaxsiyat}\n\nFoydalanuvchi bu grafikni yubordi va dedi: '{prompt}'\n\nGrafikni ko'rib, do'st treyder sifatida javob ber. Savol ber, suhbatni davom ettir."}
        ]}]
        model = "meta-llama/llama-4-scout-17b-16e-instruct"
    else:
        messages = [
            {"role": "system", "content": void_shaxsiyat},
            {"role": "user", "content": prompt}
        ]
        model = "llama3-8b-8192"
    
    data = {"model": model, "messages": messages, "max_tokens": 500}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=data, timeout=45)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Uzr, hozir javob bera olmayapman 😅 ({str(e)[:50]})"

def void_strategiya(strategiya_nomi, desc, rasm_b64, user_fikr=""):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""Sen "Void" - tajribali SMC/ICT treyder do'stsan. O'zbek tilida gaplash.

Foydalanuvchi {strategiya_nomi} strategiyasi bo'yicha tahlil so'radi.
{f"Uning fikri: {user_fikr}" if user_fikr else ""}

{strategiya_nomi} usulida ({desc}) grafikni tahlil qil.

Javob formati - do'st sifatida, qisqa:
- Nima ko'ryapsan (2-3 gap)
- Muhim darajalar
- Signal: BUY/SELL/WAIT va sababi
- Oxirida 1 ta savol ber

Hazilkash va do'stona bo'l."""

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{rasm_b64}"}},
        {"type": "text", "text": prompt}
    ]}]
    data = {"model": "meta-llama/llama-4-scout-17b-16e-instruct", "messages": messages, "max_tokens": 600}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=data, timeout=45)
        javob = r.json()["choices"][0]["message"]["content"]
        signal = "WAIT"
        if "BUY" in javob.upper(): signal = "BUY"
        elif "SELL" in javob.upper(): signal = "SELL"
        return javob, signal
    except Exception as e:
        return f"Xatolik 😅", "WAIT"

def void_umumiy(tahlillar, rasm_b64):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    tahlil_matn = "\n".join([f"{k}: {v[:200]}" for k, v in tahlillar.items()])
    
    prompt = f"""Sen "Void" treyder do'stsan. O'zbek tilida.

Quyidagi tahlillarni ko'rib, FINAL xulosani ber:
{tahlil_matn}

Javob:
- Barcha tahlillar nima deyapti (qisqa)
- FINAL: BUY / SELL / WAIT
- Entry, SL, TP darajalari
- Ishonch: X%
- Oxirida qisqa hazil yoki motivatsiya"""

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{rasm_b64}"}},
        {"type": "text", "text": prompt}
    ]}]
    data = {"model": "meta-llama/llama-4-scout-17b-16e-instruct", "messages": messages, "max_tokens": 700}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=data, timeout=60)
        javob = r.json()["choices"][0]["message"]["content"]
        signal = "WAIT"
        if "BUY" in javob.upper(): signal = "BUY"
        elif "SELL" in javob.upper(): signal = "SELL"
        return javob, signal
    except:
        return "Xatolik 😅", "WAIT"

# ===== KLAVIATURALAR =====
def bosh_kb(uid):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 Signallar", callback_data="signals"),
        InlineKeyboardButton("🤖 AI Tahlil", callback_data="ai_start"),
    )
    kb.add(
        InlineKeyboardButton("👤 Profilim", callback_data="profil"),
        InlineKeyboardButton("🏆 Reyting", callback_data="top"),
    )
    if uid == ADMIN_ID:
        kb.add(InlineKeyboardButton("👑 Admin", callback_data="admin"))
    return kb

def strategiya_kb(qilinganlar=[]):
    kb = InlineKeyboardMarkup(row_width=3)
    tugmalar = []
    for nom, kod, _ in STRATEGIYALAR:
        belgi = "✅" if kod in qilinganlar else ""
        tugmalar.append(InlineKeyboardButton(f"{belgi}{nom}", callback_data=f"str_{kod}"))
    kb.add(*tugmalar)
    if qilinganlar:
        kb.add(InlineKeyboardButton("🔮 UMUMIY TAHLIL", callback_data="umumiy"))
    kb.add(InlineKeyboardButton("🔙 Menu", callback_data="menu"))
    return kb

def taxmin_kb():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("🟢 BUY", callback_data="tax_BUY"),
        InlineKeyboardButton("🔴 SELL", callback_data="tax_SELL"),
        InlineKeyboardButton("🟡 WAIT", callback_data="tax_WAIT"),
    )
    return kb

def orqaga_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Menu", callback_data="menu"))
    return kb

# ===== HANDLERLAR =====
@bot.message_handler(commands=["start"])
def start(m):
    user_qosh(m.from_user.id, m.from_user.first_name)
    bot.send_message(m.chat.id,
        f"Salom *{m.from_user.first_name}*! 👋\n\n"
        f"Men *Void* — trading do'sting 🤖\n\n"
        f"Grafik yubor, birga tahlil qilamiz.\n"
        f"Signal so'ra, maslahat beraman.\n"
        f"Noto'g'ri kirsang, to'xtataman 😄\n\n"
        f"Nima qilmoqchisan? 👇",
        parse_mode="Markdown", reply_markup=bosh_kb(m.from_user.id))

@bot.message_handler(func=lambda m: True, content_types=["text"])
def matn_qabul(m):
    if m.text.startswith("/"): return
    user_qosh(m.from_user.id, m.from_user.first_name)
    uid = m.from_user.id
    
    # Foydalanuvchi matn yozsa, Void javob beradi
    javob = void_groq(m.text)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🤖 Grafik tahlil", callback_data="ai_start"),
        InlineKeyboardButton("🔙 Menu", callback_data="menu")
    )
    bot.send_message(m.chat.id, javob, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "menu")
def menu(c):
    bot.edit_message_text("Nima qilmoqchisan? 👇",
        c.message.chat.id, c.message.message_id,
        reply_markup=bosh_kb(c.from_user.id))
    bot.answer_callback_query(c.id)

# ===== PROFIL =====
@bot.callback_query_handler(func=lambda c: c.data == "profil")
def profil(c):
    u = user_olish(c.from_user.id)
    if not u: return
    _, ism, ball, tahlil, togri, streak, _, _ = u
    aniqlik = round(togri/tahlil*100) if tahlil > 0 else 0
    d = daraja(ball)
    
    # Keyingi daraja
    keyingi = None
    for min_b, nom in DARAJALAR:
        if ball < min_b:
            keyingi = (min_b, nom)
            break
    
    keyingi_matn = f"📈 Keyingi: *{keyingi[1]}* — {keyingi[0]-ball} ball" if keyingi else "👑 Eng yuqori daraja!"
    
    bot.edit_message_text(
        f"👤 *{ism}*\n\n"
        f"🎖 *{d}*\n"
        f"⭐ Ball: *{ball}*\n"
        f"🔥 Streak: *{streak} kun*\n\n"
        f"📊 Tahlillar: *{tahlil}*\n"
        f"✅ To'g'ri: *{togri}*\n"
        f"🎯 Aniqlik: *{aniqlik}%*\n\n"
        f"{keyingi_matn}\n\n"
        f"💡 To'g'ri taxmin: *+20 ball*\n"
        f"📊 Tahlil: *+5 ball*\n"
        f"🔥 7 kun streak: *+50 ball*",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

# ===== REYTING =====
@bot.callback_query_handler(func=lambda c: c.data == "top")
def top(c):
    t = top_olish()
    n = jami_user()
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    matn = f"🏆 *TOP 10*\n👥 Jami: *{n}* ta\n\n"
    for i, (ism, ball, tahlil, togri, streak) in enumerate(t):
        aniqlik = round(togri/tahlil*100) if tahlil > 0 else 0
        matn += f"{medals[i]} *{ism}*\n⭐{ball} | 🎯{aniqlik}% | 🔥{streak}kun\n\n"
    bot.edit_message_text(matn, c.message.chat.id, c.message.message_id,
                          parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

# ===== SIGNALLAR =====
@bot.callback_query_handler(func=lambda c: c.data == "signals")
def signals(c):
    conn = sqlite3.connect(DB)
    oxirgi = conn.execute("SELECT matn, rasm, sana FROM signals ORDER BY id DESC LIMIT 3").fetchall()
    conn.close()
    if not oxirgi:
        bot.edit_message_text("📊 Hozircha signal yo'q ⏳\nVoid tez orada yuboradi!",
            c.message.chat.id, c.message.message_id, reply_markup=orqaga_kb())
        bot.answer_callback_query(c.id); return
    bot.edit_message_text("📊 *OXIRGI SIGNALLAR* 👇",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    for matn, rasm_b64, sana in oxirgi:
        try:
            if rasm_b64:
                rasm_bytes = base64.b64decode(rasm_b64)
                bot.send_photo(c.message.chat.id, rasm_bytes,
                               caption=f"🕐 {sana[:16]}\n\n{matn}", parse_mode="Markdown")
            else:
                bot.send_message(c.message.chat.id, f"🕐 {sana[:16]}\n\n{matn}", parse_mode="Markdown")
        except: pass
    bot.answer_callback_query(c.id)

# ===== AI TAHLIL =====
@bot.callback_query_handler(func=lambda c: c.data == "ai_start")
def ai_start(c):
    states[c.from_user.id] = {"photo": None, "tahlillar": {}, "ai_signal": None, "user_fikr": ""}
    bot.edit_message_text(
        "🤖 Grafik rasmini yubor!\n\n"
        "Rasm bilan birga o'z fikringni ham yoz:\n"
        "_'BUY deb o'ylayman chunki...'_\n\n"
        "Yoki faqat rasm ham bo'ladi 👇",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

@bot.message_handler(content_types=["photo"])
def rasm_qabul(m):
    user_qosh(m.from_user.id, m.from_user.first_name)
    uid = m.from_user.id
    msg = bot.send_message(m.chat.id, "⏳ Void grafikni ko'ryapti...")
    try:
        file_id = m.photo[-1].file_id
        file_info = bot.get_file(file_id)
        rasm = bot.download_file(file_info.file_path)
        rasm_b64 = base64.b64encode(rasm).decode("utf-8")
        user_fikr = m.caption or ""
        
        qilinganlar = states.get(uid, {}).get("tahlillar", {})
        states[uid] = {"photo": rasm_b64, "tahlillar": qilinganlar, 
                       "ai_signal": None, "user_fikr": user_fikr}
        
        # Void birinchi reaktsiyasi
        void_reaktsiya = void_groq(
            f"Foydalanuvchi grafik yubordi. {f'Uning fikri: {user_fikr}' if user_fikr else 'Hech narsa demadi.'} "
            f"Qisqa reaktsiya ber va qaysi strategiyada tahlil qilishini so'ra.",
            rasm_b64
        )
        
        bot.delete_message(m.chat.id, msg.message_id)
        bot.send_message(m.chat.id, void_reaktsiya)
        bot.send_message(m.chat.id,
            "Qaysi strategiyada tahlil qilay? 👇",
            reply_markup=strategiya_kb(list(qilinganlar.keys())))
    except Exception as e:
        bot.edit_message_text(f"Xatolik 😅 {str(e)[:100]}", m.chat.id, msg.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("str_"))
def strategiya_tanlash(c):
    uid = c.from_user.id
    kod = c.data.replace("str_", "")
    if uid not in states or not states[uid].get("photo"):
        bot.answer_callback_query(c.id, "Avval rasm yubor!"); return

    nom, _, desc = next((x for x in STRATEGIYALAR if x[1] == kod), (kod, kod, ""))
    bot.answer_callback_query(c.id, f"⏳ {nom} tahlil...")
    bot.send_message(c.message.chat.id, f"*{nom}* bo'yicha tahlil qilyapman... ⏳",
                     parse_mode="Markdown")
    
    user_fikr = states[uid].get("user_fikr", "")
    javob, signal = void_strategiya(nom, desc, states[uid]["photo"], user_fikr)
    states[uid]["tahlillar"][kod] = f"{nom}: {javob}"
    states[uid]["ai_signal"] = signal
    
    qilinganlar = list(states[uid]["tahlillar"].keys())
    bot.send_message(c.message.chat.id, javob, parse_mode="Markdown",
                     reply_markup=strategiya_kb(qilinganlar))

@bot.callback_query_handler(func=lambda c: c.data == "umumiy")
def umumiy(c):
    uid = c.from_user.id
    if uid not in states or not states[uid].get("tahlillar"):
        bot.answer_callback_query(c.id, "Avval strategiya tanlang!"); return
    
    bot.answer_callback_query(c.id, "⏳ Final tahlil...")
    bot.send_message(c.message.chat.id, "🔮 Hammani birga ko'ryapman... ⏳")
    
    javob, ai_signal = void_umumiy(states[uid]["tahlillar"], states[uid]["photo"])
    states[uid]["ai_signal"] = ai_signal
    
    signal_emoji = "🟢" if ai_signal == "BUY" else "🔴" if ai_signal == "SELL" else "🟡"
    
    bot.send_message(c.message.chat.id,
        f"{javob}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Void signal: *{signal_emoji} {ai_signal}*\n\n"
        f"Sen nima deysiz? Ball yig'ing! 👇",
        parse_mode="Markdown", reply_markup=taxmin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("tax_"))
def taxmin(c):
    uid = c.from_user.id
    user_signal = c.data.replace("tax_", "")
    ai_signal = states.get(uid, {}).get("ai_signal", "WAIT")
    
    togri = user_signal == ai_signal
    ball = 20 if togri else 5
    streak, streak_bonus = ball_qosh(uid, ball, togri)
    
    if togri:
        matn = f"🎉 To'g'ri! *+{ball} ball*"
        if streak_bonus:
            matn += f"\n🔥 *+{streak_bonus} bonus* — {streak} kunlik streak!"
        matn += f"\n\nVoid ham shunday dedi 😄"
    else:
        matn = f"❌ Noto'g'ri, lekin *+{ball} ball*\n\nVoid: *{ai_signal}* degan edi... Keyingi safar 💪"
    
    states.pop(uid, None)
    bot.edit_message_text(matn, c.message.chat.id, c.message.message_id,
                          parse_mode="Markdown", reply_markup=bosh_kb(uid))
    bot.answer_callback_query(c.id)

# ===== ADMIN =====
@bot.callback_query_handler(func=lambda c: c.data == "admin")
def admin(c):
    if c.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📢 Signal yuborish", callback_data="signal_yubor"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stat"),
        InlineKeyboardButton("🔙 Menu", callback_data="menu"),
    )
    bot.edit_message_text(f"👑 *ADMIN*\n\n👥 Jami: *{jami_user()}* ta",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_stat")
def admin_stat(c):
    if c.from_user.id != ADMIN_ID: return
    bot.edit_message_text(f"📊 Foydalanuvchilar: *{jami_user()}* ta",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "signal_yubor")
def signal_yubor(c):
    if c.from_user.id != ADMIN_ID: return
    bot.send_message(c.message.chat.id,
        "📢 Rasm + matn yuboring (caption ga yozing)\nYoki faqat matn 👇")
    bot.register_next_step_handler(c.message, admin_signal_qabul)
    bot.answer_callback_query(c.id)

def admin_signal_qabul(m):
    if m.from_user.id != ADMIN_ID: return
    userlar = barcha_userlar()
    yuborildi = 0
    rasm_b64 = None
    
    if m.content_type == "photo":
        matn = m.caption or "📊 Yangi signal!"
        file_info = bot.get_file(m.photo[-1].file_id)
        rasm_bytes = bot.download_file(file_info.file_path)
        rasm_b64 = base64.b64encode(rasm_bytes).decode("utf-8")
    else:
        matn = m.text or "📊 Yangi signal!"

    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO signals(matn, rasm) VALUES(?,?)", (matn, rasm_b64))
    conn.commit(); conn.close()

    for uid in userlar:
        try:
            if rasm_b64:
                bot.send_photo(uid, base64.b64decode(rasm_b64),
                    caption=f"🔔 *YANGI SIGNAL!*\n\n{matn}", parse_mode="Markdown")
            else:
                bot.send_message(uid, f"🔔 *YANGI SIGNAL!*\n\n{matn}", parse_mode="Markdown")
            yuborildi += 1
        except: pass

    bot.send_message(m.chat.id, f"✅ *{yuborildi}* ta foydalanuvchiga yuborildi!",
        parse_mode="Markdown", reply_markup=bosh_kb(ADMIN_ID))

# ===== WEBHOOK =====
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Void Trade Bot ishlayapti! 🤖"

if __name__ == "__main__":
    db_yaratish()
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    print("✅ VOID BOT webhook bilan ishga tushdi!")
    app.run(host="0.0.0.0", port=5000)
