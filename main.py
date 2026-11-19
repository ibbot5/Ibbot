import yfinance as yf
import urllib.parse
import urllib.request
import json
import time
import pandas as pd

# --- PASTE YOURS HERE ---
BOT_TOKEN = "9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"
CHAT_ID = "6716644289"

SYMBOLS = {
    'GBPJPY': 'GBPJPY=X',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'XAUUSD': 'GC=F'
}

def telegram_send(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'})
    req = urllib.request.Request(url, data.encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print("Send failed:", e)

def telegram_send_to(chat_id, message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'})
    req = urllib.request.Request(url, data.encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print("Send failed:", e)

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
            return (symbol, "FLAT", f"{symbol}: No data")
        if hasattr(df.columns, 'droplevel'):
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
            return (symbol, "UP", f"{symbol}: UP 🟢\nPrice: {curr_close:.5f} above MA50, MA sloping UP")
        elif curr_close < curr_ma and ma_now < ma_before:
            return (symbol, "DOWN", f"{symbol}: DOWN 🔴\nPrice: {curr_close:.5f} below MA50, MA sloping DOWN")
        else:
            return (symbol, "FLAT", f"{symbol}: FLAT ⚪\nPrice: {curr_close:.5f} - MA not sloping clearly, wait")
    except Exception as e:
        print("Check error", symbol, e)
        return (symbol, "ERROR", f"{symbol}: Error")

print("Bot running... Send /signal in Telegram")
telegram_send("✅ <b>IB BOT Started</b>\nSend /signal for all pairs, /strong for clear only.")
offset = None

while True:
    updates = telegram_updates(offset)
    for upd in updates:
        offset = upd["update_id"] + 1
        msg = upd.get("message", {})
        text = msg.get("text", "").strip().lower().replace("/", "")
        chat_id = msg.get("chat", {}).get("id")
        if not text or not chat_id:
            continue

        if text in ["signal", "all", "check"]:
            results = [check_pair(s, y)[2] for s, y in SYMBOLS.items()]
            reply = "<b>📊 All 5 Pairs (M1 + MA50 Slope)</b>\n\n" + "\n\n".join(results)
            telegram_send_to(chat_id, reply)

        elif text in ["strong", "best", "clear"]:
            strong = []
            flat_count = 0
            for s, y in SYMBOLS.items():
                _, status, result = check_pair(s, y)
                if status in ["UP", "DOWN"]:
                    strong.append(result)
                else:
                    flat_count += 1
            if strong:
                reply = "<b>🔥 Strong Signals Only</b>\n\n" + "\n\n".join(strong) + f"\n\n{flat_count} pair(s) were FLAT and hidden."
            else:
                reply = "<b>⚪ No Strong Signal Right Now</b>\n\nAll 5 pairs are FLAT. Wait and send /strong again."
            telegram_send_to(chat_id, reply)

        elif text.upper() in SYMBOLS:
            symbol = text.upper()
            _, _, result = check_pair(symbol, SYMBOLS[symbol])
            reply = f"<b>📊 {symbol}</b>\n\n{result}"
            telegram_send_to(chat_id, reply)

        elif text in ["start", "help", "hi", "hello"]:
            reply = "<b>👋 How to use me</b>\n\n/signal - All 5 pairs\n/strong - Only clear UP/DOWN\n/gbpjpy - GBPJPY only\n/eurusd - EURUSD only\n/gbpusd - GBPUSD only\n/usdjpy - USDJPY only\n/xauusd - Gold only"
            telegram_send_to(chat_id, reply)

    time.sleep(5)
