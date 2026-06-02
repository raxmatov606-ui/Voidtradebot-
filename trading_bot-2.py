import telebot, sqlite3, requests, base64
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8967274988:AAHhNBUjjAhCCUblV59wHplsy7-wh6vu-mA"
GROQ_KEY = "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"
ADMIN_ID = 1320676673
bot = telebot.TeleBot(TOKEN)
DB = "trading.db"

# Foydalanuvchi holatlari (rasm va tahlillarni saqlash)
states = {}

STRATEGIYALAR = [
    ("📐 SMC",      "smc",     "Smart Money Concepts: Market Structure (BOS/CHoCH), Order Blocks, FVG, Liquidity zones, Premium/Discount, POI, Mitigation"),
    ("📊 ICT",      "ict",     "ICT Inner Circle Trader: Killzones (London/NY/Asia), PD Arrays, Judas Swing, OTE, Turtle Soup, Silver Bullet, IPDA"),
    ("🔄 CRT",      "crt",     "Candle Range Theory: Previous candle high/low range, CRT setup, displacement, internal/external range liquidity sweep"),
    ("💧 Likvidlik","liq",     "Liquidity Hunt: BSL/SSL equal highs/lows, stop hunt zones, inducement levels, liquidity sweep, void fills"),
    ("🧲 Magnet",   "mag",     "Magnet Theory: Price attraction to unfilled gaps, imbalances, psychological round numbers, open gaps"),
    ("📏 S&R",      "snr",     "Support & Resistance: Key historical levels, flip zones, structure levels, round numbers, daily/weekly levels"),
    ("📈 Trend",    "trend",   "Trend Following: HH/HL uptrend, LH/LL downtrend, trendlines, trend channels, pullback entries"),
    ("🕯 Kandel",   "kandel",  "Candlestick Patterns: Pin bar, engulfing, doji, hammer, shooting star, morning/evening star, inside bar"),
    ("📉 Pattern",  "pattern", "Chart Patterns: Head & Shoulders, Double top/bottom, Triangle, Flag, Wedge, Cup & Handle, pennant"),
    ("⚡ Breakout", "breakout","Breakout & Retest: Key level breaks, volume confirmation, retest entries, failed breakouts, fakeouts"),
    ("〽️ EMA/MA",  "ema",     "Moving Averages: EMA 8/21/50/200 crossover, golden/death cross, dynamic S/R, ribbon analysis"),
    ("📊 RSI",      "rsi",     "RSI: Regular/hidden divergence, overbought(70+)/oversold(30-), structure breaks, failure swings"),
    ("💹 MACD",     "macd",    "MACD: Signal line crossover, histogram divergence, zero line cross, momentum shifts"),
    ("🎯 Fibonacci","fib",     "Fibonacci: 0.382/0.5/0.618/0.786 retracement, 1.272/1.618 extension, confluence zones"),
    ("📉 Bollinger","bb",      "Bollinger Bands: Squeeze breakout, mean reversion, upper/lower band bounce, band expansion"),
    ("🔢 Volume",   "vol",     "Volume Analysis: High/low volume nodes, VWAP, volume profile, volume divergence, climax volume"),
    ("⏰ Sessiya",  "session", "Session Trading: Asian/London/NY opens, killzones, overlap sessions, session high/low sweeps"),
    ("🌊 Wyckoff",  "wyckoff", "Wyckoff: Accumulation/Distribution phases, Spring, UTAD, cause & effect, composite operator logic"),
    ("🔁 Mean Rev", "mean",    "Mean Reversion: Overextended moves, return to mean, statistical extremes, standard deviation"),
    ("📦 Range",    "range",   "Range Trading: Consolidation zones, range high/low, midpoint, range breakout vs continuation"),
    ("🏹 Scalping", "scalp",   "Scalping: 1-5 min momentum, quick entries/exits, spread awareness, order flow, micro structure"),
    ("⚡ CK",       "ck",      "CK Strategy: Consolidation & Breakout, accumulation detection, volume confirmation, entry timing"),
]

