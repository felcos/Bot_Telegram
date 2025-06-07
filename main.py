import os
import fitz  # PyMuPDF
import openai
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import telegram.error
import threading
from flask import Flask

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cargar texto desde el PDF
def extraer_texto_pdf(ruta_pdf):
    texto = ""
    with fitz.open(ruta_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto

texto_pdf = extraer_texto_pdf("datos.pdf")

# Buscar respuesta con OpenAI
def buscar_respuesta(pregunta):
    prompt = f"Con base en el siguiente texto, responde la pregunta:\n\n{texto_pdf[:3000]}\n\nPregunta: {pregunta}"
    try:
        respuesta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente experto que responde basándote exclusivamente en el contenido proporcionado."},
                {"role": "user", "content": prompt}
            ]
        )
        return respuesta.choices[0].message.content.strip()
    except openai.RateLimitError:
        return "⚠️ No puedo responder ahora mismo: se ha superado el límite de uso de OpenAI. Intenta más tarde."
    except openai.NotFoundError:
        return "❌ Error: El modelo solicitado no está disponible. Verifica tu acceso a gpt-4o."
    except openai.APIError as e:
        return f"❌ Error de OpenAI: {e}"
    except openai.OpenAIError as e:
        return f"❌ Error general de OpenAI: {e}"

# Función que responde en Telegram
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    respuesta = buscar_respuesta(pregunta)
    await update.message.reply_text(respuesta)

# Inicializar el bot
def iniciar_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    try:
        app.run_polling()
    except telegram.error.Conflict:
        print("⚠️ El bot ya está ejecutándose en otra parte. Detén otras instancias.")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

# Servidor Flask mínimo para Render
app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot de Telegram activo en Render"

def iniciar_flask():
    app_web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# Ejecutar bot + servidor Flask
if __name__ == "__main__":
    threading.Thread(target=iniciar_flask).start()
    iniciar_bot()
