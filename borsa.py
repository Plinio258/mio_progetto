
from flask import Flask, jsonify
from flask_cors import CORS
import requests
import re
import time
import threading
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

BORSA_URL = "https://www.borsaitaliana.it/borsa/obbligazioni/mot/btp/scheda"

cache = {}
cache_lock = threading.Lock()
CACHE_SECONDS = 600

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9"
})


@app.route("/")
def home():
    return "Server Borsa Italiana attivo!"


def prezzo_italiano(valore):

    if not valore:
        return None

    valore = valore.strip().replace(".", "").replace(",", ".")

    try:
        return float(valore)
    except ValueError:
        return None


def estrai_prezzo(soup):

    testo = re.sub(
        r"\s+",
        " ",
        soup.get_text(" ", strip=True)
    )

    # Ricerca del prezzo ultimo contratto
    pattern = (
        r"Prezzo Ultimo Contratto\s*:?\s*"
        r"([0-9]+(?:\.[0-9]{3})*,[0-9]+)"
    )

    match = re.search(
        pattern,
        testo,
        re.IGNORECASE
    )

    if match:
        return prezzo_italiano(match.group(1))

    # Ricerca alternativa nelle tabelle
    for row in soup.find_all("tr"):

        celle = row.find_all(["td", "th"])

        for i, cella in enumerate(celle):

            nome = cella.get_text(" ", strip=True)

            if "Prezzo Ultimo Contratto" in nome:

                if i + 1 < len(celle):

                    valore = celle[i + 1].get_text(
                        " ", strip=True
                    )

                    return prezzo_italiano(valore)

    return None


@app.route("/isin/<isin>")
def quote_obbligazione(isin):

    isin = isin.strip().upper()

    if len(isin) != 12 or not isin.isalnum():
        return jsonify({"error": "ISIN non valido"}), 400

    now = time.time()

    with cache_lock:
        elemento = cache.get(isin)

        if elemento and now - elemento["time"] < CACHE_SECONDS:
            return jsonify({
                "isin": isin,
                "bid": elemento["bid"]
            })

    url = f"{BORSA_URL}/{isin}-MOTX.html?lang=it"

    try:

        response = session.get(url, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        if isin not in response.text.upper():
            return jsonify({
                "isin": isin,
                "error": "Obbligazione non trovata"
            }), 404

        prezzo = estrai_prezzo(soup)

        if prezzo is None:
            return jsonify({
                "isin": isin,
                "error": "Prezzo non disponibile"
            }), 404

        with cache_lock:
            cache[isin] = {
                "time": time.time(),
                "bid": prezzo
            }

        return jsonify({
            "isin": isin,
            "bid": prezzo
        })

    except requests.RequestException as e:

        return jsonify({
            "isin": isin,
            "error": "Errore collegamento Borsa Italiana",
            "detail": str(e)
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
