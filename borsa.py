
from flask import Flask, jsonify
from flask_cors import CORS
import requests
import re
import time
import threading
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

BORSA_URL = (
    "https://www.borsaitaliana.it/borsa/"
    "obbligazioni/mot/btp/scheda"
)

cache = {}
cache_lock = threading.Lock()
CACHE_SECONDS = 600

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9",
    "Accept": "text/html,application/xhtml+xml"
})


@app.route("/")
def home():
    return "Server Borsa Italiana attivo!"


def numero_italiano(valore):

    if not valore:
        return None

    valore = valore.strip()
    valore = valore.replace(".", "").replace(",", ".")

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

    # METODO 1:
    # Prezzo visualizzato nella parte superiore della scheda
    # Esempio: 98,79 -0,15% Fase:

    pattern = (
        r"([0-9]+(?:\.[0-9]{3})*,[0-9]+)"
        r"\s+[+-]?[0-9]+,[0-9]+\s*%"
        r"\s+Fase\s*:"
    )

    match = re.search(
        pattern,
        testo,
        re.IGNORECASE
    )

    if match:
        return numero_italiano(match.group(1))

    # METODO 2:
    # Primo contratto della giornata
    # Esempio: 17:35:29 98,79 -0,15%

    pattern = (
        r"\d{2}:\d{2}:\d{2}\s+"
        r"([0-9]+(?:\.[0-9]{3})*,[0-9]+)"
        r"\s+[+-]?[0-9]+,[0-9]+\s*%"
    )

    match = re.search(
        pattern,
        testo
    )

    if match:
        return numero_italiano(match.group(1))

    return None


@app.route("/isin/<isin>")
def quote_obbligazione(isin):

    isin = isin.strip().upper()

    if len(isin) != 12 or not isin.isalnum():
        return jsonify({
            "error": "ISIN non valido"
        }), 400

    # CACHE
    with cache_lock:

        elemento = cache.get(isin)

        if (
            elemento
            and time.time() - elemento["time"] < CACHE_SECONDS
        ):

            return jsonify({
                "isin": isin,
                "bid": elemento["bid"]
            })

    url = f"{BORSA_URL}/{isin}-MOTX.html?lang=it"

    try:

        response = session.get(
            url,
            timeout=25
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # Verifica ISIN
        if isin not in response.text.upper():

            return jsonify({
                "isin": isin,
                "error": "ISIN non trovato nella pagina"
            }), 404

        # Estrazione ultimo prezzo
        prezzo = estrai_prezzo(soup)

        if prezzo is None:

            return jsonify({
                "isin": isin,
                "error": "Ultimo prezzo non trovato",
                "detail": "Struttura pagina Borsa Italiana non riconosciuta"
            }), 404

        # CACHE
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
