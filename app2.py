
from flask import Flask, jsonify
from flask_cors import CORS
import requests
import time
import threading

app = Flask(__name__)
CORS(app)

RADAR_URL = "https://radarcertificati.com/api/v1"

cache_radar = {}
cache_lock = threading.Lock()
CACHE_SECONDS = 600


@app.route("/")
def home():
    return "Server Radar Certificati attivo!"


def gruppo_isin(isin):

    valore = 2166136261

    for byte in isin.upper().encode("utf-8"):
        valore ^= byte
        valore = (valore * 16777619) & 0xFFFFFFFF

    return f"{valore % 256:02x}"


def cerca_isin(obj, isin):

    if isinstance(obj, dict):

        if str(obj.get("isin", "")).upper() == isin:
            return obj

        for valore in obj.values():
            risultato = cerca_isin(valore, isin)

            if risultato is not None:
                return risultato

    elif isinstance(obj, list):

        for elemento in obj:
            risultato = cerca_isin(elemento, isin)

            if risultato is not None:
                return risultato

    return None


def carica_gruppo(gruppo):

    now = time.time()

    with cache_lock:
        elemento = cache_radar.get(gruppo)

        if elemento and now - elemento["time"] < CACHE_SECONDS:
            return elemento["data"]

    url = f"{RADAR_URL}/isin/{gruppo}.json"

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "PortfolioDashboard/1.0"}
    )

    response.raise_for_status()

    dati = response.json()

    with cache_lock:
        cache_radar[gruppo] = {
            "time": time.time(),
            "data": dati
        }

    return dati


@app.route("/isin/<isin>")
def quote_isin(isin):

    isin = isin.strip().upper()

    if len(isin) != 12 or not isin.isalnum():
        return jsonify({"error": "ISIN non valido"}), 400

    try:

        gruppo = gruppo_isin(isin)
        dati = carica_gruppo(gruppo)

        certificato = cerca_isin(dati, isin)

        if certificato is None:
            return jsonify({
                "isin": isin,
                "error": "Certificato non trovato"
            }), 404

        bid = certificato.get("bid")

        return jsonify({
            "isin": isin,
            "bid": float(bid) if bid is not None else None,
            "currency": certificato.get("currency"),
            "priceAt": certificato.get("priceAt"),
            "updatedAt": certificato.get("updatedAt"),
            "source": certificato.get("priceSource")
                      or certificato.get("source")
                      or "Radar Certificati"
        })

    except requests.RequestException as e:

        return jsonify({
            "isin": isin,
            "error": "Errore collegamento Radar",
            "detail": str(e)
        }), 502

    except Exception as e:

        return jsonify({
            "isin": isin,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
