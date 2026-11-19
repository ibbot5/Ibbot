import yfinance as yf
import urllib.parse
import urllib.request
import json
import time
import os
import sys
import traceback
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"IB BOT V3.1 FIXED is running")
        def log_message(self, *a):
            pass
    try:
        print(f"Starting web server on port {port}", flush=True)
        HTTPServer(("0.0.0.0", port), H).serve_forever()
    except Exception as e:
        print(f"Web server error: {e}", flush=True)

threading.Thread(target=keep_alive, daemon=True).start()

BOT_TOKEN = "
9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"
CHAT_ID = "6716644289"

print("BOT_TOKEN set?", "YES" if BOT_TOKEN != "PASTE_YOUR_BOT_TOKEN_HERE" and len(BOT_TOKEN) > 10 else "NO - PLEASE PASTE REAL TOKEN", flush=True)

SYMBOLS = {
    'GBPJPY': 'GBPJPY=X',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'XAUUSD': 'GC=F',
    'EURJPY': 'EURJPY=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
    'EURJPY_OTC': 'EURJPY=X',
    'AEDCNY_OTC': 'AEDCNY=X',
}

def display_name(sym):
    if sym == 'XAUUSD':
        return 'XAU/USD'
    if sym == 'EURJPY_OTC':
        return 'EUR/JPY OTC'
    if sym == 'AEDCNY_OTC':
        return 'AED/CNY OTC'
    return f"{sym[:3]}/{sym[3:]}"

def tf_label(tf):
    if tf == "5m":
        return "5min"
    if tf == "1m":
        return "1min"
    if tf == "30m":
        return "30min"
    if tf == "1h":
        return "1 Hour"
    return tf

def telegram_send(chat_id, message, buttons=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data_dict = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
        if buttons:
            keyboard = []
            row = []
            for txt, cb in buttons:
                row.append({"text": txt, "callback_data": cb})
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            data_dict['reply_markup'] = json.dumps({"inline_keyboard": keyboard})
        data = urllib.parse.urlencode(data_dict)
        req = urllib.request.Request(url, data.encode())
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"Send failed: {e}", flush=True)

def telegram_answer_callback(callback_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
        data = urllib.parse.urlencode({'callback_query_id': callback_id})
        req = urllib.request.Request(url, data.encode())
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        print(f"Answer callback failed: {e}", flush=True)

def telegram_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
    if offset:
        url += f"&offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
            return data.get("result", [])
    except Exception as e:
        print(f"Updates failed: {e}", flush=True)
        return []

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    deltas = closes.diff()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.rolling(period).mean()
    avg_loss = losses.rolling(period).mean()
    rs = avg_gain / (avg_loss + 0.000001)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])

def detect_pattern(df):
    try:
        o2, c2 = float(df['Open'].iloc[-4]), float(df['Close'].iloc[-4])
        h2, l2 = float(df['High'].iloc[-4]), float(df['Low'].iloc[-4])
        o1, c1 = float(df['Open'].iloc[-3]), float(df['Close'].iloc[-3])
        h1, l1 = float(df['High'].iloc[-3]), float(df['Low'].iloc[-3])
        o0, c0 = float(df['Open'].iloc[-2]), float(df['Close'].iloc[-2])
        h0, l0 = float(df['High'].iloc[-2]), float(df['Low'].iloc[-2])
    except Exception:
        return "None", "NONE"
    def body(o,c): return abs(c-o)
    def is_green(o,c): return c > o
    def is_red(o,c): return c < o
    def is_doji(o,c,h,l):
        rng = h - l + 0.000001
        return body(o,c) / rng < 0.15
    def is_hammer(o,c,h,l):
        rng = h - l + 0.000001
        lower_wick = min(o,c) - l
        upper_wick = h - max(o,c)
        return lower_wick > body(o,c)*2 and lower_wick > rng*0.55 and upper_wick < body(o,c)*0.5
    def is_shooting(o,c,h,l):
        rng = h - l + 0.000001
        upper_wick = h - max(o,c)
        lower_wick = min(o,c) - l
        return upper_wick > body(o,c)*2 and upper_wick > rng*0.55 and lower_wick < body(o,c)*0.5
    if is_doji(o0,c0,h0,l0):
        return "Doji - Confused", "WAIT"
    if is_red(o2,c2) and body(o1,c1) < body(o2,c2)*0.4 and is_green(o0,c0) and c0 > (o2+c2)/2:
        return "Morning Star ⭐", "BUY"
    if is_green(o2,c2) and body(o1,c1) < body(o2,c2)*0.4 and is_red(o0,c0) and c0 < (o2+c2)/2:
        return "Evening Star ⭐", "SELL"
    if is_red(o1,c1) and is_green(o0,c0) and c0 > o1 and o0 < c1:
        return "Bullish Engulfing 🟢", "BUY"
    if is_green(o1,c1) and is_red(o0,c0) and c0 < o1 and o0 > c1:
        return "Bearish Engulfing 🔴", "SELL"
    if is_hammer(o0,c0,h0,l0) and is_red(o1,c1):
        return "Hammer 🔨", "BUY"
    if is_shooting(o0,c0,h0,l0) and is_green(o1,c1):
        return "Shooting Star / Pin Bar Top 📌", "SELL"
    if is_hammer(o0,c0,h0,l0) and is_green(o0,c0):
        return "Pin Bar Bottom 📌", "BUY"
    if is_shooting(o0,c0,h0,l0) and is_red(o0,c0):
        return "Pin Bar Top 📌", "SELL"
    if is_green(o2,c2) and is_green(o1,c1) and is_green(o0,c0):
        return "3 Green - Too Late", "WAIT"
    if is_red(o2,c2) and is_red(o1,c1) and is_red(o0,c0):
        return "3 Red - Too Late", "WAIT"
    return "No Pattern - Pullback Only", "PULLBACK"

