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

BOT_TOKEN = "9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"
MY_CHAT_ID = "6716644289"
BASE = "https://api.telegram.org/bot" + BOT_TOKEN

def keep_alive():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"RUNNING")
        def log_message(self, *a, **k):
            pass
    try:
        HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), H).serve_forever()
    except:
        pass

threading.Thread(target=keep_alive, daemon=True).start()

PAIR_NAME = "GBP/JPY (OTC)"
YAHOO = "GBPJPY=X"
AUTO = set()
if MY_CHAT_ID != "YOUR_CHAT_ID_HERE":
    try:
        AUTO.add(int(MY_CHAT_ID))
    except:
        pass
LAST_MIN = -1

def send(cid, text, markup=None):
    try:
        d = {"chat_id": cid, "text": text, "parse_mode": "HTML"}
        if markup:
            d["reply_markup"] = json.dumps(markup)
        req = urllib.request.Request(BASE + "/sendMessage", data=urllib.parse.urlencode(d).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(e, flush=True)

def get_updates(off):
    try:
        with urllib.request.urlopen(BASE + "/getUpdates?offset=" + str(off) + "&timeout=20", timeout=30) as r:
            return json.loads(r.read().decode())
    except:
        return {"result": []}

def rsi_calc(closes):
    try:
        s = pd.Series(closes)
        d = s.diff()
        g = d.where(d > 0, 0).rolling(14).mean()
        l = (-d.where(d < 0, 0)).rolling(14).mean()
        r = 100 - (100 / (1 + g / l))
        v = float(r.iloc[-1])
        if np.isnan(v):
            return 50.0
        return v
    except:
        return 50.0

def dr_predict_strong():
    df = yf.download(YAHOO, period="1d", interval="1m", progress=False)
    if df is None or len(df) < 30:
        return None
    try:
        df.columns = df.columns.droplevel(1)
    except:
        pass
    df["ma"] = df["Close"].rolling(20).mean()
    rsi = rsi_calc(df["Close"])
    o = df["Open"].iloc[-4:-1].tolist()
    c = df["Close"].iloc[-4:-1].tolist()
    h = df["High"].iloc[-4:-1].tolist()
    l = df["Low"].iloc[-4:-1].tolist()
    O = o[-1]
    C = c[-1]
    H = h[-1]
    L = l[-1]
    O1 = o[-2]
    C1 = c[-2]
    O2 = o[-3]
    C2 = c[-3]
    body = abs(C - O)
    upper = H - max(O, C)
    lower = min(O, C) - L
    is_green = C > O
    is_red = C < O
    is_green1 = C1 > O1
    is_red1 = C1 < O1
    is_green2 = C2 > O2
    is_red2 = C2 < O2
    ma = float(df["ma"].iloc[-2])
    price = float(C)

    # --- ORDER BLOCK DETECTION (last 30 candles) ---
    bullish_ob = None
    bearish_ob = None
    # Use full df for OB search
    for i in range(2, len(df)-1):
        oi = float(df["Open"].iloc[i])
        ci = float(df["Close"].iloc[i])
        hi = float(df["High"].iloc[i])
        li = float(df["Low"].iloc[i])
        next_c = float(df["Close"].iloc[i+1])
        # Bullish OB: Red candle, next candle breaks above its high
        if ci < oi and next_c > hi:
            bullish_ob = (li, hi)
        # Bearish OB: Green candle, next candle breaks below its low
        if ci > oi and next_c < li:
            bearish_ob = (li, hi)

    in_bull_ob = False
    in_bear_ob = False
    ob_text = ""
    if bullish_ob and bullish_ob[0] <= price <= bullish_ob[1]:
        in_bull_ob = True
        ob_text = f"Bullish OB: {bullish_ob[0]:.3f} - {bullish_ob[1]:.3f}"
    if bearish_ob and bearish_ob[0] <= price <= bearish_ob[1]:
        in_bear_ob = True
        ob_text = f"Bearish OB: {bearish_ob[0]:.3f} - {bearish_ob[1]:.3f}"

    # Pattern detection
    is_hammer = lower > body * 2 and is_green
    is_shooting = upper > body * 2 and is_red
    is_bull_engulf = is_green and is_red1 and C > O1 and O < C1
    is_bear_engulf = is_red and is_green1 and C < O1 and O > C1
    is_morning = is_red2 and is_green and C > O2
    is_evening = is_green2 and is_red and C < O2
    is_bull_pin = lower > body * 1.5 and is_green
    is_bear_pin = upper > body * 1.5 and is_red

    bull_pattern = is_hammer or is_bull_engulf or is_morning or is_bull_pin
    bear_pattern = is_shooting or is_bear_engulf or is_evening or is_bear_pin

    # --- NEW: ORDER BLOCK + PATTERN + RSI = STRONGEST ---
    # BUY: In Bullish OB + Bull Pattern + RSI low + Price below MA
    if in_bull_ob and bull_pattern and rsi < 45 and price < ma:
        if is_hammer:
            pat = "Hammer"
        elif is_bull_engulf:
            pat = "Bullish Engulfing"
        elif is_morning:
            pat = "Morning Star"
        else:
            pat = "Bullish Pin Bar"
        return ["BUY", pat + " + ORDER BLOCK + RSI " + str(round(rsi)) + " + Below MA - 4 CONFIRMATIONS | " + ob_text, price, rsi]

    # SELL: In Bearish OB + Bear Pattern + RSI high + Price above MA
    if in_bear_ob and bear_pattern and rsi > 55 and price > ma:
        if is_shooting:
            pat = "Shooting Star"
        elif is_bear_engulf:
            pat = "Bearish Engulfing"
        elif is_evening:
            pat = "Evening Star"
        else:
            pat = "Bearish Pin Bar"
        return ["SELL", pat + " + ORDER BLOCK + RSI " + str(round(rsi)) + " + Above MA - 4 CONFIRMATIONS | " + ob_text, price, rsi]

    # Fallback - keep old logic if OB not touched but RSI extreme
    if bull_pattern and rsi < 30:
        return ["BUY", "Pattern + RSI " + str(round(rsi)) + " OVERSOLD - Strong Reversal (No OB)", price, rsi]
    if bear_pattern and rsi > 70:
        return ["SELL", "Pattern + RSI " + str(round(rsi)) + " OVERBOUGHT - Strong Reversal (No OB)", price, rsi]
    return None

def loop_dr():
    global LAST_MIN
    print("STRONG MODE STARTED", flush=True)
    while True:
        try:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
            minute = int(time.time() // 60)
            if now.second < 12 and minute != LAST_MIN:
                LAST_MIN = minute
                res = dr_predict_strong()
                if res:
                    direction = res[0]
                    reason = res[1]
                    price = res[2]
                    rsi = res[3]
                    tstr = now.strftime("%I:%M%p")
                    for cid in list(AUTO):
                        msg = "STRONG SIGNAL - ORDER BLOCK\n\n" + direction + " - " + PAIR_NAME + " - 1 MIN\n\nReason: " + reason + "\nPrice: " + str(round(price, 5)) + " | RSI: " + str(round(rsi, 0)) + "\nEnter NOW: " + tstr + "\n\nOpen " + direction + " trade now! - Pocket Option"
                        send(cid, msg)
            time.sleep(3)
        except Exception as e:
            print(e, flush=True)
            time.sleep(5)

threading.Thread(target=loop_dr, daemon=True).start()

def menu():
    return {"inline_keyboard": [[{"text": "STRONG MODE ON", "callback_data": "ON"}], [{"text": "OFF", "callback_data": "OFF"}]]}

def main():
    print("BOT STRONG STARTED", flush=True)
    if MY_CHAT_ID != "YOUR_CHAT_ID_HERE":
        try:
            send(int(MY_CHAT_ID), "ORDER BLOCK MODE ON. Pair: GBP/JPY (OTC) - 1 MIN - Pocket Option. I will ONLY send when Order Block + Pattern + RSI + MA agree.")
        except:
            pass
    off = 0
    while True:
        try:
            ups = get_updates(off)
            for u in ups.get("result", []):
                off = u["update_id"] + 1
                if "callback_query" in u:
                    cb = u["callback_query"]
                    cid = cb["message"]["chat"]["id"]
                    if cb["data"] == "ON":
                        AUTO.add(cid)
                        send(cid, "STRONG MODE ON", menu())
                    else:
                        AUTO.discard(cid)
                        send(cid, "OFF", menu())
                elif "message" in u and u["message"].get("text"):
                    cid = u["message"]["chat"]["id"]
                    txt = u["message"]["text"].lower()
                    if txt in ["/start", "start", "hi"]:
                        AUTO.add(cid)
                        send(cid, "STRONG MODE - ORDER BLOCK\n\nPair: GBP/JPY (OTC)\nTime: 1 MIN\nFor: Pocket Option\n\nI only send when Order Block + Pattern + RSI + MA agree.", menu())
        except Exception as e:
            print(e, flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
