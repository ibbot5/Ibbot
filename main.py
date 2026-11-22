import os, time, json, urllib.request, urllib.parse, threading, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import yfinance as yf
import pandas as pd
import numpy as np

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

# DR STYLE - GBP/JPY OTC - FOR POCKET OPTION
PAIR_NAME = "GBP/JPY (OTC)"
YAHOO = "GBPJPY=X"

AUTO = set()
if MY_CHAT_ID != "YOUR_CHAT_ID_HERE":
    try: AUTO.add(int(MY_CHAT_ID))
    except: pass
LAST_MIN = -1

def send(cid, text, markup=None):
    try:
        d={"chat_id":cid,"text":text,"parse_mode":"HTML"}
        if markup: d["reply_markup"]=json.dumps(markup)
        req=urllib.request.Request(BASE+"/sendMessage", data=urllib.parse.urlencode(d).encode(), headers={"Content-Type":"application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e: print(e, flush=True)

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

def dr_predict():
    try:
        df=yf.download(YAHOO, period="1d", interval="1m", progress=False)
        if df is None or len(df)<30: return None
        try: df.columns=df.columns.droplevel(1)
        except: pass
        df['ma']=df['Close'].rolling(10).mean()
        rsi=rsi_calc(df['Close'])
        o=df['Open'].iloc[-4:-1].tolist(); c=df['Close'].iloc[-4:-1].tolist()
        h=df['High'].iloc[-4:-1].tolist(); l=df['Low'].iloc[-4:-1].tolist()
        O,C,H,L = o[-1],c[-1],h[-1],l[-1]
        O1,C1 = o[-2],c[-2]
        O2,C2 = o[-3],c[-3]
        body=abs(C-O)
        upper=H-max(O,C); lower=min(O,C)-L
        is_green=C>O; is_red=C<O
