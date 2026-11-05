
# -*- coding: utf-8 -*-

import os
import base64
import mimetypes

from flask import Flask, request, jsonify
from flask_cors import CORS
from email.message import EmailMessage

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


app = Flask(__name__)

# Limite complessivo della richiesta: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Configurazione CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://plinio258.github.io"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


# Mittente Gmail
MITTENTE = "plinio.at.258@gmail.com"

# Limite singolo allegato: 9 MB
MAX_ALLEGATO = 9 * 1024 * 1024


# --------------------------------------------------
# PAGINA PRINCIPALE
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "stato": "Servizio email attivo con Gmail API"
    })


# --------------------------------------------------
# TEST CONNESSIONE
# --------------------------------------------------

@app.route("/test", methods=["POST"])
def test():

    return jsonify({
        "stato": "Connessione POST funzionante"
    })


# --------------------------------------------------
# CONNESSIONE GMAIL API
# --------------------------------------------------

def gmail_service():

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:

        raise ValueError(
            "Credenziali Google mancanti su Render"
        )

    credenziali = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[
            "https://www.googleapis.com/auth/gmail.send"
        ]
    )

    credenziali.refresh(Request())

    servizio = build(
        "gmail",
        "v1",
        credentials=credenziali,
        cache_discovery=False
    )

    return servizio


# --------------------------------------------------
# INVIO EMAIL
# --------------------------------------------------

@app.route("/invia", methods=["POST"])
def invia():

    destinatario = request.form.get("destinatario")
    oggetto = request.form.get("oggetto")
    contenuto = request.form.get("contenuto")

    if not destinatario or not oggetto or not contenuto:

        return jsonify({
            "errore": "Compila tutti i campi"
        }), 400

    # Creazione email
    msg = EmailMessage()

    msg["From"] = MITTENTE
    msg["To"] = destinatario
    msg["Subject"] = oggetto

    msg.set_content(contenuto)

    # --------------------------------------------------
    # GESTIONE ALLEGATI MULTIPLI
    # --------------------------------------------------

    allegati = request.files.getlist("allegato")

    for allegato in allegati:

        if not allegato or not allegato.filename:
            continue

        nome_file = os.path.basename(allegato.filename)

        dati = allegato.read()

        if len(dati) > MAX_ALLEGATO:

            return jsonify({
                "errore": (
                    f"Il file {nome_file} supera il limite di 9 MB"
                )
            }), 400

        if not dati:
            continue

        tipo_mime, _ = mimetypes.guess_type(nome_file)

        if tipo_mime:

            maintype, subtype = tipo_mime.split("/", 1)

        else:

            maintype = "application"
            subtype = "octet-stream"

        msg.add_attachment(
            dati,
            maintype=maintype,
            subtype=subtype,
            filename=nome_file
        )

    # --------------------------------------------------
    # INVIO TRAMITE GMAIL API HTTPS
    # --------------------------------------------------

    try:

        servizio = gmail_service()

        messaggio = base64.urlsafe_b64encode(
            msg.as_bytes()
        ).decode("utf-8")

        servizio.users().messages().send(
            userId="me",
            body={
                "raw": messaggio
            }
        ).execute()

        return jsonify({
            "messaggio": "Email inviata correttamente"
        }), 200

    except Exception:

        app.logger.exception(
            "Errore durante invio Gmail API"
        )

        return jsonify({
            "errore": "Invio email non riuscito"
        }), 500


# --------------------------------------------------
# GESTIONE FILE TROPPO GRANDI
# --------------------------------------------------

@app.errorhandler(413)
def file_troppo_grande(error):

    return jsonify({
        "errore": "Richiesta troppo grande (massimo 10 MB)"
    }), 413


# --------------------------------------------------
# AVVIO SERVER
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
