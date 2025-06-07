import os
import logging
import fitz  # PyMuPDF
import openai
import telegram
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils.extractor import procesar_documentos, buscar_en_tablas, detectar_plantilla
from dotenv import load_dotenv

# Configura logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Carga variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Inicializa cliente OpenAI
client = openai.OpenAI(api_key=OPENAI_KEY)

# Procesa documentos al iniciar (una sola vez)
documentos = procesar_documentos("documentos")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hola, soy un bot especializado en asesoría legal. Puedes hacerme preguntas sobre aduanas, tributos internos, criptoactivos o legitimación de capitales.")

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    try:
        # Paso 1: Buscar en tablas de los documentos cargados
        resultado_tabla = buscar_en_tablas(documentos, pregunta)
        if resultado_tabla:
            await update.message.reply_text(resultado_tabla)
            return

        # Paso 2: Preguntar al modelo 4o con contexto de los documentos
        prompt = """Responde como asesor legal en base a los siguientes manuales técnicos. Si detectas que el usuario puede necesitar una plantilla o formulario, indícalo claramente.
        
"""
        for doc in documentos.values():
            prompt += doc[:1000] + "\n"  # recorta para no exceder tokens
        prompt += f"\nPregunta del usuario: {pregunta}"

        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente legal experto en procedimientos administrativos."},
                {"role": "user", "content": prompt}
            ]
        )
        texto_respuesta = respuesta.choices[0].message.content.strip()

        # Paso 3: Si se detecta plantilla, ofrecer archivo
        plantilla = detectar_plantilla(pregunta)
        if plantilla:
            ruta = os.path.join("templates", plantilla)
            if os.path.exists(ruta):
                await update.message.reply_document(document=open(ruta, "rb"), filename=plantilla, caption=texto_respuesta)
                return

        await update.message.reply_text(texto_respuesta)

    except openai.RateLimitError:
        await update.message.reply_text("Has superado el límite de uso de OpenAI. Intenta más tarde.")
    except Exception as e:
        logging.error(f"Error al procesar pregunta: {e}")
        await update.message.reply_text("Lo siento, ha ocurrido un error procesando tu solicitud.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()
