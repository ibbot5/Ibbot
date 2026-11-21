import os, time, json, urllib.request, urllib.parse, threading, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
import pandas as pd
import numpy as np

# ===== PUT YOUR TOKEN + ID HERE =====
BOT_TOKEN = "9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"
MY_CHAT_ID = "6716644289"
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

def keep_alive():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"RUNNING")
        def log_message(self,*a,**k): pass
    try: HTTPServer(("0.0.0.0", int(os.environ.get("PORT",10000))), H).serve_forever()
    except: pass
threading.Thread(target=keep_alive, daemon=True).start()

SYMBOLS = {"EURUSD":"EURUSD=X","GBPJPY":"GBPJPY=X","EURJPY_OTC":"EURJPY=X","AEDCNY_OTC":"CNY=X"}
DISPLAY = {"EURUSD":"EUR/USD","GBPJPY":"GBP/JPY","EURJPY_OTC":"EUR/JPY OTC","AEDCNY_OTC":"AED/CNY OTC"}
WEEKDAY = ["EURUSD","GBPJPY"]
WEEKEND = ["EURJPY_OTC","AEDCNY_OTC"]

AUTO = set()
if MY_CHAT_ID != "YOUR_CHAT_ID_HERE":
    try: AUTO.add(int(MY_CHAT_ID))
    except: pass
LAST = {}