DARAJALAR = [
    (0,    "🌱 Yangi Boshlovchi"),
    (201,  "📈 O'rta Treyder"),
    (501,  "💼 Pro Treyder"),
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
        sana TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT, matn TEXT,
        rasm TEXT, sana TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS predictions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        ai_signal TEXT, user_signal TEXT, togri INTEGER DEFAULT 0,
        sana TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.commit(); c.close()

def user_qosh(uid, ism):
    c = sqlite3.connect(DB)
    c.execute("INSERT OR IGNORE INTO users VALUES(?,?,0,0,0,CURRENT_TIMESTAMP)", (uid, ism))
    c.commit(); c.close()

def user_olish(uid):
    c = sqlite3.connect(DB)
    r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    c.close(); return r

def ball_qosh(uid, ball, togri=False):
    c = sqlite3.connect(DB)
    c.execute("UPDATE users SET ball=ball+?, tahlil_soni=tahlil_soni+1, togri_soni=togri_soni+? WHERE user_id=?",
              (ball, 1 if togri else 0, uid))
    c.commit(); c.close()

def top_olish():
    c = sqlite3.connect(DB)
    r = c.execute("SELECT ism, ball, tahlil_soni, togri_soni FROM users ORDER BY ball DESC LIMIT 10").fetchall()
    c.close(); return r

def barcha_userlar():
    c = sqlite3.connect(DB)
    r = c.execute("SELECT user_id FROM users").fetchall()
    c.close(); return [x[0] for x in r]

def jami_user():
    c = sqlite3.connect(DB)
    n = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    c.close(); return n

def prediction_saqlash(uid, ai_s, user_s, togri):
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO predictions(user_id,ai_signal,user_signal,togri) VALUES(?,?,?,?)",
              (uid, ai_s, user_s, togri))
    c.commit(); c.close()

# ===== GROQ AI =====
def groq_tahlil(strategiya_nomi, strategiya_desc, rasm_b64):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    prompt = f"""Sen professional trading analistisan. Faqat o'zbek tilida javob ber.

Strategiya: {strategiya_nomi}
Tahlil usuli: {strategiya_desc}

Ushbu grafik rasmini {strategiya_nomi} strategiyasi asosida chuqur tahlil qil.

Javob formati:
📊 **{strategiya_nomi} TAHLILI**

🔍 **Ko'rilgan narsalar:**
[nima ko'ryapsan]

📍 **Muhim darajalar:**
[darajalar]

📈 **Trend:**
[trend yo'nalishi]

🎯 **Signal:**
BUY / SELL / WAIT

💡 **Sabab:**
[nima uchun]

⚠️ **Ehtiyot:**
[xavf]"""

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{rasm_b64}"}},
        {"type": "text", "text": prompt}
    ]}]
    data = {"model": "meta-llama/llama-4-scout-17b-16e-instruct", "messages": messages, "max_tokens": 1500}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers=headers, json=data, timeout=45)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ Xatolik: {str(e)}"

def groq_umumiy(tahlillar_dict, rasm_b64):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    tahlil_matn = "\n\n".join([f"=== {k} ===\n{v}" for k, v in tahlillar_dict.items()])
    prompt = f"""Sen professional trading analistisan. Faqat o'zbek tilida javob ber.

Quyida bir nechta strategiyalar bo'yicha tahlillar berilgan:

{tahlil_matn}

Barcha tahlillarni hisobga olib UMUMIY xulosani ber.

Javob formati:
🔮 **UMUMIY TAHLIL**

📊 **Strategiyalar xulosasi:**
[har bir strategiyani qisqacha]

🎯 **FINAL SIGNAL: BUY / SELL / WAIT**

💰 **Entry zona:**
[narx oralig'i]

🛑 **Stop Loss:**
[daraja]

✅ **Take Profit:**
TP1: [daraja]
TP2: [daraja]
TP3: [daraja]

📊 **Ishonch darajasi:** [%]

💡 **Asosiy sabab:**
[nima uchun shu signal]"""

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{rasm_b64}"}},
        {"type": "text", "text": prompt}
    ]}]
    data = {"model": "meta-llama/llama-4-scout-17b-16e-instruct", "messages": messages, "max_tokens": 2000}
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                          headers=headers, json=data, timeout=60)
        javob = r.json()["choices"][0]["message"]["content"]
        # Final signalni aniqlash
        signal = "WAIT"
        if "FINAL SIGNAL: BUY" in javob or "**BUY**" in javob:
            signal = "BUY"
        elif "FINAL SIGNAL: SELL" in javob or "**SELL**" in javob:
            signal = "SELL"
        return javob, signal
    except Exception as e:
        return f"❌ Xatolik: {str(e)}", "WAIT"

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
        kb.add(InlineKeyboardButton("👑 Admin Panel", callback_data="admin"))
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
    kb.add(InlineKeyboardButton("🔙 Bosh menu", callback_data="menu"))
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
    kb.add(InlineKeyboardButton("🔙 Bosh menu", callback_data="menu"))
    return kb

