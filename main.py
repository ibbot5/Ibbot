import os
import time
import json
import urllib.request
import urllib.parse
import threading
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
import pandas as pd
import numpy as np

# ============ PUT YOUR TOKEN AND ID HERE ============
BOT_TOKEN = "9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"  # <-- Paste token from @BotFather here
MY_CHAT_ID = "6716644289"  # <-- Paste your ID number here, e.g. "123456789"
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============ KEEP RENDER ALIVE (Fix Timed Out) ============
# Render Web Service needs a port, this gives it one
def keep_alive():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"IB BOT RUNNING")
        def log_message(self, *a, **k):
            pass
    port = int(os.environ.get("PORT", 10000))
    try:
        HTTPServer(("0.0.0.0", port), Handler).serve_forever()
    except:
        pass

threading.Thread(target=keep_alive, daemon=True).start()

# ============ SYMBOLS ============
SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPJPY": "GBPJPY=X",
    "EURJPY_OTC": "EURJPY=X",
    "AEDCNY_OTC": "CNY=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "XAUUSD": "GC=F",
}

DISPLAY = {
    "EURUSD": "EUR/USD",
    "GBPJPY": "GBP/JPY",
    "EURJPY_OTC": "EUR/JPY OTC",
    "AEDCNY_OTC": "AED/CNY OTC",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "XAUUSD": "GOLD",
}

WEEKDAY_PAIRS = ["EURUSD", "GBPJPY"]
WEEKEND_PAIRS = ["EURJPY_OTC", "AEDCNY_OTC"]
AUTO_247 = set()
if MY_CHAT_ID and MY_CHAT_ID != "YOUR_CHAT_ID_HERE":
    try:
        AUTO_247.add(int(MY_CHAT_ID))
    except:
        pass
LAST_SENT_247 = {}

def telegram_send(chat_id, text, reply_markup=None):
    try:
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        req = urllib.request.Request(BASE + "/sendMessage", data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"Send error: {e}", flush=True)

def get_updates(offset):
    try:
        url = f"{BASE}/getUpdates?offset={offset}&timeout=20"
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"GetUpdates error: {e}", flush=True)
        return {"result": []}

def calc_rsi(closes, period=14):
    try:
        closes = pd.Series(closes)
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        val = float(rsi.iloc[-1])
        return 50.0 if np.isnan(val) else val
    except:
        return 50.0

def detect_pattern(df):
    try:
        o = float(df['Open'].iloc[-2]); c = float(df['Close'].iloc[-2])
        h = float(df['High'].iloc[-2]); l = float(df['Low'].iloc[-2])
        prev_o = float(df['Open'].iloc[-3]); prev_c = float(df['Close'].iloc[-3])
        body = abs(c - o); upper = h - max(o, c); lower = min(o, c) - l; total = h - l
        if total == 0:
            return "No Pattern", None
        if lower > body * 2 and upper < body * 0.5 and c < o:
            return "Hammer 🔨", "BUY"
        if upper > body * 2 and lower < body * 0.5 and c > o:
            return "Shooting Star ⭐", "SELL"
        if prev_c < prev_o and c > o and c > prev_o and o < prev_c:
            return "Bullish Engulfing 🟢", "BUY"
        if prev_c > prev_o and c < o and c < prev_o and o > prev_c:
            return "Bearish Engulfing 🔴", "SELL"
        if body < total * 0.1:
            return "Doji ➖", None
        if body > total * 0.9:
            return ("Bullish Marubozu", "BUY") if c > o else ("Bearish Marubozu", "SELL")
        return "No Pattern", None
    except:
        return "No Pattern", None