def check_pair(symbol, yahoo_symbol, timeframe="5m"):
    try:
        if timeframe == "1h":
            period = "5d"
            interval = "1h"
        elif timeframe == "30m":
            period = "5d"
            interval = "30m"
        elif timeframe == "5m":
            period = "1d"
            interval = "5m"
        else:
            period = "1d"
            interval = "1m"
        df = yf.download(yahoo_symbol, period=period, interval=interval, progress=False)
        if df is None or len(df) < 70:
            return (symbol, "FLAT", f"{display_name(symbol)}: No data", "LOW")
        try:
            df.columns = df.columns.droplevel(1)
        except Exception:
            pass
        df['ma'] = df['Close'].rolling(50).mean()
        closes = df['Close']
        curr_close = float(closes.iloc[-2])
        prev_close = float(closes.iloc[-3])
        prev_open = float(df['Open'].iloc[-3])
        curr_ma = float(df['ma'].iloc[-2])
        ma_now = float(df['ma'].iloc[-2])
        ma_before = float(df['ma'].iloc[-5])
        rsi = calc_rsi(closes)
        pattern_name, pattern_dir = detect_pattern(df)
        def candle_color(o, c):
            return 1 if c > o else -1
        last3 = [candle_color(float(df['Open'].iloc[-2-i]), float(df['Close'].iloc[-2-i])) for i in range(3)]
        last5 = [candle_color(float(df['Open'].iloc[-2-i]), float(df['Close'].iloc[-2-i])) for i in range(5)]
        label = tf_label(timeframe)
        name = display_name(symbol)
        is_otc = "_OTC" in symbol
        otc_note = "\n⚠️ OTC Proxy - Check Quotex chart" if is_otc else ""
        if pattern_dir == "WAIT":
            return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nPattern: {pattern_name}\nRSI: {rsi:.0f} ❌\nDon't trade - {pattern_name}{otc_note}", "LOW")
        if last3[0] == last3[1] == last3[2] and pattern_dir == "PULLBACK":
            return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nReason: 3 same candles - Don't chase ❌\nRSI: {rsi:.0f}{otc_note}", "LOW")
        if last5 == [1,-1,1,-1,1] or last5 == [-1,1,-1,1,-1]:
            return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nReason: Choppy - zig zag ❌\nRSI: {rsi:.0f}{otc_note}", "LOW")
        dist = abs(curr_close - curr_ma) / (curr_close + 0.000001) * 100
        if dist > 0.35:
            return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nReason: Too far from MA50 ({dist:.2f}%) ❌\nRSI: {rsi:.0f}{otc_note}", "LOW")
        if curr_close > curr_ma and ma_now > ma_before:
            pullback_ok = prev_close < prev_open
            if rsi > 45 and (pattern_dir == "BUY" or (pattern_dir == "PULLBACK" and pullback_ok)):
                conf = "HIGH" if pattern_dir == "BUY" and rsi > 50 else "MEDIUM"
                return (symbol, "UP", f"⬆️ <b>{name} : UP - {label}</b>\n\nPrice: {curr_close:.5f}\nAbove MA50, MA UP\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nConfidence: {conf} ✅{otc_note}\n\nTake BUY for {label} ✅", conf)
            return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nReason: Above MA50 but Pattern: {pattern_name} / RSI {rsi:.0f} ❌{otc_note}", "LOW")
        if curr_close < curr_ma and ma_now < ma_before:
            pullback_ok = prev_close > prev_open
            if rsi < 55 and (pattern_dir == "SELL" or (pattern_dir == "PULLBACK" and pullback_ok)):
                conf = "HIGH" if pattern_dir == "SELL" and rsi < 50 else "MEDIUM"
                return (symbol, "DOWN", f"⬇️ <b>{name} : DOWN - {label}</b>\n\nPrice: {curr_close:.5f}\nBelow MA50, MA DOWN\nPattern: {pattern_name}\nRSI: {rsi:.0f}\nConfidence: {conf} ✅{otc_note}\n\nTake SELL for {label} ✅", conf)
            return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nReason: Below MA50 but Pattern: {pattern_name} / RSI {rsi:.0f} ❌{otc_note}", "LOW")
        return (symbol, "FLAT", f"⚪ <b>{name} : WAIT - {label}</b>\n\nPrice: {curr_close:.5f}\nMA flat\nPattern: {pattern_name}\nRSI: {rsi:.0f}{otc_note}\n\nDon't trade ❌", "LOW")
    except Exception as e:
        print(f"Check error {symbol}: {e}", flush=True)
        traceback.print_exc()
        return (symbol, "ERROR", f"{display_name(symbol)}: Error", "LOW")

