
# -*- coding: utf-8 -*-

import os
import base64
import mimetypes
import hmac
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from email.message import EmailMessage

from itsdangerous import URLSafeTimedSerializer
from itsdangerous import BadSignature, SignatureExpired

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


app = Flask(__name__)

# Limite complessivo richiesta: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Configurazione CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://plinio258.github.io"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Mittente Gmail
MITTENTE = "plinio.at.258@gmail.com"

# Limite singolo allegato: 9 MB
MAX_ALLEGATO = 9 * 1024 * 1024

# Durata autorizzazione: 2 ore
DURATA_ACCESSO = 2 * 60 * 60


# --------------------------------------------------
# CONFIGURAZIONE PASSWORD
# --------------------------------------------------

PASSWORD_ACCESSO = os.environ.get("PASSWORD_ACCESSO")
SECRET_KEY = os.environ.get("SESSION_SECRET")

if not PASSWORD_ACCESSO or not SECRET_KEY:
    raise RuntimeError(
        "PASSWORD_ACCESSO o SESSION_SECRET mancanti su Render"
    )

serializzatore = URLSafeTimedSerializer(
    SECRET_KEY,
    salt="protezione-invio-email"
)


# --------------------------------------------------
# CONTROLLO AUTENTICAZIONE
# --------------------------------------------------

def richiedi_accesso(f):

    @wraps(f)
    def funzione_protetta(*args, **kwargs):

        autorizzazione = request.headers.get(
            "Authorization", ""
        )

        if not autorizzazione.startswith("Bearer "):
            return jsonify({
                "errore": "Accesso non autorizzato"
            }), 401

        token = autorizzazione[7:].strip()

        try:

            dati = serializzatore.loads(
                token,
                max_age=DURATA_ACCESSO
            )

            if dati.get("autenticato") is not True:
                raise BadSignature("Token non valido")

        except SignatureExpired:

            return jsonify({
                "errore": "Sessione scaduta. Effettua nuovamente l'accesso."
            }), 401

        except BadSignature:

            return jsonify({
                "errore": "Accesso non autorizzato"
            }), 401

        return f(*args, **kwargs)

    return funzione_protetta


# --------------------------------------------------
# PAGINA PRINCIPALE
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "stato": "Servizio email attivo con Gmail API"
    })


# --------------------------------------------------
# ACCESSO CON PASSWORD
# --------------------------------------------------

@app.route("/login", methods=["POST"])
def login():

    dati = request.get_json(silent=True) or {}

    password = dati.get("password")

    if not isinstance(password, str):
        return jsonify({
            "errore": "Inserisci la password"
        }), 400

    if not hmac.compare_digest(
        password,
        PASSWORD_ACCESSO
    ):

        return jsonify({
            "errore": "Password non corretta"
        }), 401

    token = serializzatore.dumps({
        "autenticato": True
    })

    return jsonify({
        "messaggio": "Accesso autorizzato",
        "token": token
    }), 200


# --------------------------------------------------
# VERIFICA ACCESSO
# --------------------------------------------------

@app.route("/verifica-accesso", methods=["GET"])
@richiedi_accesso
def verifica_accesso():

    return jsonify({
        "autenticato": True
    }), 200


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
# INVIO EMAIL PROTETTO DA PASSWORD
# --------------------------------------------------

@app.route("/invia", methods=["POST"])
@richiedi_accesso
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
