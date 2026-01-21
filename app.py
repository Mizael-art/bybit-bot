from flask import Flask, request, jsonify
import requests
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from scipy.signal import argrelextrema

app = Flask(__name__)

BASE_URL = "https://api.bybit.com/v5/market"
TIMEFRAMES = {
    "15m": "15",
    "1H": "60",
    "4H": "240",
    "1D": "D"
}
LIMIT = 200

# ===============================
# UTILIDADES
# ===============================
def get_candles(symbol, interval):
    r = requests.get(f"{BASE_URL}/kline", params={
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": LIMIT
    })
    data = r.json()["result"]["list"]
    df = pd.DataFrame(data, columns=[
        "timestamp","open","high","low","close","volume","turnover"
    ])
    df = df.astype(float).sort_values("timestamp")
    return df

def add_indicators(df):
    df["ma50"] = SMAIndicator(df["close"], 50).sma_indicator()
    df["ma200"] = SMAIndicator(df["close"], 200).sma_indicator()
    df["rsi"] = RSIIndicator(df["close"]).rsi()
    macd = MACD(df["close"])
    df["macd"] = macd.macd_diff()
    stoch = StochasticOscillator(df["high"], df["low"], df["close"])
    df["stoch"] = stoch.stoch()
    return df

def structure(df):
    tops = argrelextrema(df["high"].values, np.greater, order=5)[0]
    bottoms = argrelextrema(df["low"].values, np.less, order=5)[0]

    if len(tops) < 2 or len(bottoms) < 2:
        return "Indefinida"

    t1, t2 = df.iloc[tops][-2:]["high"]
    f1, f2 = df.iloc[bottoms][-2:]["low"]

    if t2 > t1 and f2 > f1:
        return "Alta"
    elif t2 < t1 and f2 < f1:
        return "Baixa"
    else:
        return "Lateral"

# ===============================
# ENDPOINT: ANALISAR UM PAR
# ===============================
@app.route("/analyze/symbol", methods=["GET"])
def analyze_symbol():
    symbol = request.args.get("symbol")
    strategy = request.args.get("strategy", "completa")

    result = {"symbol": symbol, "strategy": strategy, "timeframes": []}

    for tf, interval in TIMEFRAMES.items():
        df = add_indicators(get_candles(symbol, interval))
        last = df.iloc[-1]

        result["timeframes"].append({
            "timeframe": tf,
            "estrutura": structure(df),
            "preco": round(last["close"], 2),
            "ma50": round(last["ma50"], 2),
            "ma200": round(last["ma200"], 2),
            "rsi": round(last["rsi"], 2),
            "macd": round(last["macd"], 4),
            "stoch": round(last["stoch"], 2)
        })

    return jsonify(result)

# ===============================
# ENDPOINT: SCANNER DE MERCADO
# ===============================
@app.route("/analyze/market", methods=["GET"])
def scan_market():
    r = requests.get(f"{BASE_URL}/instruments-info", params={"category": "linear"})
    symbols = [s["symbol"] for s in r.json()["result"]["list"] if s["quoteCoin"] == "USDT"]

    opportunities = []

    for symbol in symbols:
        try:
            df = add_indicators(get_candles(symbol, "240"))
            last = df.iloc[-1]

            if (
                structure(df) == "Alta"
                and last["close"] > last["ma50"] > last["ma200"]
                and last["rsi"] > 50
            ):
                opportunities.append({
                    "symbol": symbol,
                    "preco": round(last["close"], 2),
                    "estrutura": "Alta"
                })
        except:
            continue

    return jsonify({
        "total_encontrados": len(opportunities),
        "oportunidades": opportunities[:10]
    })

# ===============================
# START
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
