from flask import Flask, jsonify, request
import requests
import pandas as pd
import numpy as np
import os

app = Flask(__name__)

BINANCE_BASE = "https://api.binance.com"

# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================
def get_candles(symbol, interval="1h", limit=200):
    url = f"{BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)

    if r.status_code != 200:
        return None

    df = pd.DataFrame(r.json(), columns=[
        "time","open","high","low","close","volume",
        "close_time","qv","trades","tb","tq","ignore"
    ])

    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)

    return df


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    return macd_line, signal


def market_structure(df):
    highs = df["high"]
    lows = df["low"]

    swing_highs = []
    swing_lows = []

    for i in range(2, len(df)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            swing_highs.append((i, highs[i]))
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            swing_lows.append((i, lows[i]))

    structure = "Lateral"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        if swing_highs[-1][1] > swing_highs[-2][1] and swing_lows[-1][1] > swing_lows[-2][1]:
            structure = "Alta (HH / HL)"
        elif swing_highs[-1][1] < swing_highs[-2][1] and swing_lows[-1][1] < swing_lows[-2][1]:
            structure = "Baixa (LH / LL)"

    return structure, swing_highs[-2:], swing_lows[-2:]


# ======================================================
# HEALTH CHECK
# ======================================================
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "Help Trade IA",
        "engine": "Binance Public API"
    })


# ======================================================
# ANALISAR UM PAR
# ======================================================
@app.route("/analyze")
def analyze():
    symbol = request.args.get("symbol", "").upper()
    tf = request.args.get("timeframe", "1h")

    if not symbol:
        return jsonify({"error": "Use ?symbol=BTCUSDT"}), 400

    df = get_candles(symbol, tf)
    if df is None:
        return jsonify({"error": "Erro ao buscar dados"}), 500

    df["rsi"] = rsi(df["close"])
    df["macd"], df["signal"] = macd(df["close"])
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()

    structure, tops, bottoms = market_structure(df)

    trend = "Lateral"
    if df["ma50"].iloc[-1] > df["ma200"].iloc[-1]:
        trend = "Alta"
    elif df["ma50"].iloc[-1] < df["ma200"].iloc[-1]:
        trend = "Baixa"

    return jsonify({
        "symbol": symbol,
        "timeframe": tf,
        "price": df["close"].iloc[-1],
        "structure": structure,
        "trend": trend,
        "tops": tops,
        "bottoms": bottoms,
        "indicators": {
            "rsi": round(df["rsi"].iloc[-1], 2),
            "macd": round(df["macd"].iloc[-1], 4),
            "signal": round(df["signal"].iloc[-1], 4),
            "ma50": round(df["ma50"].iloc[-1], 2),
            "ma200": round(df["ma200"].iloc[-1], 2),
            "volume": df["volume"].iloc[-1]
        },
        "risk_management": {
            "monthly_target": "10% a 15%",
            "risk_per_trade": "1% a 5%",
            "rr_min": "1:3"
        },
        "note": "Análise técnica automatizada. Trade apenas com confluência."
    })


# ======================================================
# SCANNER – TODOS OS PARES USDT
# ======================================================
@app.route("/scan/market")
def scan_market():
    info = requests.get(f"{BINANCE_BASE}/api/v3/exchangeInfo").json()
    symbols = [s["symbol"] for s in info["symbols"]
               if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]

    opportunities = []

    for symbol in symbols[:50]:  # limite para não sobrecarregar
        df = get_candles(symbol, "1h", 150)
        if df is None:
            continue

        df["rsi"] = rsi(df["close"])
        structure, _, _ = market_structure(df)

        if df["rsi"].iloc[-1] < 30 and structure == "Alta (HH / HL)":
            opportunities.append({
                "symbol": symbol,
                "setup": "Pullback em tendência de alta",
                "rsi": round(df["rsi"].iloc[-1], 2)
            })

        if df["rsi"].iloc[-1] > 70 and structure == "Baixa (LH / LL)":
            opportunities.append({
                "symbol": symbol,
                "setup": "Pullback em tendência de baixa",
                "rsi": round(df["rsi"].iloc[-1], 2)
            })

    return jsonify({
        "total_opportunities": len(opportunities),
        "opportunities": opportunities
    })


# ======================================================
# START
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
