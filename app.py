from flask import Flask, jsonify, request
import requests
import os

app = Flask(__name__)

# ======================================================
# ROTA RAIZ - HEALTH CHECK
# ======================================================
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "Help Trade IA",
        "message": "API funcionando corretamente"
    })


# ======================================================
# SCAN DE TODOS OS PARES FUTUROS USDT (BYBIT - API PÚBLICA)
# ======================================================
@app.route("/analyze/market")
def scan_market():
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {
        "category": "linear"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if r.status_code != 200:
        return jsonify({
            "error": "Erro ao acessar API da Bybit",
            "status_code": r.status_code,
            "response": r.text
        }), 500

    try:
        data = r.json()
    except Exception:
        return jsonify({
            "error": "Resposta da Bybit não é JSON",
            "raw_response": r.text
        }), 500

    if "result" not in data or "list" not in data["result"]:
        return jsonify({
            "error": "Formato inesperado da API da Bybit",
            "response": data
        }), 500

    symbols = [
        s["symbol"]
        for s in data["result"]["list"]
        if s.get("quoteCoin") == "USDT"
    ]

    return jsonify({
        "status": "ok",
        "total_pairs": len(symbols),
        "pairs_preview": symbols[:20]  # preview
    })


# ======================================================
# ANÁLISE DE UM PAR ESPECÍFICO
# ======================================================
@app.route("/analyze")
def analyze_symbol():
    symbol = request.args.get("symbol")

    if not symbol:
        return jsonify({
            "error": "Par inválido",
            "message": "Use /analyze?symbol=BTCUSDT"
        }), 400

    # Aqui entra futuramente:
    # - Estrutura
    # - Topos e fundos
    # - Indicadores
    # - Gestão de risco
    # - Setup do usuário

    return jsonify({
        "status": "analysis_received",
        "symbol": symbol,
        "structure": "não calculada (placeholder)",
        "recommendation": "Somente análise de cenário no momento",
        "risk_management": {
            "max_risk_per_trade": "3% a 5%",
            "rr_minimum": "1:3"
        },
        "note": "Módulo de análise completa será aplicado aqui"
    })


# ======================================================
# START LOCAL (IGNORADO NO RENDER, MAS ÚTIL PARA TESTE)
# ======================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