def predict_next_1m(symbol, yahoo_symbol):
    try:
        df = yf.download(yahoo_symbol, period="1d", interval="1m", progress=False)
        if df is None or len(df) < 70:
            return None
        try: df.columns = df.columns.droplevel(1)
        except: pass
        df['ma'] = df['Close'].rolling(50).mean()
        closes = df['Close']; rsi = calc_rsi(closes)
        o = float(df['Open'].iloc[-2]); c = float(df['Close'].iloc[-2])
        ma = float(df['ma'].iloc[-2])
        prev_o = float(df['Open'].iloc[-3]); prev_c = float(df['Close'].iloc[-3])
        pattern_name, pattern_dir = detect_pattern(df)
        name = DISPLAY.get(symbol, symbol)
        if c < o and pattern_dir == "BUY" and rsi < 55:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nPrice: {c:.5f}\n\n👉 BUY - 1 min expiry ✅"
        if c > o and pattern_dir == "SELL" and rsi > 45:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nPrice: {c:.5f}\n\n👉 SELL - 1 min expiry ✅"
        if c > ma and prev_c < prev_o and c > o and 50 < rsi < 70:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nAbove MA50, pullback done\nRSI: {rsi:.0f}\n\n👉 BUY ✅"
        if c < ma and prev_c > prev_o and c < o and 30 < rsi < 50:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nBelow MA50, pullback done\nRSI: {rsi:.0f}\n\n👉 SELL ✅"
        if c > o and prev_c > prev_o and c > ma and 55 < rsi < 75:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nMomentum: 2 GREEN\nRSI: {rsi:.0f}\n\n👉 BUY ✅"
        if c < o and prev_c < prev_o and c < ma and 25 < rsi < 45:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nMomentum: 2 RED\nRSI: {rsi:.0f}\n\n👉 SELL ✅"
        return None
    except Exception as e:
        print(f"Predict error {symbol}: {e}", flush=True)
        return None

def get_active_pairs():
    lagos = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
    return WEEKEND_PAIRS if lagos.weekday() >= 5 else WEEKDAY_PAIRS

def auto_247_loop():
    print("🤖 AUTO 24/7 LOOP STARTED", flush=True)
    while True:
        try:
            now_minute = int(time.time() // 60)
            lagos = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
            time_str = lagos.strftime("%I:%M%p")
            active_pairs = get_active_pairs()
            for chat_id in list(AUTO_247):
                for sym in active_pairs:
                    key = f"{chat_id}_{sym}"
                    if LAST_SENT_247.get(key) == now_minute:
                        continue
                    LAST_SENT_247[key] = now_minute
                    signal = predict_next_1m(sym, SYMBOLS[sym])
                    if signal:
                        telegram_send(chat_id, f"⏰ <b>{time_str} - 1 MIN - 24/7</b>\n\n" + signal)
            time.sleep(10)
        except Exception as e:
            print(f"247 loop error: {e}", flush=True)
            time.sleep(10)

threading.Thread(target=auto_247_loop, daemon=True).start()

def main_menu():
    return {"inline_keyboard": [
        [{"text": "🤖 AUTO 24/7 ON - 2 PAIRS 1MIN", "callback_data": "AUTO247_ON"}],
        [{"text": "🛑 AUTO 24/7 OFF", "callback_data": "AUTO247_OFF"}],
    ]}

def handle_callback(chat_id, data):
    if data == "AUTO247_ON":
        AUTO_247.add(chat_id)
        telegram_send(chat_id, "🤖 <b>AUTO 24/7 ON ✅</b>\n\nMon-Fri: EUR/USD + GBP/JPY\nSat-Sun: EUR/JPY OTC + AED/CNY OTC", main_menu())
    elif data == "AUTO247_OFF":
        AUTO_247.discard(chat_id)
        telegram_send(chat_id, "🛑 AUTO 24/7 OFF", main_menu())

def handle_message(chat_id, text):
    low = text.lower().strip()
    if low in ["/start", "start", "hi", "hello"]:
        AUTO_247.add(chat_id)
        telegram_send(chat_id, "👋 <b>Welcome IB BOT V4 - 24/7</b>\n\n🤖 AUTO is ON already for you.\nYou will get signals every minute.\n\nMon-Fri: EUR/USD + GBP/JPY\nSat-Sun: OTC Pairs", main_menu())
    elif low in ["/stop", "stop", "off"]:
        AUTO_247.discard(chat_id)
        telegram_send(chat_id, "🛑 Stopped.", main_menu())
    else:
        telegram_send(chat_id, "Choose:", main_menu())

def main():
    print("IB BOT V4 - 24/7 STARTED - Token inside code", flush=True)
    # Send test to your ID on start so you know it works
    if MY_CHAT_ID and MY_CHAT_ID != "YOUR_CHAT_ID_HERE":
        try:
            telegram_send(int(MY_CHAT_ID), "✅ Bot restarted and connected. AUTO 24/7 is ON. You will get signals every minute.")
        except Exception as e:
            print(f"Start test send error: {e}", flush=True)
    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                if "callback_query" in u:
                    cb = u["callback_query"]
                    handle_callback(cb["message"]["chat"]["id"], cb["data"])
                elif "message" in u:
                    msg = u["message"]
                    if msg.get("text"):
                        handle_message(msg["chat"]["id"], msg["text"])
        except Exception as e:
            print(f"Main loop error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
