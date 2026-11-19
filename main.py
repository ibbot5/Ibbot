import yfinance as yf
import urllib.parse
import urllib.request
import json
import time

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
        # 5min = more reliable, 1min = fast
        if timeframe == "5m":
            period = "5d"
            interval = "5m"
        else:
            period = "2d"
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

def pair_buttons