# ===== HANDLERLAR =====
@bot.message_handler(commands=["start"])
def start(m):
    user_qosh(m.from_user.id, m.from_user.first_name)
    bot.send_message(m.chat.id,
        f"👋 Salom, *{m.from_user.first_name}*!\n\n"
        "📈 *Trading Signal Bot*\n\n"
        "🤖 AI grafik tahlili\n"
        "📊 Professional signallar\n"
        "🏆 Ball to'plash va reyting\n"
        "👤 Shaxsiy profil\n\n"
        "Quyidan tanlang 👇",
        parse_mode="Markdown", reply_markup=bosh_kb(m.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data == "menu")
def menu(c):
    bot.edit_message_text("📈 *Bosh Menu*\n\nNima qilmoqchisiz?",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=bosh_kb(c.from_user.id))
    bot.answer_callback_query(c.id)

# ===== PROFIL =====
@bot.callback_query_handler(func=lambda c: c.data == "profil")
def profil(c):
    u = user_olish(c.from_user.id)
    if not u:
        bot.answer_callback_query(c.id, "Avval /start bosing!"); return
    _, ism, ball, tahlil, togri, _ = u
    aniqlik = round(togri/tahlil*100) if tahlil > 0 else 0
    d = daraja(ball)
    bot.edit_message_text(
        f"👤 *PROFILINGIZ*\n\n"
        f"🏷 Ism: *{ism}*\n"
        f"🎖 Daraja: *{d}*\n"
        f"⭐ Ball: *{ball}*\n\n"
        f"📊 Jami tahlillar: *{tahlil}*\n"
        f"✅ To'g'ri taxminlar: *{togri}*\n"
        f"🎯 Aniqlik: *{aniqlik}%*\n\n"
        f"💡 To'g'ri taxmin qilsangiz *+20 ball*\n"
        f"📊 Tahlil qilsangiz *+5 ball*",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

# ===== REYTING =====
@bot.callback_query_handler(func=lambda c: c.data == "top")
def top(c):
    t = top_olish()
    n = jami_user()
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    matn = f"🏆 *TOP 10 TREYDERLAR*\n👥 Jami: *{n}* ta\n\n"
    for i, (ism, ball, tahlil, togri) in enumerate(t):
        aniqlik = round(togri/tahlil*100) if tahlil > 0 else 0
        matn += f"{medals[i]} *{ism}*\n⭐{ball} ball | 🎯{aniqlik}%\n\n"
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
        bot.edit_message_text("📊 *SIGNALLAR*\n\nHozircha signal yo'q ⏳",
            c.message.chat.id, c.message.message_id,
            parse_mode="Markdown", reply_markup=orqaga_kb())
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
    states[c.from_user.id] = {"photo": None, "tahlillar": {}, "ai_signal": None}
    bot.edit_message_text(
        "🤖 *AI GRAFIK TAHLILI*\n\n"
        "📸 Grafik rasmini yuboring!\n\n"
        "AI sizning rasmingizni tanlagan strategiyangiz asosida tahlil qiladi 👇",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

@bot.message_handler(content_types=["photo"])
def rasm_qabul(m):
    user_qosh(m.from_user.id, m.from_user.first_name)
    msg = bot.send_message(m.chat.id, "📥 Rasm qabul qilindi! Yuklanmoqda...")
    try:
        file_id = m.photo[-1].file_id
        file_info = bot.get_file(file_id)
        rasm = bot.download_file(file_info.file_path)
        rasm_b64 = base64.b64encode(rasm).decode("utf-8")
        qilinganlar = states.get(m.from_user.id, {}).get("tahlillar", {})
        states[m.from_user.id] = {"photo": rasm_b64, "tahlillar": qilinganlar, "ai_signal": None}
        bot.delete_message(m.chat.id, msg.message_id)
        bot.send_message(m.chat.id,
            "✅ *Rasm yuklandi!*\n\n"
            "Qaysi strategiya bo'yicha tahlil qilayim?\n"
            "Bir yoki bir nechta tanlang 👇",
            parse_mode="Markdown",
            reply_markup=strategiya_kb(list(qilinganlar.keys())))
    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}", m.chat.id, msg.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("str_"))
def strategiya_tanlash(c):
    uid = c.from_user.id
    kod = c.data.replace("str_", "")
    if uid not in states or not states[uid].get("photo"):
        bot.answer_callback_query(c.id, "Avval rasm yuboring!"); return

    # Strategiya nomini top
    nom, _, desc = next((x for x in STRATEGIYALAR if x[1] == kod), (kod, kod, ""))
    
    bot.answer_callback_query(c.id, f"⏳ {nom} tahlil qilinmoqda...")
    bot.send_message(c.message.chat.id, f"🤖 *{nom}* strategiyasi bo'yicha tahlil qilinmoqda... ⏳",
                     parse_mode="Markdown")
    
    javob = groq_tahlil(nom, desc, states[uid]["photo"])
    states[uid]["tahlillar"][kod] = f"{nom}:\n{javob}"
    
    qilinganlar = list(states[uid]["tahlillar"].keys())
    
    bot.send_message(c.message.chat.id, javob, parse_mode="Markdown",
                     reply_markup=strategiya_kb(qilinganlar))

@bot.callback_query_handler(func=lambda c: c.data == "umumiy")
def umumiy(c):
    uid = c.from_user.id
    if uid not in states or not states[uid].get("tahlillar"):
        bot.answer_callback_query(c.id, "Avval strategiya tanlang!"); return
    
    bot.answer_callback_query(c.id, "⏳ Umumiy tahlil qilinmoqda...")
    bot.send_message(c.message.chat.id, "🔮 *Barcha strategiyalar bo'yicha umumiy tahlil qilinmoqda...* ⏳",
                     parse_mode="Markdown")
    
    javob, ai_signal = groq_umumiy(states[uid]["tahlillar"], states[uid]["photo"])
    states[uid]["ai_signal"] = ai_signal
    
    signal_emoji = "🟢" if ai_signal == "BUY" else "🔴" if ai_signal == "SELL" else "🟡"
    
    bot.send_message(c.message.chat.id,
        f"{javob}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 *SIZNING TAXMININGIZ?*\n"
        f"AI signal: *{signal_emoji} {ai_signal}*\n\n"
        f"Siz nima deysiz? Ball yig'ing! 👇",
        parse_mode="Markdown", reply_markup=taxmin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("tax_"))
def taxmin(c):
    uid = c.from_user.id
    user_signal = c.data.replace("tax_", "")
    ai_signal = states.get(uid, {}).get("ai_signal", "WAIT")
    
    togri = user_signal == ai_signal
    ball = 20 if togri else 5
    ball_qosh(uid, ball, togri)
    prediction_saqlash(uid, ai_signal, user_signal, 1 if togri else 0)
    
    if togri:
        matn = (f"🎉 *TO'G'RI!* +{ball} ball!\n\n"
                f"✅ Sizning taxmin: *{user_signal}*\n"
                f"🤖 AI signal: *{ai_signal}*\n\n"
                f"Ajoyib tahlil! 💪")
    else:
        matn = (f"📊 *NOTO'G'RI*, lekin +{ball} ball!\n\n"
                f"❌ Sizning taxmin: *{user_signal}*\n"
                f"🤖 AI signal: *{ai_signal}*\n\n"
                f"Keyingi safar omad! 💪")
    
    states.pop(uid, None)
    bot.edit_message_text(matn, c.message.chat.id, c.message.message_id,
                          parse_mode="Markdown", reply_markup=bosh_kb(uid))
    bot.answer_callback_query(c.id)

# ===== RISK KALKULYATOR =====
@bot.message_handler(commands=["risk"])
def risk(m):
    try:
        _, dep, rsk, sl = m.text.split()
        dep, rsk, sl = float(dep), float(rsk), float(sl)
        risk_sum = dep * rsk / 100
        lot = risk_sum / (sl * 10)
        bot.send_message(m.chat.id,
            f"🧮 *RISK HISOB-KITOBI*\n\n"
            f"💰 Depozit: *${dep:,.2f}*\n"
            f"⚠️ Risk: *{rsk}%* = *${risk_sum:,.2f}*\n"
            f"📉 Stop Loss: *{sl} pip*\n"
            f"📦 Lot: *{lot:.2f}*\n\n"
            f"🎯 *Take Profit:*\n"
            f"TP1 (1.5R): {sl*1.5:.0f} pip = *${risk_sum*1.5:.2f}*\n"
            f"TP2 (2R):   {sl*2:.0f} pip = *${risk_sum*2:.2f}*\n"
            f"TP3 (3R):   {sl*3:.0f} pip = *${risk_sum*3:.2f}*",
            parse_mode="Markdown", reply_markup=orqaga_kb())
    except:
        bot.send_message(m.chat.id, "❌ Format: `/risk 1000 2 50`", parse_mode="Markdown")

# ===== ADMIN PANEL =====
@bot.callback_query_handler(func=lambda c: c.data == "admin")
def admin(c):
    if c.from_user.id != ADMIN_ID:
        bot.answer_callback_query(c.id, "❌ Ruxsat yo'q!"); return
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📢 Signal yuborish", callback_data="signal_yubor"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stat"),
        InlineKeyboardButton("🔙 Bosh menu", callback_data="menu"),
    )
    bot.edit_message_text(f"👑 *ADMIN PANEL*\n\n👥 Jami: *{jami_user()}* ta foydalanuvchi",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=kb)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "admin_stat")
