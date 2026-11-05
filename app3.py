
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

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

CORS(app, resources={
    r"/*": {
        "origins": ["https://plinio258.github.io"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "stato": "Servizio email attivo con Gmail API"
    })


@app.route("/test", methods=["POST"])
def test():
    return jsonify({
        "stato": "Connessione POST funzionante"
    })


def gmail_service():

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise ValueError("Credenziali Google mancanti su Render")

    credenziali = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"]
    )

    credenziali.refresh(Request())

    servizio = build(
        "gmail",
        "v1",
        credentials=credenziali,
        cache_discovery=False
    )

    return servizio


@app.route("/invia", methods=["POST"])
def invia():

    destinatario = request.form.get("destinatario")
    oggetto = request.form.get("oggetto")
    contenuto = request.form.get("contenuto")

    if not destinatario or not oggetto or not contenuto:
        return jsonify({
            "errore": "Compila tutti i campi"
        }), 400

    msg = EmailMessage()

    msg["From"] = "plinio.at.258@gmail.com"
    msg["To"] = destinatario
    msg["Subject"] = oggetto

    msg.set_content(contenuto)

    allegato = request.files.get("allegato")

    if allegato and allegato.filename:

        if not allegato.filename.lower().endswith(".pdf"):
            return jsonify({
                "errore": "Sono ammessi solo PDF"
            }), 400

        dati = allegato.read()

        if len(dati) > 9 * 1024 * 1024:
            return jsonify({
                "errore": "PDF troppo grande"
            }), 400

        msg.add_attachment(
            dati,
            maintype="application",
            subtype="pdf",
            filename=os.path.basename(allegato.filename)
        )

    try:

        servizio = gmail_service()

        messaggio = base64.urlsafe_b64encode(
            msg.as_bytes()
        ).decode("utf-8")

        servizio.users().messages().send(
            userId="me",
            body={"raw": messaggio}
        ).execute()

        return jsonify({
            "messaggio": "Email inviata correttamente"
        })

    except Exception:

        app.logger.exception("Errore durante invio Gmail API")

        return jsonify({
            "errore": "Invio email non riuscito"
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