def timeframe_buttons():
    return [("✅ 5min", "TF_5m"), ("1min", "TF_1m"), ("30min 🕧", "TF_30m"), ("1 Hour 🕐", "TF_1h")]

def pair_buttons(timeframe):
    btns = []
    for sym in SYMBOLS.keys():
        btns.append((f"{display_name(sym)}", f"{timeframe}_{sym}"))
    btns.append((f"📊 ALL - {timeframe}", f"{timeframe}_ALL"))
    btns.append((f"🔥 STRONG - {timeframe}", f"{timeframe}_STRONG"))
    btns.append(("⬅️ Change Time", "BACK_TF"))
    return btns

def send_timeframe_menu(chat_id):
    msg = "<b>🔥 Welcome to IB BOT V3.1 FIXED 🕯️</b>\n\n<b>MA50 + RSI + Candlestick + OTC</b>\n\nChoose your minutes 👇\n\n<b>We recommend 5min</b> - slower and safer."
    telegram_send(chat_id, msg, buttons=timeframe_buttons())

def send_pair_menu(chat_id, timeframe):
    label = tf_label(timeframe)
    msg = f"<b>⏰ Time: {label} ✅</b>\n\nChoose a pair below 👇"
    telegram_send(chat_id, msg, buttons=pair_buttons(timeframe))

def main():
    print("IB BOT V3.1 FIXED - Running...", flush=True)
    # Safe start message - will not crash if token is wrong
    try:
        if BOT_TOKEN != "PASTE_YOUR_BOT_TOKEN_HERE":
            telegram_send(CHAT_ID, "✅ <b>IB BOT V3.1 FIXED Started</b>\nSend /start to see buttons.")
        else:
            print("Skipping start message - token not set yet", flush=True)
    except Exception as e:
        print(f"Start message failed (not fatal): {e}", flush=True)
    offset = None
    while True:
        try:
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
                    elif data == "TF_30m":
                        send_pair_menu(chat_id, "30m")
                    elif data == "TF_1h":
                        send_pair_menu(chat_id, "1h")
                    elif data == "BACK_TF":
                        send_timeframe_menu(chat_id)
                    elif data.endswith("_ALL"):
                        tf = data.split("_")[0]
                        label = tf_label(tf)
                        results = []
                        for s, y in SYMBOLS.items():
                            _, status, txt, _ = check_pair(s, y, tf)
                            if status == "UP":
                                results.append(f"⬆️ {display_name(s)} : UP")
                            elif status == "DOWN":
                                results.append(f"⬇️ {display_name(s)} : DOWN")
                            else:
                                results.append(f"⚪ {display_name(s)} : WAIT")
                        reply = f"<b>📊 ALL PAIRS - {label}</b>\n\n" + "\n".join(results) + "\n\nChoose again 👇"
                        telegram_send(chat_id, reply, buttons=pair_buttons(tf))
                    elif data.endswith("_STRONG"):
                        tf = data.split("_")[0]
                        label = tf_label(tf)
                        strong = []
                        for s, y in SYMBOLS.items():
                            _, status, result, conf = check_pair(s, y, tf)
                            if status in ["UP", "DOWN"] and conf == "HIGH":
                                strong.append(result)
                        if strong:
                            reply = f"<b>🔥 STRONG ONLY - {label} - HIGH CONF ONLY</b>\n\n" + "\n\n".join(strong) + "\n\nChoose again 👇"
                        else:
                            reply = f"<b>⚪ No Strong Signal - {label}</b>\n\nAll pairs are WAIT. Don't trade now.\n\nChoose again 👇"
                        telegram_send(chat_id, reply, buttons=pair_buttons(tf))
                    elif "_" in data and data.split("_")[0] in ["5m", "1m", "30m", "1h"]:
                        parts = data.split("_", 1)
                        tf = parts[0]
                        sym = parts[1]
                        if sym in SYMBOLS:
                            _, _, result, _ = check_pair(sym, SYMBOLS[sym], tf)
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
        except Exception as e:
            print(f"Main loop error: {e}", flush=True)
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()
