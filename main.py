import fitz  # PyMuPDF
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os

# --- Cargar variables de entorno ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# --- Inicializar OpenAI ---
openai.api_key = OPENAI_API_KEY

# --- Leer el PDF completo ---
def extraer_texto_pdf(ruta_pdf):
    texto = ""
    with fitz.open(ruta_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto

texto_pdf = extraer_texto_pdf("datos.pdf")

# --- Buscar respuesta con GPT ---
def buscar_respuesta(pregunta):
    prompt = f"Con base en el siguiente texto, responde a esta pregunta:\n\n{texto_pdf[:3000]}\n\nPregunta: {pregunta}"
    respuesta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return respuesta.choices[0].message.content.strip()

# --- Bot de Telegram ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    respuesta = buscar_respuesta(pregunta)
    await update.message.reply_text(respuesta)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()

if __name__ == '__main__':
    main()
