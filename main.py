import os
import fitz  # PyMuPDF
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

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

# Función que genera la respuesta con OpenAI
def buscar_respuesta(pregunta):
    prompt = f"Con base en el siguiente texto, responde la pregunta:\n\n{texto_pdf[:3000]}\n\nPregunta: {pregunta}"
    respuesta = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un asistente experto que responde basándote exclusivamente en el contenido proporcionado."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content.strip()

# Función de respuesta al mensaje recibido en Telegram
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    respuesta = buscar_respuesta(pregunta)
    await update.message.reply_text(respuesta)

# Punto de entrada principal
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()

if __name__ == "__main__":
    main()
