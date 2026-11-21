import os
import time
import json
import urllib.request
import urllib.parse
import threading
import datetime
import yfinance as yf
import pandas as pd
import numpy as np

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============ SYMBOLS ============
# Yahoo symbols for data
SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "GBPJPY": "GBPJPY=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",
    "EURJPY": "EURJPY=X",
    "USDCHF": "USDCHF=X",
    # OTC - Weekend pairs (use real underlying as proxy)
    "EURJPY_OTC": "EURJPY=X",
    "AEDCNY_OTC": "CNY=X",
    "USDJPY_OTC": "USDJPY=X",
    "EURUSD_OTC": "EURUSD=X",
}

DISPLAY = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "GBPJPY": "GBP/JPY",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "XAUUSD": "GOLD",
    "EURJPY": "EUR/JPY",
    "USDCHF": "USD/CHF",
    "EURJPY_OTC": "EUR/JPY OTC",
    "AEDCNY_OTC": "AED/CNY OTC",
    "USDJPY_OTC": "USD/JPY OTC",
    "EURUSD_OTC": "EUR/USD OTC",
}

def display_name(sym):
    return DISPLAY.get(sym, sym)

# ============ 24/7 SETTINGS - 2 PAIRS ============
WEEKDAY_PAIRS = ["EURUSD", "GBPJPY"]  # Mon-Fri
WEEKEND_PAIRS = ["EURJPY_OTC", "AEDCNY_OTC"]  # Sat-Sun OTC
AUTO_247 = set()  # chat_ids with auto ON
LAST_SENT_247 = {}

