import os
import logging
import json
from dotenv import load_dotenv
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler, CallbackQueryHandler
)
from utils.extractor import procesar_documentos, buscar_en_tablas, detectar_plantilla, cargar_json_desde_txt, documentar

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# Inicializar cliente OpenAI
client = openai.OpenAI(api_key=OPENAI_KEY)

# Procesar documentos
documentos_texto, documentos_tablas = procesar_documentos("documentos")

# Cargar datos desde archivos .txt JSON
BASE_JSON_DIR = "documentos"
json_data = cargar_json_desde_txt(BASE_JSON_DIR)

# Estados para ConversationHandler
APELLIDOS, NOMBRES, CEDULA, RANGO, UNIDAD, TEMA, TIPO_CONSULTA = range(7)
usuarios_contexto = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hola, soy un bot especializado en asesoría legal. Escribe 'consulta' para iniciar una nueva consulta guiada."
    )

async def iniciar_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Indica tus apellidos:")
    return APELLIDOS

async def guardar_apellidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['apellidos'] = update.message.text
    await update.message.reply_text("Ahora tus nombres:")
    return NOMBRES

async def guardar_nombres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nombres'] = update.message.text
    await update.message.reply_text("Cédula de identidad:")
    return CEDULA

async def guardar_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['cedula'] = update.message.text
    await update.message.reply_text("Rango:")
    return RANGO

async def guardar_rango(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['rango'] = update.message.text
    await update.message.reply_text("Unidad de adscripción:")
    return UNIDAD

async def guardar_unidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['unidad'] = update.message.text

    # Guardar log
    with open("log.txt", "a", encoding="utf-8") as log:
        log.write(json.dumps(context.user_data, ensure_ascii=False) + "\n")

    # Guardar contexto del usuario
    user_id = update.effective_user.id
    usuarios_contexto[user_id] = {
        "rango": context.user_data['rango'],
        "modo": "guiado"
    }

    keyboard = [[
        InlineKeyboardButton("Legitimación de Capitales", callback_data='tema_legitimacion'),
        InlineKeyboardButton("Criptoactivos", callback_data='tema_cripto')
    ], [
        InlineKeyboardButton("Tributos", callback_data='tema_tributos'),
        InlineKeyboardButton("Aduana", callback_data='tema_aduana')
    ]]
    await update.message.reply_text("¿Sobre qué tema es tu consulta?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TEMA

async def elegir_tema(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tema = query.data.replace("tema_", "")
    usuarios_contexto[query.from_user.id]['tema'] = tema

    keyboard = [[
        InlineKeyboardButton("Buscar situación y modalidad", callback_data='consulta_guiada'),
        InlineKeyboardButton("Consulta libre", callback_data='consulta_libre')
    ]]
    await query.edit_message_text("¿Cómo deseas realizar tu consulta?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TIPO_CONSULTA

async def tipo_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data
    usuarios_contexto[query.from_user.id]['modo'] = modo
    await query.edit_message_text("Perfecto, puedes comenzar tu consulta escribiéndola aquí.")
    return ConversationHandler.END

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    user_id = update.effective_user.id
    prefijo = ""
    if user_id in usuarios_contexto:
        rango = usuarios_contexto[user_id].get("rango")
        prefijo = f"Mi {rango}, "

    try:
        # Reconocimiento de solicitud de documentación
        if pregunta.lower().startswith("documentar"):
            await documentar(update, context)
            return


        resultado_tabla = buscar_en_tablas(pregunta, documentos_tablas)
        if resultado_tabla:
            await update.message.reply_text(prefijo + resultado_tabla)
            return

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
            await update.message.reply_text(prefijo + respuesta_json)
            return

        contexto = "\n".join([texto[:1000] for _, texto in documentos_texto])
        prompt = (
            "Responde como asesor legal. Si detectas que el usuario puede necesitar una plantilla, menciónala claramente.\n\n"
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

        plantilla = detectar_plantilla(pregunta)
        if plantilla:
            ruta = os.path.join("templates", plantilla)
            if os.path.exists(ruta):
                await update.message.reply_document(document=open(ruta, "rb"), filename=plantilla, caption="Aquí tienes el archivo solicitado.")
                await update.message.reply_text(prefijo + texto_respuesta)
                return
            else:
                texto_respuesta += "\n\nNota: El documento solicitado no está disponible. Contacta con el administrador."

        await update.message.reply_text(prefijo + texto_respuesta)

    except openai.RateLimitError:
        await update.message.reply_text("Has superado el límite de uso de OpenAI. Intenta más tarde.")
    except Exception as e:
        logging.exception("Error al procesar la pregunta")
        await update.message.reply_text("Lo siento, ha ocurrido un error procesando tu solicitud.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("(?i)^consulta$"), iniciar_consulta)],
        states={
            APELLIDOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_apellidos)],
            NOMBRES: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nombres)],
            CEDULA: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cedula)],
            RANGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_rango)],
            UNIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_unidad)],
            TEMA: [CallbackQueryHandler(elegir_tema)],
            TIPO_CONSULTA: [CallbackQueryHandler(tipo_consulta)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        webhook_url="https://bot-telegram-yzpk.onrender.com"
    )
