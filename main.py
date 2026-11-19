
import yfinance as yf
import urllib.parse
import urllib.request
import json
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- Fake web server so Render Web Service doesn't fail ---
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"IB BOT is running")
        def log_message(self, *a):
            pass
    try:
        HTTPServer(("0.0.0.0", port), H).serve_forever()
    except Exception as e:
        print("Web server error:", e)

threading.Thread(target=keep_alive, daemon=True).start()

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
    if sym == 'XAUUSD':
        return 'XAU/USD'
    return f"{sym[:3]}/{sym[3:]}"

def telegram_send(chat_id, message, buttons=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data_dict = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    if buttons:
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

def check_pair(symbol, yahoo_symbol, timeframe="5m"):
    try:
        # Faster: 1d is enough for MA50
        if timeframe == "5m":
            period = "1d"
            interval = "5m"
        else:
            period = "1d"
            interval = "1m"
        df = yf.download(yahoo_symbol, period=period, interval=interval, progress=False)
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
        label = "5min" if timeframe == "5m" else "1min"

        if curr_close > curr_ma and ma_now > ma_before:
            return (symbol, "UP", f"⬆️ <b>{display_name(symbol)} : UP - {label}</b>\n\nPrice: {curr_close:.5f}\nAbove MA50, MA sloping UP\n\nTake BUY for {label} ✅")
        elif curr_close < curr_ma and ma_now < ma_before:
            return (symbol, "DOWN", f"⬇️ <b>{display_name(symbol)} : DOWN - {label}</b>\n\nPrice: {curr_close:.5f}\nBelow MA50, MA sloping DOWN\n\nTake SELL for {label} ✅")
        else:
            return (symbol, "FLAT", f"⚪ <b>{display_name(symbol)} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nMA not sloping clearly\n\nDon't trade now, wait ❌")
    except Exception as e:
        print("Check error", symbol, e)
        return (symbol, "ERROR", f"{display_name(symbol)}: Error")

def timeframe_buttons():
    return [
        ("✅ 5min", "TF_5m"),
        ("1min", "TF_1m"),
    ]

def pair_buttons(timeframe):
    btns = []
    for sym in SYMBOLS.keys():
        btns.append((f"{display_name(sym)}", f"{timeframe}_{sym}"))
    btns.append((f"📊 ALL - {timeframe}", f"{timeframe}_ALL"))
    btns.append((f"🔥 STRONG - {timeframe}", f"{timeframe}_STRONG"))
    btns.append(("⬅️ Change Time", "BACK_TF"))
    return btns

def send_timeframe_menu(chat_id):
    msg = "<b>🔥 Welcome to IB BOT 🔥</b>\n\n<b>REAL MARKET - Not OTC</b>\n\nChoose your minutes 👇\n\n<b>We recommend 5min</b> - slower and safer."
    telegram_send(chat_id, msg, buttons=timeframe_buttons())

def send_pair_menu(chat_id, timeframe):
    label = "5min" if timeframe == "5m" else "1min"
    msg = f"<b>⏰ Time: {label} ✅</b>\n\nChoose a pair below 👇\nTap one and I will give you UP / DOWN for {label}:"
    telegram_send(chat_id, msg, buttons=pair_buttons(timeframe))

print("IB BOT - 5min - Running...")
telegram_send(CHAT_ID, "✅ <b>IB BOT Started - 5min Mode</b>\nSend /start to see buttons.")
offset = None

while True:
    updates = telegram_updates(offset)
    for upd in updates:
        offset = upd["update_id"] + 1

        if "callback_query" in upd:
            cb = upd["callback_query"]
            telegram_answer_callback(cb["id"])
            chat_id = cb["message"]["chat"]["id"]
            data = cb["data"]

            if data == "TF_5m":
                send_pair_menu(chat_id, "5m")
            elif data == "TF_1m":
                send_pair_menu(chat_id, "1m")
            elif data == "BACK_TF":
                send_timeframe_menu(chat_id)
            elif data.endswith("_ALL"):
                tf = data.split("_")[0]
                label = "5min" if tf == "5m" else "1min"
                results = []
                for s, y in SYMBOLS.items():
                    _, status, _ = check_pair(s, y, tf)
                    if status == "UP":
                        results.append(f"⬆️ {display_name(s)} : UP")
                    elif status == "DOWN":
                        results.append(f"⬇️ {display_name(s)} : DOWN")
                    else:
                        results.append(f"⚪ {display_name(s)} : WAIT")
                reply = f"<b>📊 ALL PAIRS - {label} - REAL</b>\n\n" + "\n".join(results) + "\n\nChoose again 👇"
                telegram_send(chat_id, reply, buttons=pair_buttons(tf))
            elif data.endswith("_STRONG"):
                tf = data.split("_")[0]
                label = "5min" if tf == "5m" else "1min"
                strong = []
                for s, y in SYMBOLS.items():
                    _, status, result = check_pair(s, y, tf)
                    if status in ["UP", "DOWN"]:
                        strong.append(result)
                if strong:
                    reply = f"<b>🔥 STRONG ONLY - {label}</b>\n\n" + "\n\n".join(strong) + "\n\nChoose again 👇"
                else:
                    reply = f"<b>⚪ No Strong Signal - {label}</b>\n\nAll pairs are WAIT. Don't trade now.\n\nChoose again 👇"
                telegram_send(chat_id, reply, buttons=pair_buttons(tf))
            elif "_" in data and data.split("_")[0] in ["5m", "1m"]:
                tf, sym = data.split("_")
                if sym in SYMBOLS:
                    _, _, result = check_pair(sym, SYMBOLS[sym], tf)
                    reply = result + "\n\nChoose another pair 👇"
                    telegram_send(chat_id, reply, buttons=pair_buttons(tf))
            continue

        msg = upd.get("message", {})
        text = msg.get("text", "").strip().lower().replace("/", "")
        chat_id = msg.get("chat", {}).get("id")
        if not text or not chat_id:
            continue
        if text in ["start", "help", "hi", "hello", "menu"]:
            send_timeframe_menu(chat_id)

    time.sleep(2)
