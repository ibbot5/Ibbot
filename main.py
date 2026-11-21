import os, time, json, urllib.request, urllib.parse, threading, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
import pandas as pd
import numpy as np

# ===== PUT YOUR TOKEN + ID HERE =====
BOT_TOKEN = "9062675637:AAEEAVM0DU3by2Q2gpq5kL1QQm62AnRDo6g"
MY_CHAT_ID = "6716644289"
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Keep Render Alive
def keep_alive():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"RUNNING")
        def log_message(self,*a,**k): pass
    try:
        HTTPServer(("0.0.0.0", int(os.environ.get("PORT",10000))), H).serve_forever()
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
        with urllib.request.urlopen(f"{BASE}/getUpdates?offset={off}&timeout=20", timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"GetUpdates {e}", flush=True); return {"result":[]}

def rsi_calc(closes):
    try:
        s=pd.Series(closes); d=s.diff()
        g=d.where(d>0,0).rolling(14).mean(); l=(-d.where(d<0,0)).rolling(14).mean()
        r=100-(100/(1+g/l)); v=float(r.iloc[-1]); return 50.0 if np.isnan(v) else v
    except: return 50.0

def analyze_1_candle(sym, yahoo):
    """Track 1 by 1 candle - always returns a verdict"""
    try:
        df=yf.download(yahoo, period="1d", interval="1m", progress=False)
        if df is None or len(df)<70: return None
        try: df.columns=df.columns.droplevel(1)
        except: pass
        df['ma']=df['Close'].rolling(20).mean()
        closes=df['Close']; rsi=rsi_calc(closes)
        # Last CLOSED candle ( -2 because -1 is still forming )
        o=float(df['Open'].iloc[-2]); c=float(df['Close'].iloc[-2])
        h=float(df['High'].iloc[-2]); l=float(df['Low'].iloc[-2])
        ma=float(df['ma'].iloc[-2])
        po=float(df['Open'].iloc[-3]); pc=float(df['Close'].iloc[-3])
        body=abs(c-o); upper=h-max(o,c); lower=min(o,c)-l; total=h-l if h-l!=0 else 1
        is_green=c>o; is_red=c<o
        name=DISPLAY.get(sym,sym)

        # Pattern names for 1 candle
        pattern="No Pattern"
        if lower>body*1.5 and body>0: pattern="Hammer 🔨"
        elif upper>body*1.5 and body>0: pattern="Shooting Star ⭐"
        elif body<total*0.1: pattern="Doji ➖"
        elif body>total*0.8: pattern="Marubozu 🟩" if is_green else "Marubozu 🟥"
        elif is_green and pc<po: pattern="Bullish Engulfing 🟢"
        elif is_red and pc>po: pattern="Bearish Engulfing 🔴"

        # 1-BY-1 DECISION - Always gives BUY/SELL/WAIT
        # Strong BUY
        if is_green and c>ma and rsi<70 and (pattern.startswith("Hammer") or pattern.startswith("Bullish") or body>total*0.6):
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nCandle: GREEN ✅ | Pattern: {pattern}\nRSI: {rsi:.0f} | Price: {c:.5f} | Above MA20 ✅\n\n👉 <b>BUY - 1 min</b>"
        # Strong SELL
        if is_red and c<ma and rsi>30 and (pattern.startswith("Shooting") or pattern.startswith("Bearish") or body>total*0.6):
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nCandle: RED ✅ | Pattern: {pattern}\nRSI: {rsi:.0f} | Price: {c:.5f} | Below MA20 ✅\n\n👉 <b>SELL - 1 min</b>"
        # Weak trend follow - still trade
        if is_green and c>ma and rsi>50:
            return f"⬆️ <b>{name} : NEXT CANDLE UP</b>\nCandle: GREEN | Pattern: {pattern}\nRSI: {rsi:.0f} | Price: {c:.5f}\nTrend: UP ✅\n\n👉 <b>BUY - 1 min</b>"
        if is_red and c<ma and rsi<50:
            return f"⬇️ <b>{name} : NEXT CANDLE DOWN</b>\nCandle: RED | Pattern: {pattern}\nRSI: {rsi:.0f} | Price: {c:.5f}\nTrend: DOWN ✅\n\n👉 <b>SELL - 1 min</b>"
        # WAIT - but still tell you why
        if rsi>75:
            return f"⏳ <b>{name} : WAIT</b>\nCandle: {'GREEN' if is_green else 'RED'} | Pattern: {pattern}\nRSI: {rsi:.0f} - OVERBOUGHT ❌\nPrice: {c:.5f}\n\n👉 No trade, wait for pullback"
        if rsi<25:
            return f"⏳ <b>{name} : WAIT</b>\nCandle: {'GREEN' if is_green else 'RED'} | Pattern: {pattern}\nRSI: {rsi:.0f} - OVERSOLD ❌\nPrice: {c:.5f}\n\n👉 No trade, wait for pullback"
        return f"⏳ <b>{name} : WAIT</b>\nCandle: {'GREEN' if is_green else 'RED'} | Pattern: {pattern}\nRSI: {rsi:.0f} | Price: {c:.5f}\nMA20: {ma:.5f} - Sideways ❌\n\n👉 No clear direction this candle"
    except Exception as e:
        print(f"Analyze {sym} {e}", flush=True); return None

def active_pairs():
    lagos=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1)))
    return WEEKEND if lagos.weekday()>=5 else WEEKDAY

def loop_1by1():
    print("1-BY-1 TRACKER STARTED", flush=True)
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
                    msg=analyze_1_candle(sym, SYMBOLS[sym])
                    if msg:
                        send(cid, f"⏰ <b>{tstr} - 1 MIN - Candle by Candle</b>\n\n"+msg)
            time.sleep(10)
        except Exception as e:
            print(f"Loop err {e}", flush=True); time.sleep(10)

threading.Thread(target=loop_1by1, daemon=True).start()

def menu():
    return {"inline_keyboard":[[{"text":"🤖 AUTO 1-BY-1 ON","callback_data":"ON"}],[{"text":"🛑 OFF","callback_data":"OFF"}]]}

def main():
    print("BOT STARTED - 1 BY 1", flush=True)
    if MY_CHAT_ID!="YOUR_CHAT_ID_HERE":
        try: send(int(MY_CHAT_ID), "✅ Bot restarted. 1-by-1 Candle Tracker ON. You will get a message EVERY 1 minute candle.")
        except: pass
    off=0
    while True:
        try:
            ups=get_updates(off)
            for u in ups.get("result",[]):
                off=u["update_id"]+1
                if "callback_query" in u:
                    cb=u["callback_query"]; cid=cb["message"]["chat"]["id"]
                    if cb["data"]=="ON": AUTO.add(cid); send(cid,"🤖 1-by-1 ON ✅ You will get every candle.",menu())
                    else: AUTO.discard(cid); send(cid,"🛑 OFF",menu())
                elif "message" in u and u["message"].get("text"):
                    cid=u["message"]["chat"]["id"]; txt=u["message"]["text"].lower()
                    if txt in ["/start","start","hi"]: AUTO.add(cid); send(cid,"👋 <b>IB BOT - 1 BY 1 Candle Tracker</b>\n\nI will track EVERY 1-min candle for you, 1 by 1. No skipping.",menu())
        except Exception as e: print(e, flush=True); time.sleep(5)

if __name__=="__main__": main()