# ============ TELEGRAM HELPERS ============
def telegram_send(chat_id, text, reply_markup=None):
    try:
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        req = urllib.request.Request(
            BASE + "/sendMessage",
            data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
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

# ============ INDICATORS ============
def calc_rsi(closes, period=14):
    try:
        closes = pd.Series(closes)
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        val = float(rsi.iloc[-1])
        if np.isnan(val):
            return 50.0
        return val
    except:
        return 50.0

def detect_pattern(df):
    try:
        # Use last closed candle (iloc[-2]) and previous (iloc[-3])
        o = float(df['Open'].iloc[-2]); c = float(df['Close'].iloc[-2])
        h = float(df['High'].iloc[-2]); l = float(df['Low'].iloc[-2])
        prev_o = float(df['Open'].iloc[-3]); prev_c = float(df['Close'].iloc[-3])
        body = abs(c - o)
        upper = h - max(o, c)
        lower = min(o, c) - l
        total = h - l
        if total == 0:
            return "No Pattern", None

        # Hammer - bullish
        if lower > body * 2 and upper < body * 0.5 and c < o:
            return "Hammer 🔨", "BUY"
        # Shooting Star - bearish
        if upper > body * 2 and lower < body * 0.5 and c > o:
            return "Shooting Star ⭐", "SELL"
        # Bullish Engulfing
        if prev_c < prev_o and c > o and c > prev_o and o < prev_c:
            return "Bullish Engulfing 🟢", "BUY"
        # Bearish Engulfing
        if prev_c > prev_o and c < o and c < prev_o and o > prev_c:
            return "Bearish Engulfing 🔴", "SELL"
        # Doji
        if body < total * 0.1:
            return "Doji ➖", None
        # Marubozu
        if body > total * 0.9:
            return ("Bullish Marubozu", "BUY") if c > o else ("Bearish Marubozu", "SELL")
        return "No Pattern", None
    except:
        return "No Pattern", None

# ============ PREDICT NEXT 1-MIN CANDLE ============
def predict_next_1m(symbol, yahoo_symbol):
    try:
        df = yf.download(yahoo_symbol, period="1d", interval="1m", progress=False)
        if df is None or len(df) < 70:
            return None
        try:
            df.columns = df.columns.droplevel(1)
        except:
            pass
        df['ma'] = df['Close'].rolling(50).mean()
        closes = df['Close']
        rsi = calc_rsi(closes)

        o = float(df['Open'].iloc[-2]); c = float(df['Close'].iloc[-2])
        ma = float(df['ma'].iloc[-2])
        prev_o = float(df['Open'].iloc[-3]); prev_c = float(df['Close'].iloc[-3])

        pattern_name, pattern_dir = detect_pattern(df)
        name = display_name(symbol)

        # 1. REVERSAL UP
        if c < o and pattern_dir == "BUY" and rsi < 55:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nPrice: {c:.5f}\n\n👉 BUY - 1 min expiry ✅"
        # 2. REVERSAL DOWN
        if c > o and pattern_dir == "SELL" and rsi > 45:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nPrice: {c:.5f}\n\n👉 SELL - 1 min expiry ✅"
        # 3. PULLBACK UP
        if c > ma and prev_c < prev_o and c > o and 50 < rsi < 70:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nAbove MA50, pullback done\nRSI: {rsi:.0f}\n\n👉 BUY ✅"
        # 4. PULLBACK DOWN
        if c < ma and prev_c > prev_o and c < o and 30 < rsi < 50:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nBelow MA50, pullback done\nRSI: {rsi:.0f}\n\n👉 SELL ✅"
        # 5. MOMENTUM UP - 2 greens
        if c > o and prev_c > prev_o and c > ma and 55 < rsi < 75:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nMomentum: 2 GREEN\nRSI: {rsi:.0f}\n\n👉 BUY ✅"
        # 6. MOMENTUM DOWN - 2 reds
        if c < o and prev_c < prev_o and c < ma and 25 < rsi < 45:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nMomentum: 2 RED\nRSI: {rsi:.0f}\n\n👉 SELL ✅"
        return None
    except Exception as e:
        print(f"Predict error {symbol}: {e}", flush=True)
        return None

def get_active_pairs():
    lagos = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
    weekday = lagos.weekday()  # 0=Mon, 5=Sat, 6=Sun
    if weekday >= 5:
        return WEEKEND_PAIRS
    return WEEKDAY_PAIRS

# ============ AUTO 24/7 LOOP ============
def auto_247_loop():
    print("🤖 AUTO 24/7 LOOP STARTED - 2 PAIRS 1 MIN", flush=True)
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

# ============ MANUAL CHECK (OLD) ============
def check_pair(symbol, timeframe="5m"):
    try:
        yahoo_symbol = SYMBOLS[symbol]
        interval = "5m" if timeframe == "5m" else "1m" if timeframe == "1m" else "30m"
        period = "1d" if interval in ["1m", "5m"] else "5d"
        df = yf.download(yahoo_symbol, period=period, interval=interval, progress=False)
        if df is None or len(df) < 70:
            return "⚠️ Not enough data. Try again."
        try:
            df.columns = df.columns.droplevel(1)
        except:
            pass
        df['ma'] = df['Close'].rolling(50).mean()
        rsi = calc_rsi(df['Close'])
        o = float(df['Open'].iloc[-2]); c = float(df['Close'].iloc[-2])
        ma = float(df['ma'].iloc[-2])
        pattern_name, pattern_dir = detect_pattern(df)
        name = display_name(symbol)
        if pattern_dir == "BUY" and rsi < 60 and c > ma:
            return f"⬆️ <b>{name} : BUY</b>\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nPrice: {c:.5f}\nMA50: {ma:.5f}"
        if pattern_dir == "SELL" and rsi > 40 and c < ma:
            return f"⬇️ <b>{name} : SELL</b>\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nPrice: {c:.5f}\nMA50: {ma:.5f}"
        if c > ma and rsi > 50:
            return f"⬆️ <b>{name} : BUY (Trend)</b>\nRSI: {rsi:.0f}\nPrice: {c:.5f}\nPattern: {pattern_name}"
        if c < ma and rsi < 50:
            return f"⬇️ <b>{name} : SELL (Trend)</b>\nRSI: {rsi:.0f}\nPrice: {c:.5f}\nPattern: {pattern_name}"
        return f"⏳ <b>{name} : WAIT</b>\nRSI: {rsi:.0f}\nPrice: {c:.5f}\nPattern: {pattern_name}\n\nNo clear signal. Wait for next candle."
    except Exception as e:
        return f"⚠️ Error: {e}"

# ============ MENUS ============
def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "🤖 AUTO 24/7 ON - 2 PAIRS 1MIN", "callback_data": "AUTO247_ON"}],
            [{"text": "🛑 AUTO 24/7 OFF", "callback_data": "AUTO247_OFF"}],
            [{"text": "📊 Manual Check - EUR/USD", "callback_data": "CHECK_EURUSD"}],
            [{"text": "📊 Manual Check - GBP/JPY", "callback_data": "CHECK_GBPJPY"}],
            [{"text": "📊 Manual Check - GOLD", "callback_data": "CHECK_XAUUSD"}],
        ]
    }

