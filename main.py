import yfinance as yf
import urllib.parse
import urllib.request
import json
import time

# --- PASTE YOURS HERE ---
BOT_TOKEN = "9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"
CHAT_ID = "6716644289"

SYMBOLS = {
    'GBPJPY': 'GBPJPY=X',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'XAUUSD': 'GC=F',
    'EURJPY': 'EURJPY=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
}

def display_name(sym):
    # GBPJPY -> GBP/JPY
    if sym == 'XAUUSD':
        return 'XAU/USD'
    return f"{sym[:3]}/{sym[3:]}"

def telegram_send(chat_id, message, buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data_dict = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    if buttons:
        # buttons = list of [text, callback_data]
        keyboard = []
        row = []
        for i, (txt, cb) in enumerate(buttons):
            row.append({"text": txt, "callback_data": cb})
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        data_dict['reply_markup'] = json.dumps({"inline_keyboard": keyboard})
    data = urllib.parse.urlencode(data_dict)
    req = urllib.request.Request(url, data.encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print("Send failed:", e)

def telegram_answer_callback(callback_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    data = urllib.parse.urlencode({'callback_query_id': callback_id})
    req = urllib.request.Request(url, data.encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except:
        pass

def telegram_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
    if offset:
        url += f"&offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
            return data.get("result", [])
    except Exception as e:
        print("Updates failed:", e)
        return []

def check_pair(symbol, yahoo_symbol):
    try:
        df = yf.download(yahoo_symbol, period="2d", interval="1m", progress=False)
        if df is None or len(df) < 60:
            return (symbol, "FLAT", f"{display_name(symbol)}: No data")
        try:
            df.columns = df.columns.droplevel(1)
        except:
            pass
        df['ma'] = df['Close'].rolling(50).mean()
        curr_close = float(df['Close'].iloc[-2])
        curr_ma = float(df['ma'].iloc[-2])
        ma_now = float(df['ma'].iloc[-2])
        ma_before = float(df['ma'].iloc[-2 - 3])

        if curr_close > curr_ma and ma_now > ma_before:
            return (symbol, "UP", f"⬆️ <b>{display_name(symbol)} : UP</b>\n\nPrice: {curr_close:.5f}\nAbove MA50, MA sloping UP\n\nTake BUY ✅")
        elif curr_close < curr_ma and ma_now < ma_before:
            return (symbol, "DOWN", f"⬇️ <b>{display_name(symbol)} : DOWN</b>\n\nPrice: {curr_close:.5f}\nBelow MA50, MA sloping DOWN\n\nTake SELL ✅")
        else:
            return (symbol, "FLAT", f"⚪ <b>{display_name(symbol)} : WAIT</b>\n\nPrice: {curr_close:.5f}\nMA not sloping clearly\n\nDon't trade now, wait ❌")
    except Exception as e:
        print("Check error", symbol, e)
        return (symbol, "ERROR", f"{display_name(symbol)}: Error")

def main_menu_buttons():
    btns = []
    for sym in SYMBOLS.keys():
        btns.append((f"{display_name(sym)}", sym))
    btns.append(("📊 ALL PAIRS", "ALL"))
    btns.append(("🔥 STRONG ONLY", "STRONG"))
    return btns

def send_main_menu(chat_id):
    msg = "<b>🔥 Welcome to IB BOT 🔥</b>\n\n<b>REAL MARKET - Not OTC</b>\n\nChoose a pair below 👇\nTap one and I will give you UP / DOWN now:"
    telegram_send(chat_id, msg, buttons=main_menu_buttons())

print("IB BOT - ARRXBOT Style - Running...")
telegram_send(CHAT_ID, "✅ <b>IB BOT Started</b>\nSend /start to see buttons.")
offset = None

while True:
    updates = telegram_updates(offset)
    for upd in updates:
        offset = upd["update_id"] + 1

        # --- BUTTON TAP ---
        if "callback_query" in upd:
            cb = upd["callback_query"]
            telegram_answer_callback(cb["id"])
            chat_id = cb["message"]["chat"]["id"]
            data = cb["data"]

            if data == "ALL":
                results = []
                for s, y in SYMBOLS.items():
                    _, status, result = check_pair(s, y)
                    # short version for ALL
                    if status == "UP":
                        results.append(f"⬆️ {display_name(s)} : UP")
                    elif status == "DOWN":
                        results.append(f"⬇️ {display_name(s)} : DOWN")
                    else:
                        results.append(f"⚪ {display_name(s)} : WAIT")
                reply = "<b>📊 ALL PAIRS - REAL</b>\n\n" + "\n".join(results) + "\n\nChoose again 👇"
                telegram_send(chat_id, reply, buttons=main_menu_buttons())

            elif data == "STRONG":
                strong = []
                for s, y in SYMBOLS.items():
                    _, status, result = check_pair(s, y)
                    if status in ["UP", "DOWN"]:
                        strong.append(result)
                if strong:
                    reply = "<b>🔥 STRONG ONLY - REAL</b>\n\n" + "\n\n".join(strong) + "\n\nChoose again 👇"
                else:
                    reply = "<b>⚪ No Strong Signal</b>\n\nAll pairs are WAIT. Don't trade now.\n\nChoose again 👇"
                telegram_send(chat_id, reply, buttons=main_menu_buttons())

            elif data in SYMBOLS:
                _, _, result = check_pair(data, SYMBOLS[data])
                reply = result + "\n\nChoose another pair 👇"
                telegram_send(chat_id, reply, buttons=main_menu_buttons())
            continue

        # --- TEXT MESSAGE ---
        msg = upd.get("message", {})
        text = msg.get("text", "").strip().lower().replace("/", "")
        chat_id = msg.get("chat", {}).get("id")
        if not text or not chat_id:
            continue

        if text in ["start", "help", "hi", "hello", "menu"]:
            send_main_menu(chat_id)
        elif text in ["signal", "all", "check"]:
            results = []
            for s, y in SYMBOLS.items():
                _, status, _ = check_pair(s, y)
                if status == "UP":
                    results.append(f"⬆️ {display_name(s)} : UP")
                elif status == "DOWN":
                    results.append(f"⬇️ {display_name(s)} : DOWN")
                else:
                    results.append(f"⚪ {display_name(s)} : WAIT")
            reply = "<b>📊 ALL PAIRS - REAL</b>\n\n" + "\n".join(results)
            telegram_send(chat_id, reply, buttons=main_menu_buttons())
        elif text.upper() in SYMBOLS:
            symbol = text.upper()
            _, _, result = check_pair(symbol, SYMBOLS[symbol])
            telegram_send(chat_id, result, buttons=main_menu_buttons())

    time.sleep(5)
