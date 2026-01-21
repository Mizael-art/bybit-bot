from flask import Flask, jsonify, request
import requests
import pandas as pd
import numpy as np
import os

app = Flask(__name__)
BINANCE = "https://api.binance.com"

# ======================================================
# DADOS DE MERCADO
# ======================================================
def get_candles(symbol, tf="1h", limit=300):
    url = f"{BINANCE}/api/v3/klines"
    params = {"symbol": symbol, "interval": tf, "limit": limit}
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


# ======================================================
# INDICADORES
# ======================================================
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


# ======================================================
# ESTRUTURA + TOPOS E FUNDOS
# ======================================================
def market_structure(df):
    highs, lows = df["high"], df["low"]
    tops, bottoms = [], []

    for i in range(2, len(df)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            tops.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            bottoms.append(lows[i])

    structure = "Lateral / Confusa"
    if len(tops) >= 2 and len(bottoms) >= 2:
        if tops[-1] > tops[-2] and bottoms[-1] > bottoms[-2]:
            structure = "Alta (HH + HL)"
        elif tops[-1] < tops[-2] and bottoms[-1] < bottoms[-2]:
            structure = "Baixa (LH + LL)"

    return structure, tops[-2:], bottoms[-2:]


# ======================================================
# CONFLUÊNCIA
# ======================================================
def confluence_score(df, structure):
    score = 0
    reasons = []

    if structure.startswith("Alta") or structure.startswith("Baixa"):
        score += 1
        reasons.append("Estrutura clara")

    if df["ma50"].iloc[-1] > df["ma200"].iloc[-1]:
        score += 1
        reasons.append("Média 50 acima da 200")

    if df["rsi"].iloc[-1] < 30 or df["rsi"].iloc[-1] > 70:
        score += 1
        reasons.append("RSI extremo")

    if df["volume"].iloc[-1] > df["volume"].rolling(20).mean().iloc[-1]:
        score += 1
        reasons.append("Volume acima da média")

    return score, reasons


# ======================================================
# HOME
# ======================================================
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot": "Help Trade IA",
        "mode": "Análise técnica conservadora"
    })


# ======================================================
# ANÁLISE DE UM PAR
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
    score, reasons = confluence_score(df, structure)

    decision = "Esperar"
    if score >= 3:
        decision = "Cenário interessante (avaliar entrada)"
    if score < 2:
        decision = "Cenário fraco – NÃO operar"

    return jsonify({
        "symbol": symbol,
        "timeframe": tf,
        "price": df["close"].iloc[-1],
        "structure": structure,
        "tops": tops,
        "bottoms": bottoms,
        "indicators": {
            "rsi": round(df["rsi"].iloc[-1], 2),
            "macd": round(df["macd"].iloc[-1], 4),
            "ma50": round(df["ma50"].iloc[-1], 2),
            "ma200": round(df["ma200"].iloc[-1], 2),
            "volume": df["volume"].iloc[-1]
        },
        "confluence": {
            "score": score,
            "factors": reasons
        },
        "decision": decision,
        "risk_rules": {
            "max_risk": "1% a 3%",
            "rr_min": "1:3",
            "note": "Nunca aumentar risco com mais confiança"
        }
    })


# ======================================================
# SCANNER DE MERCADO
# ======================================================
@app.route("/scan/market")
def scan_market():
    info = requests.get(f"{BINANCE}/api/v3/exchangeInfo").json()
    symbols = [s["symbol"] for s in info["symbols"]
               if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]

    results = []

    for symbol in symbols[:40]:
        df = get_candles(symbol, "1h", 200)
        if df is None:
            continue

        df["rsi"] = rsi(df["close"])
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()

        structure, _, _ = market_structure(df)
        score, _ = confluence_score(df, structure)

        if score >= 3:
            results.append({
                "symbol": symbol,
                "structure": structure,
                "rsi": round(df["rsi"].iloc[-1], 2),
                "price": df["close"].iloc[-1]
            })

    return jsonify({
        "setups_found": len(results),
        "results": results
    })


# ======================================================
# START
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