def admin_stat(c):
    if c.from_user.id != ADMIN_ID: return
    n = jami_user()
    bot.edit_message_text(f"📊 *STATISTIKA*\n\n👥 Foydalanuvchilar: *{n}* ta",
        c.message.chat.id, c.message.message_id,
        parse_mode="Markdown", reply_markup=orqaga_kb())
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "signal_yubor")
def signal_yubor(c):
    if c.from_user.id != ADMIN_ID: return
    bot.send_message(c.message.chat.id,
        "📢 *SIGNAL YUBORISH*\n\n"
        "Rasm + matn yuboring:\n"
        "1. Rasmni tanlang\n"
        "2. Caption (izoh) ga signal matnini yozing\n"
        "3. Yuboring\n\n"
        "Yoki faqat matn yuboring 👇",
        parse_mode="Markdown")
    bot.register_next_step_handler(c.message, admin_signal_qabul)
    bot.answer_callback_query(c.id)

def admin_signal_qabul(m):
    if m.from_user.id != ADMIN_ID: return
    userlar = barcha_userlar()
    yuborildi = 0
    rasm_b64 = None
    
    if m.content_type == "photo":
        matn = m.caption or "📊 Yangi signal!"
        file_id = m.photo[-1].file_id
        file_info = bot.get_file(file_id)
        rasm_bytes = bot.download_file(file_info.file_path)
        rasm_b64 = base64.b64encode(rasm_bytes).decode("utf-8")
    else:
        matn = m.text or "📊 Yangi signal!"

    # DB ga saqlash
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO signals(matn, rasm) VALUES(?,?)", (matn, rasm_b64))
    conn.commit(); conn.close()

    for uid in userlar:
        try:
            if rasm_b64:
                rasm_bytes = base64.b64decode(rasm_b64)
                bot.send_photo(uid, rasm_bytes,
                    caption=f"🔔 *YANGI SIGNAL!*\n\n{matn}",
                    parse_mode="Markdown")
            else:
                bot.send_message(uid, f"🔔 *YANGI SIGNAL!*\n\n{matn}", parse_mode="Markdown")
            yuborildi += 1
        except: pass

    bot.send_message(m.chat.id,
        f"✅ Signal *{yuborildi}* ta foydalanuvchiga yuborildi!",
        parse_mode="Markdown", reply_markup=bosh_kb(ADMIN_ID))

print("✅ TRADING BOT ishga tushdi!")
db_yaratish()
bot.infinity_polling()
