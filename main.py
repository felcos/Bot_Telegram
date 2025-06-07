import os
import logging
import fitz  # PyMuPDF para leer PDFs
import docx
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI, APIError, RateLimitError
from dotenv import load_dotenv
from utils.extractor import procesar_documentos, buscar_en_tablas, detectar_plantilla

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# Cargamos documentos al iniciar
base_conocimiento = procesar_documentos("documentos")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola. Soy un asistente legal. Puedes describirme una situación o problema legal y te diré qué procedimiento o referencia legal se aplica. Si necesitas una plantilla, también te la puedo proporcionar.")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text

    try:
        # Buscar coincidencias en las tablas
        respuesta = buscar_en_tablas(base_conocimiento, pregunta)
        if not respuesta:
            respuesta = preguntar_openai(pregunta)

        await update.message.reply_text(respuesta)

        plantilla = detectar_plantilla(base_conocimiento, pregunta)
        if plantilla:
            ruta_archivo = f"templates/{plantilla}"
            if os.path.exists(ruta_archivo):
                await update.message.reply_document(InputFile(ruta_archivo))
            else:
                await update.message.reply_text("No encontré la plantilla, pero parece que podrías necesitarla.")

    except RateLimitError:
        await update.message.reply_text("He alcanzado el límite de uso de OpenAI. Inténtalo más tarde.")
    except APIError as e:
        await update.message.reply_text("Error al consultar OpenAI.")
        logging.error(f"Error API: {e}")
    except Exception as e:
        await update.message.reply_text("Ocurrió un error inesperado.")
        logging.exception("Error general")

def preguntar_openai(pregunta):
    respuesta = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Eres un experto legal en procedimientos aduaneros, tributarios, de criptoactivos y legitimación de capitales. Responde usando solo los manuales proporcionados."},
            {"role": "user", "content": pregunta},
        ]
    )
    return respuesta.choices[0].message.content.strip()

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()
