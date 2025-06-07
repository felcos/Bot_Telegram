import os
import logging
import json
from dotenv import load_dotenv
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils.extractor import procesar_documentos, buscar_en_tablas, detectar_plantilla
from utils.extractor import cargar_json_desde_txt


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

# Cargar datos desde archivos .txt JSON

BASE_JSON_DIR = "documentos"
json_data = cargar_json_desde_txt(BASE_JSON_DIR )

# Memoria de contexto por usuario
contexto_usuario = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola, soy un bot especializado en asesoría legal. Puedes hacerme preguntas sobre aduanas, tributos internos, criptoactivos o legitimación de capitales."
    )

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    user_id = update.effective_user.id

    try:
        # Paso 1: Buscar coincidencias en tablas
        resultado_tabla = buscar_en_tablas(pregunta, documentos_tablas)
        if resultado_tabla:
            contexto_usuario[user_id] = pregunta
            await update.message.reply_text(resultado_tabla)
            return

        # Paso 2: Buscar en datos JSON
        mejores = []
        for item in json_data:
            texto = f"{item.get('situacion', '')} {item.get('modalidad', '')}"
            simil = (len(set(pregunta.lower().split()) & set(texto.lower().split()))) / (len(set(pregunta.lower().split())) + 1)
            if simil > 0.3:
                mejores.append((simil, item))
        mejores.sort(reverse=True, key=lambda x: x[0])
        if mejores:
            item = mejores[0][1]
            contexto_usuario[user_id] = item.get('situacion') or pregunta
            respuesta_json = (
                f"Situación: {item.get('situacion')}"
                f"Incidencias/Modalidad: {item.get('modalidad')}"
                f"Procedimiento: {item.get('procedimiento')}"
                f"Referencia Legal: {item.get('referencia_legal')}"
            )
            await update.message.reply_text(respuesta_json)
            return

        # Paso 3: Si no se ubica, preguntar contexto
        if user_id not in contexto_usuario:
            await update.message.reply_text("No tengo suficiente información para ayudarte. ¿Puedes describirme la situación o modalidad legal que quieres consultar?")
            contexto_usuario[user_id] = pregunta  # guarda como posible inicio de hilo
            return

        # Paso 4: Consultar modelo con contexto de documentos
        contexto = "\n".join([texto[:1000] for _, texto in documentos_texto])
        prompt = (
            f"Responde como asesor legal en base a los siguientes manuales técnicos. "
            f"La conversación anterior fue: {contexto_usuario[user_id]}\n\n"
            f"Documentación:
{contexto}\n\n"
            f"Nueva pregunta del usuario: {pregunta}"
        )

        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente legal experto en procedimientos administrativos."},
                {"role": "user", "content": prompt}
            ]
        )
        texto_respuesta = respuesta.choices[0].message.content.strip()
        contexto_usuario[user_id] = pregunta

        # Paso 5: Verificar si se requiere plantilla
        plantilla = detectar_plantilla(pregunta)
        if plantilla:
            ruta = os.path.join("templates", plantilla)
            if os.path.exists(ruta):
                await update.message.reply_document(document=open(ruta, "rb"), filename=plantilla, caption="Aquí tienes el archivo solicitado.")
                await update.message.reply_text(texto_respuesta)
                return
            else:
                texto_respuesta += "\n\nNota: Se menciona un documento que no está disponible. Por favor, contacta con el administrador para subirlo."

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
