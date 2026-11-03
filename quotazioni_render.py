
import os
import hmac
import yfinance as yf

from datetime import datetime
from flask import Blueprint, request, jsonify

quotazioni = Blueprint("quotazioni", __name__)


@quotazioni.route("/aggiorna_excel", methods=["POST"])
def aggiorna_excel():

    # Autenticazione
    api_key = os.environ.get("EXCEL_API_KEY")
    ricevuta = request.headers.get("X-API-Key", "")

    if not api_key or not hmac.compare_digest(api_key, ricevuta):
        return jsonify({"error": "Accesso non autorizzato"}), 401

    dati = request.get_json(silent=True) or {}
    ticker_list = dati.get("tickers", [])

    if not isinstance(ticker_list, list):
        return jsonify({"error": "Formato tickers non valido"}), 400

    if len(ticker_list) > 34:
        return jsonify({"error": "Troppe righe richieste"}), 400

    risultati = []

    for elemento in ticker_list:

        try:
            riga = int(elemento["riga"])
            simbolo = str(elemento["ticker"]).strip().upper()

            if riga < 2 or riga > 35 or len(simbolo) <= 2:
                continue

            ticker = yf.Ticker(simbolo)

            info = ticker.info
            nome = info.get("longName") or info.get("shortName")

            storico = ticker.history(period="1d")

            if storico.empty:
                raise ValueError("Quotazione non disponibile")

            prezzo = float(storico["Close"].dropna().iloc[-1])

            ts = info.get("regularMarketTime")

            if ts:
                data = datetime.fromtimestamp(ts).isoformat()
            else:
                data = storico.index[-1].isoformat()

            var_pct = info.get("regularMarketChangePercent")

            if var_pct is None:
                raise ValueError("Variazione percentuale non disponibile")

            risultati.append({
                "riga": riga,
                "ticker": simbolo,
                "nome": nome,
                "prezzo": round(prezzo, 3),
                "data": data,
                "variazione": float(var_pct)
            })

        except Exception as e:
            risultati.append({
                "riga": elemento.get("riga"),
                "ticker": elemento.get("ticker"),
                "errore": str(e)
            })

    return jsonify({"risultati": risultati})
