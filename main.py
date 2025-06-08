import os
import logging
import json
from dotenv import load_dotenv
import openai
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from utils.extractor import procesar_documentos, buscar_en_tablas, detectar_plantilla, cargar_json_desde_txt

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

# Variables de sesión
usuario_info = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola, soy un bot especializado en asesoría legal. Puedes hacerme preguntas sobre aduanas, tributos internos, criptoactivos o legitimación de capitales."
    )

async def manejar_documentacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.message.text
    tema = mensaje.split("documentar", 1)[-1].strip()
    if not tema:
        await update.message.reply_text("¿Qué tema necesitas documentar?")
        return

    campos_comunes = ["Fecha", "Hora", "Lugar", "Unidad actuante", "Funcionario actuante"]
    texto = f"\u270d\ufe0f Documento: {tema.capitalize()}\n\n"
    for campo in campos_comunes:
        texto += f"{campo}: [Por completar]\n"

    if "acta" in tema.lower():
        texto += "\nHechos constatados: [Describa brevemente los hechos]"
    elif "informe" in tema.lower():
        texto += "\nResumen del análisis: [Incluya observaciones y recomendaciones]"
    else:
        texto += "\nContenido: [Describa el contenido principal]"

    await update.message.reply_text(
        f"Aquí tienes una plantilla para documentar '{tema}':\n\n{texto}\n\nPuedes editar este mensaje y reenviarlo a tus superiores."
    )

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    global usuario_info

    if pregunta.lower().startswith("documentar"):
        await manejar_documentacion(update, context)
        return

    try:
        # Paso 1: Buscar coincidencias en tablas
        resultado_tabla = buscar_en_tablas(pregunta, documentos_tablas)
        if resultado_tabla:
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
            respuesta_json = (
                f"Situación: {item.get('situacion')}\n"
                f"Incidencias/Modalidad: {item.get('modalidad')}\n"
                f"Procedimiento: {item.get('procedimiento')}\n"
                f"Referencia Legal: {item.get('referencia_legal')}"
            )
            await update.message.reply_text(respuesta_json)
            return

        # Paso 3: Consultar modelo con contexto de documentos
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
                {"role": "system", "content": "Eres un asistente legal experto en procedimientos administrativos dela Guardia Nacional Bolivariana, estas asesorando a un agente de la guardia nacional bolivariana sobre como proceder, es de vital importancia que consigas ubicarte en situacion, modalidad o incidencia para poder responder con la información sobre el procedimiento y las bases legales y ademas ofrecer documentos que puedan ser de utilidad."},
                {"role": "user", "content": prompt}
            ]
        )
        texto_respuesta = respuesta.choices[0].message.content.strip()

        # Paso 4: Verificar si se requiere plantilla
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
