import os
import logging
from dotenv import load_dotenv
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils.extractor import procesar_documentos, buscar_en_tablas, detectar_plantilla

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Inicializar cliente OpenAI
client = openai.OpenAI(api_key=OPENAI_KEY)

# Procesar documentos al arrancar
documentos_texto, documentos_tablas = procesar_documentos("documentos")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola, soy un bot especializado en asesoría legal. Puedes hacerme preguntas sobre aduanas, tributos internos, criptoactivos o legitimación de capitales."
    )

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    try:
        # Paso 1: Buscar coincidencias en tablas
        resultado_tabla = buscar_en_tablas(documentos_tablas, pregunta)
        if resultado_tabla:
            await update.message.reply_text(resultado_tabla)
            return

        # Paso 2: Consultar modelo con contexto de documentos
        contexto = "\n".join([texto[:1000] for _, texto in documentos_texto])
        prompt = (
            "Responde como asesor legal en base a los siguientes manuales técnicos. "
            "Si detectas que el usuario puede necesitar una plantilla o formulario, indícalo claramente.\n\n"
            + contexto +
            f"\n\nPregunta del usuario: {pregunta}"
        )

        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente legal experto en procedimientos administrativos."},
                {"role": "user", "content": prompt}
            ]
        )
        texto_respuesta = respuesta.choices[0].message.content.strip()

        # Paso 3: Verificar si se requiere plantilla
        plantilla = detectar_plantilla(pregunta)
        if plantilla:
            ruta = os.path.join("templates", plantilla)
            if os.path.exists(ruta):
                await update.message.reply_document(document=open(ruta, "rb"), filename=plantilla, caption=texto_respuesta)
                return

        await update.message.reply_text(texto_respuesta)

    except openai.RateLimitError:
        await update.message.reply_text("Has superado el límite de uso de OpenAI. Intenta nuevamente más tarde.")
    except Exception as e:
        logging.exception("Error al procesar la pregunta")
        await update.message.reply_text("Lo siento, ha ocurrido un error procesando tu solicitud.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 8443)),
    webhook_url="https://bot-telegram-yzpk.onrender.com"
)

