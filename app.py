from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime

app = Flask(__name__)

# Consente al sito GitHub di interrogare il server
CORS(app)

@app.route("/")
def home():
    return "Server quotazioni Yahoo Finance attivo"

@app.route("/quote/<symbol>")
def quote(symbol):

    try:
        ticker = yf.Ticker(symbol.upper())

        # Ultime quotazioni disponibili
        data = ticker.history(
            period="5d",
            interval="1m",
            prepost=True
        )

        if data.empty:
            return jsonify({"error": "Quotazione non disponibile"}), 404

        # Ultimo prezzo disponibile
        price = float(data["Close"].dropna().iloc[-1])

        # Informazioni sul titolo
        info = ticker.fast_info

        previous_close = float(info["previous_close"])

        change = price - previous_close
        change_pct = (change / previous_close) * 100

        currency = info.get("currency", "USD")

        quote_time = data.index[-1].isoformat()

        timezone = str(data.index[-1].tz)

        return jsonify({
            "symbol": symbol.upper(),
            "price": price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "currency": currency,
            "quote_time": quote_time,
            "timezone": timezone
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
