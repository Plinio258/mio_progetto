
import os
import smtplib

from flask import Flask, request, jsonify
from flask_cors import CORS
from email.message import EmailMessage

app = Flask(__name__)

# Limite richiesta: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Configurazione CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://plinio258.github.io"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


# Verifica servizio
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "stato": "Servizio email attivo"
    })


# Verifica connessione POST
@app.route("/test", methods=["POST"])
def test():
    return jsonify({
        "stato": "Connessione POST funzionante"
    })


# Invio email
@app.route("/invia", methods=["POST"])
def invia():

    destinatario = request.form.get("destinatario")
    oggetto = request.form.get("oggetto")
    contenuto = request.form.get("contenuto")

    mittente = request.form.get("mittente")
    password = request.form.get("password")

    if not destinatario or not oggetto or not contenuto:
        return jsonify({"errore": "Compila tutti i campi"}), 400

    if not mittente or not password:
        return jsonify({"errore": "Inserire email e password"}), 400

    msg = EmailMessage()

    msg["From"] = mittente
    msg["To"] = destinatario
    msg["Subject"] = oggetto

    msg.set_content(contenuto)

    allegato = request.files.get("allegato")

    if allegato and allegato.filename:

        if not allegato.filename.lower().endswith(".pdf"):
            return jsonify({"errore": "Sono ammessi solo PDF"}), 400

        dati = allegato.read()

        if len(dati) > 9 * 1024 * 1024:
            return jsonify({"errore": "PDF troppo grande"}), 400

        msg.add_attachment(
            dati,
            maintype="application",
            subtype="pdf",
            filename=os.path.basename(allegato.filename)
        )

    try:

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:

            server.starttls()
            server.login(mittente, password)
            server.send_message(msg)

        return jsonify({
            "messaggio": "Email inviata correttamente"
        })

    except Exception:

        app.logger.exception("Errore durante l'invio")

        return jsonify({
            "errore": "Invio email non riuscito"
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