def send(cid, text, markup=None):
    try:
        d={"chat_id":cid,"text":text,"parse_mode":"HTML"}
        if markup: d["reply_markup"]=json.dumps(markup)
        req=urllib.request.Request(BASE+"/sendMessage", data=urllib.parse.urlencode(d).encode(), headers={"Content-Type":"application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e: print(f"Send err {e}", flush=True)

def get_updates(off):
    try:
        with urllib.request.urlopen(f"{BASE}/getUpdates?offset={off}&timeout=20", timeout=30) as r: return json.loads(r.read().decode())
    except: return {"result":[]}

def rsi_calc(closes):
    try:
        s=pd.Series(closes); d=s.diff()
        g=d.where(d>0,0).rolling(14).mean(); l=(-d.where(d<0,0)).rolling(14).mean()
        r=100-(100/(1+g/l)); v=float(r.iloc[-1]); return 50.0 if np.isnan(v) else v
    except: return 50.0

# ===== ALL CANDLE PATTERNS DETECTOR =====
def detect_all(o,c,h,l):
    # o,c,h,l are lists of last 5 candles, o[-1] is last closed candle
    # Returns list of (name, direction) direction = BUY / SELL / NEUTRAL
    res=[]
    O,C,H,L = o[-1],c[-1],h[-1],l[-1]
    O1,C1,H1,L1 = o[-2],c[-2],h[-2],l[-2]
    O2,C2,H2,L2 = o[-3],c[-3],h[-3],l[-3]
    body=abs(C-O); body1=abs(C1-O1); body2=abs(C2-O2)
    total=H-L if H-L!=0 else 1; total1=H1-L1 if H1-L1!=0 else 1
    upper=H-max(O,C); lower=min(O,C)-L
    is_green=C>O; is_red=C<O
    is_green1=C1>O1; is_red1=C1<O1
    is_green2=C2>O2; is_red2=C2<O2

    # --- 1. SINGLE CANDLE ---
    if body < total*0.1: res.append(("Doji ➖","NEUTRAL"))
    if body < total*0.15 and upper<total*0.2 and lower>body*2: res.append(("Dragonfly Doji 🐉","BUY"))
    if body < total*0.15 and lower<total*0.2 and upper>body*2: res.append(("Gravestone Doji 🪦","SELL"))
    if lower>body*2 and upper<body*0.5 and is_green: res.append(("Hammer 🔨","BUY"))
    if lower>body*2 and upper<body*0.5 and is_red: res.append(("Hanging Man � hanging","SELL"))
    if upper>body*2 and lower<body*0.5 and is_green: res.append(("Inverted Hammer 🔨⬆️","BUY"))
    if upper>body*2 and lower<body*0.5 and is_red: res.append(("Shooting Star ⭐","SELL"))
    if body>total*0.9: res.append(("Marubozu 🟩 STRONG","BUY" if is_green else "SELL"))
    if body>total*0.5 and body<total*0.9 and upper<total*0.2 and lower<total*0.2: res.append(("Full Marubozu","BUY" if is_green else "SELL"))
    if body<total*0.4 and upper>total*0.25 and lower>total*0.25: res.append(("Spinning Top 🌀","NEUTRAL"))
    if upper>body*1.5 and lower<body*0.5 and is_red: res.append(("Pin Bar Down 📌","SELL"))
    if lower>body*1.5 and upper<body*0.5 and is_green: res.append(("Pin Bar Up 📌","BUY"))
    if is_green and body>total*0.7: res.append(("Bullish Belt Hold","BUY"))
    if is_red and body>total*0.7: res.append(("Bearish Belt Hold","SELL"))
    if is_green and body<total*0.2 and upper>total*0.4: res.append(("Long Legged Doji","NEUTRAL"))
    # Long / Short candle
    if body>total*0.6: res.append(("Long Candle","BUY" if is_green else "SELL"))

    # --- 2. DOUBLE CANDLE ---
    if is_green and is_red1 and C>O1 and O<C1: res.append(("Bullish Engulfing 🟢🟢","BUY"))
    if is_red and is_green1 and C<O1 and O>C1: res.append(("Bearish Engulfing 🔴🔴","SELL"))
    if is_green and is_red1 and O<C1 and C>O1 and C<C1: res.append(("Bullish Harami 🤰","BUY"))
    if is_red and is_green1 and O>C1 and C<O1 and C>C1: res.append(("Bearish Harami 🤰","SELL"))
    if is_green and is_red1 and O<C1 and C>(O1+C1)/2: res.append(("Piercing Line ✨","BUY"))
    if is_red and is_green1 and O>C1 and C<(O1+C1)/2: res.append(("Dark Cloud Cover ☁️","SELL"))
    if abs(H-H1)<total*0.05 and is_red and is_green1: res.append(("Tweezer Top 🔝","SELL"))
    if abs(L-L1)<total*0.05 and is_green and is_red1: res.append(("Tweezer Bottom 🔽","BUY"))
    if is_green and is_red1 and O<C1 and C>O1: res.append(("Bullish Kicker","BUY"))
    if is_red and is_green1 and O>C1 and C<O1: res.append(("Bearish Kicker","SELL"))
    if is_green and is_green1 and C>C1 and O>O1: res.append(("Bullish Meeting Line","BUY"))
    if is_red and is_red1 and C<C1 and O<O1: res.append(("Bearish Meeting Line","SELL"))
    if body<body1*0.3 and body1>total1*0.6: res.append(("Harami Cross ✝️","NEUTRAL"))
    if is_green and is_red1 and C> (H1+L1)/2: res.append(("Counterattack Bullish","BUY"))
    if is_red and is_green1 and C< (H1+L1)/2: res.append(("Counterattack Bearish","SELL"))

    # --- 3. TRIPLE CANDLE ---
    if is_red2 and body2>total*0.3 and body1<total*0.2 and is_green and C>O2: res.append(("Morning Star ⭐🌅","BUY"))
    if is_green2 and body2>total*0.3 and body1<total*0.2 and is_red and C<O2: res.append(("Evening Star ⭐🌇","SELL"))
    if is_red2 and is_red1 and is_red and C2>C1>C and O1<O2 and O<O1: res.append(("Three Black Crows 🐦‍⬛","SELL"))
    if is_green2 and is_green1 and is_green and C2<C1<C and O1>O2 and O>O1: res.append(("Three White Soldiers 🪖","BUY"))
    if is_red2 and is_green1 and is_green and C1>O2 and C>C1: res.append(("Three Inside Up ⬆️","BUY"))
    if is_green2 and is_red1 and is_red and C1<O2 and C<C1: res.append(("Three Inside Down ⬇️","SELL"))
    if is_red2 and is_green1 and is_green and C>O2: res.append(("Three Outside Up","BUY"))
    if is_green2 and is_red1 and is_red and C<O2: res.append(("Three Outside Down","SELL"))
    if is_green2 and is_red1 and is_green and C>C2: res.append(("Rising Three Methods 📈","BUY"))
    if is_red2 and is_green1 and is_red and C<C2: res.append(("Falling Three Methods 📉","SELL"))
    if is_green2 and is_red1 and is_red and C>O2: res.append(("Abandoned Baby Bullish 👶","BUY"))
    if is_red2 and is_green1 and is_green and C<O2: res.append(("Abandoned Baby Bearish 👶","SELL"))
    if is_green2 and is_green1 and is_green and body<body1<body2: res.append(("Advance Block - Weak UP","SELL"))
    if is_red2 and is_red1 and is_red and body<body1<body2: res.append(("Deliberation - Weak DOWN","BUY"))
    if is_green2 and is_red1 and is_green and C>C2: res.append(("Morning Doji Star","BUY"))
    if is_red2 and is_green1 and is_red and C<C2: res.append(("Evening Doji Star","SELL"))
    if is_green and is_green1 and is_red2 and C>O1: res.append(("Upside Gap Two Crows","SELL"))
    if is_red and is_red1 and is_green2 and C<O1: res.append(("Downside Gap Three Methods","BUY"))

    return res

def analyze_all(sym, yahoo):
    try:
        df=yf.download(yahoo, period="1d", interval="1m", progress=False)
        if df is None or len(df)<80: return None
        try: df.columns=df.columns.droplevel(1)
        except: pass
        df['ma']=df['Close'].rolling(20).mean()
        closes=df['Close']; rsi=rsi_calc(closes)
        # Last 5 closed candles (-6 to -2)
        o=df['Open'].iloc[-6:-1].tolist(); c=df['Close'].iloc[-6:-1].tolist()
        h=df['High'].iloc[-6:-1].tolist(); l=df['Low'].iloc[-6:-1].tolist()
        last_c=float(c[-1]); ma=float(df['ma'].iloc[-2])
        patterns=detect_all(o,c,h,l)
        name=DISPLAY.get(sym,sym)
        buys=[p for p,d in patterns if d=="BUY"]
        sells=[p for p,d in patterns if d=="SELL"]
        neut=[p for p,d in patterns if d=="NEUTRAL"]
        pat_txt=", ".join([p for p,d in patterns]) if patterns else "No Clear Pattern"
        # DECISION - Count votes
        score=len(buys)-len(sells)
        if ma: 
            if last_c>ma: score+=1
            else: score-=1
        if rsi<30: score+=1
        if rsi>70: score-=1

        if score>=2:
            return f"⬆️ <b>{name} : BUY - 1 min</b>\nPatterns Found ({len(patterns)}):\n{pat_txt}\nBullish: {len(buys)} vs Bearish: {len(sells)}\nRSI: {rsi:.0f} | Price: {last_c:.5f} | MA20: {ma:.5f}\n\n👉 <b>BUY</b>"
        if score<=-2:
            return f"⬇️ <b>{name} : SELL - 1 min</b>\nPatterns Found ({len(patterns)}):\n{pat_txt}\nBullish: {len(buys)} vs Bearish: {len(sells)}\nRSI: {rsi:.0f} | Price: {last_c:.5f} | MA20: {ma:.5f}\n\n👉 <b>SELL</b>"
        return f"⏳ <b>{name} : WAIT - 1 min</b>\nPatterns Found ({len(patterns)}):\n{pat_txt}\nBullish: {len(buys)} vs Bearish: {len(sells)}\nRSI: {rsi:.0f} | Price: {last_c:.5f}\n\n👉 No strong pattern, skip this candle"
    except Exception as e:
        print(f"Analyze {sym} {e}", flush=True); return None

def active_pairs():
    lagos=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
    return WEEKEND if lagos.weekday()>=5 else WEEKDAY

def loop_1by1():
    print("ALL PATTERNS BOT STARTED", flush=True)
    while True:
        try:
            minute=int(time.time()//60)
            lagos=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
            tstr=lagos.strftime("%I:%M%p")
            for cid in list(AUTO):
                for sym in active_pairs():
                    key=f"{cid}_{sym}"
                    if LAST.get(key)==minute: continue
                    LAST[key]=minute
                    msg=analyze_all(sym, SYMBOLS[sym])
                    if msg: send(cid, f"⏰ <b>{tstr} - 1 MIN - ALL PATTERNS</b>\n\n"+msg)
            time.sleep(10)
        except Exception as e: print(f"Loop {e}", flush=True); time.sleep(10)
threading.Thread(target=loop_1by1, daemon=True).start()

def menu(): return {"inline_keyboard":[[{"text":"🤖 AUTO ALL PATTERNS ON","callback_data":"ON"}],[{"text":"🛑 OFF","callback_data":"OFF"}]]}

def main():
    print("BOT STARTED - ALL PATTERNS", flush=True)
    if MY_CHAT_ID!="YOUR_CHAT_ID_HERE":
        try: send(int(MY_CHAT_ID), "✅ Bot restarted. ALL Candle Patterns ON. I will check ALL patterns 1 by 1 every candle.")
        except: pass
    off=0
    while True:
        try:
            ups=get_updates(off)
            for u in ups.get("result",[]):
                off=u["update_id"]+1
                if "callback_query" in u:
                    cb=u["callback_query"]; cid=cb["message"]["chat"]["id"]
                    if cb["data"]=="ON": AUTO.add(cid); send(cid,"🤖 ALL Patterns ON ✅",menu())
                    else: AUTO.discard(cid); send(cid,"🛑 OFF",menu())
                elif "message" in u and u["message"].get("text"):
                    cid=u["message"]["chat"]["id"]; txt=u["message"]["text"].lower()
                    if txt in ["/start","start","hi"]: AUTO.add(cid); send(cid,"👋 <b>IB BOT - ALL Patterns</b>\n\nI now know 40+ patterns: Doji, Hammer, Shooting Star, Engulfing, Morning Star, Three Soldiers, Three Crows, Harami, Tweezer, Piercing, Dark Cloud, Marubozu + more.\n\nI will track them 1 by 1.",menu())
        except Exception as e: print(e, flush=True); time.sleep(5)
if __name__=="__main__": main()
