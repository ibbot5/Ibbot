import urllib.request, urllib.parse, json, time
import pandas as pd

TELEGRAM_TOKEN = "9062675637:AAEnNib3nE7hi2G-HhOssh0yjEkm4-0xyRU"

SYMBOLS = {
    'GBPJPY': 'GBPJPY=X',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'XAUUSD': 'GC=F'
}

def telegram_send(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except Exception as e:
        print("Send failed:", e)

def telegram_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=10"
    if offset:
        url += f"&offset={offset}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read().decode())
            return data.get('result', [])
    except:
        return []

def check_pair(name, symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1h"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        df = pd.DataFrame({'Close': closes})
        df['ma'] = df['Close'].rolling(50).mean()
        curr = float(df['Close'].iloc[-1])
        ma = float(df['ma'].iloc[-1])
        ma_old = float(df['ma'].iloc[-4])
        if curr > ma and ma > ma_old:
            return ("UP", f"{name}: UP 🟢\nPrice: {curr:.4f} above MA50, MA sloping UP")
        elif curr < ma and ma < ma_old:
            return ("DOWN", f"{name}: DOWN 🔴\nPrice: {curr:.4f} below MA50, MA sloping DOWN")
        else:
            return ("FLAT", f"{name}: FLAT ⚪\nPrice: {curr:.4f} - MA not sloping clearly, wait")
    except Exception as e:
        return ("ERROR", f"{name}: Error - {e}")

print("Bot running... Send /signal in Telegram")
offset = None

while True:
    updates = telegram_updates(offset)
    for upd in updates:
        offset = upd['update_id'] + 1
        msg = upd.get('message', {})
        text = msg.get('text', '').strip().lower().replace('/', '')
        chat_id = msg.get('chat', {}).get('id')
        if not text or not chat_id:
            continue
        print("Got command:", text)

        if text in ['signal', 'all', 'check']:
            results = [check_pair(n, s)[1] for n, s in SYMBOLS.items()]
            reply = "<b>📊 All 5 Pairs (H1 + MA50 Slope)</b>\n\n" + "\n\n".join(results)
            telegram_send(chat_id, reply)

        elif text in ['strong', 'best', 'clear']:
            strong = []
            flat = 0
            for n, s in SYMBOLS.items():
                status, result = check_pair(n, s)
                if status in ['UP', 'DOWN']:
                    strong.append(result)
                else:
                    flat += 1
            if strong:
                reply = "<b>🔥 Strong Signals Only</b>\n\n" + "\n\n".join(strong) + f"\n\n{flat} pair(s) were FLAT and hidden."
            else:
                reply = "<b>⚪ No Strong Signal Right Now</b>\n\nAll 5 pairs are FLAT. Wait and send /strong again."
            telegram_send(chat_id, reply)

        elif text.upper() in SYMBOLS:
            name = text.upper()
            _, result = check_pair(name, SYMBOLS[name])
            reply = f"<b>📊 {name} (H1 + MA50 Slope)</b>\n\n{result}"
            telegram_send(chat_id, reply)

        elif text in ['start', 'help', 'hi', 'hello']:
            reply = "<b>👋 How to use me</b>\n\n/signal - All 5 pairs\n/strong - Only clear UP/DOWN, hide FLAT\n/gbpjpy - GBPJPY only\n/eurusd - EURUSD only\n/gbpusd - GBPUSD only\n/usdjpy - USDJPY only\n/xauusd - Gold only"
            telegram_send(chat_id, reply)

    time.sleep(5)