def handle_callback(chat_id, data):
    if data == "AUTO247_ON":
        AUTO_247.add(chat_id)
        telegram_send(chat_id, "🤖 <b>AUTO 24/7 ON ✅</b>\n\n<b>2 Pairs, 1 Min, Non-Stop</b>\n\nMon-Fri: EUR/USD + GBP/JPY\nSat-Sun: EUR/JPY OTC + AED/CNY OTC\n\nYou will get like:\n12:30PM EUR/USD UP ⬆️\n12:30PM GBP/JPY DOWN ⬇️\n\nJust enter and wait 1 min.", main_menu())
    elif data == "AUTO247_OFF":
        AUTO_247.discard(chat_id)
        telegram_send(chat_id, "🛑 AUTO 24/7 OFF", main_menu())
    elif data.startswith("CHECK_"):
        sym = data.replace("CHECK_", "")
        telegram_send(chat_id, "⏳ Checking...")
        result = check_pair(sym, "5m")
        telegram_send(chat_id, result, main_menu())
    else:
        telegram_send(chat_id, "Choose:", main_menu())

def handle_message(chat_id, text):
    low = text.lower().strip()
    if low in ["/start", "start", "hi", "hello"]:
        telegram_send(chat_id, "👋 <b>Welcome to IB BOT V4 - 24/7</b>\n\n<b>2 Pairs, 1 Min, Next Candle UP/DOWN</b>\n\nPress AUTO 24/7 ON to start getting signals every minute, non-stop.\n\nMon-Fri: EUR/USD + GBP/JPY\nSat-Sun: OTC Pairs\n\nUse /stop to stop.", main_menu())
    elif low in ["auto on", "auto", "on"]:
        AUTO_247.add(chat_id)
        telegram_send(chat_id, "🤖 AUTO 24/7 ON ✅\n\nYou will get signals every minute.", main_menu())
    elif low in ["/stop", "stop", "off"]:
        AUTO_247.discard(chat_id)
        telegram_send(chat_id, "🛑 Stopped.", main_menu())
    elif low in ["eurusd", "eur/usd"]:
        telegram_send(chat_id, check_pair("EURUSD", "5m"))
    elif low in ["gbpjpy", "gbp/jpy"]:
        telegram_send(chat_id, check_pair("GBPJPY", "5m"))
    else:
        telegram_send(chat_id, "Choose:", main_menu())

# ============ MAIN POLLING LOOP ============
def main():
    print("IB BOT V4 - 24/7 STARTED", flush=True)
    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                if "callback_query" in u:
                    cb = u["callback_query"]
                    chat_id = cb["message"]["chat"]["id"]
                    handle_callback(chat_id, cb["data"])
                elif "message" in u:
                    msg = u["message"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    if text:
                        handle_message(chat_id, text)
        except Exception as e:
            print(f"Main loop error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
