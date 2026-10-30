from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)

# Abilita il collegamento con GitHub Pages
CORS(app, resources={
    r"/*": {
        "origins": "*"
    }
})


@app.route("/")
def home():
    return "Server Yahoo Finance attivo!"


@app.route("/quote/<symbol>")
def quote(symbol):

    try:
        symbol = symbol.upper()

        ticker = yf.Ticker(symbol)

        # Recupera le ultime quotazioni
        data = ticker.history(
            period="5d",
            interval="1m",
            prepost=True
        )

        if data.empty:
            return jsonify({
                "error": "Quotazione non disponibile"
            }), 404

        # Ultimo prezzo disponibile
        close_data = data["Close"].dropna()

        if close_data.empty:
            return jsonify({
                "error": "Prezzo non disponibile"
            }), 404

        price = float(close_data.iloc[-1])

        # Recupera informazioni sul titolo
        info = ticker.fast_info

        previous_close = float(info["previous_close"])

        currency = info.get("currency", "USD")

        # Calcolo variazione
        change = price - previous_close

        change_pct = (
            change / previous_close
        ) * 100 if previous_close else 0

        # Orario ultima quotazione
        quote_time = data.index[-1].isoformat()

        timezone = str(data.index[-1].tz)

        return jsonify({
            "symbol": symbol,
            "price": price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "currency": currency,
            "quote_time": quote_time,
            "timezone": timezone
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
