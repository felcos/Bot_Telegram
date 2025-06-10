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
APELLIDOS, NOMBRES, CEDULA, RANGO, UNIDAD, TEMA = range(6)
usuarios_contexto = {}

async def mostrar_documentos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    archivos = os.listdir("templates")
    archivos = [f for f in archivos if f.endswith(".docx") or f.endswith(".pdf") or f.endswith(".txt") or f.endswith(".xls")]

    if not archivos:
        await query.edit_message_text("No hay documentos disponibles para descargar.")
        return

    botones = [
        [InlineKeyboardButton(f"📎 {nombre}", callback_data=f"descargar_{i}")]
        for i, nombre in enumerate(archivos)
    ]
    context.user_data['documentos_disponibles'] = archivos

    await query.edit_message_text("Selecciona el documento que deseas descargar:", reply_markup=InlineKeyboardMarkup(botones))

async def descargar_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    index = int(query.data.replace("descargar_", ""))
    archivos = context.user_data.get('documentos_disponibles', [])

    if index < len(archivos):
        archivo = archivos[index]
        ruta = os.path.join("templates", archivo)
        if os.path.exists(ruta):
            await query.message.reply_document(document=open(ruta, "rb"), filename=archivo)
        else:
            await query.edit_message_text("No se pudo encontrar el archivo.")
    else:
        await query.edit_message_text("Índice de documento inválido.")

async def volver_al_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Consulta guiada", callback_data="iniciar_consulta_callback")],
        [InlineKeyboardButton("Consulta libre", callback_data="consulta_libre")]
    ]

    await query.edit_message_text(
        "👮‍♂️ Has vuelto al menú principal. ¿Cómo deseas continuar?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Consulta guiada", callback_data="iniciar_consulta_callback")],
        [InlineKeyboardButton("Consulta libre", callback_data="consulta_libre")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "👮‍♂️ Bienvenido. Soy un bot de apoyo legal para la Guardia Nacional Bolivariana.\n\n¿Deseas iniciar una consulta?",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "👮‍♂️ Bienvenido. Soy un bot de apoyo legal para la Guardia Nacional Bolivariana.\n\n¿Deseas iniciar una consulta?",
            reply_markup=reply_markup
        )

async def iniciar_consulta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id in usuarios_contexto and 'rango' in usuarios_contexto[user_id]:
        keyboard = [
            [InlineKeyboardButton("Legitimación", callback_data='tema_capitales'),
             InlineKeyboardButton("Criptoactivos", callback_data='tema_cripto')],
            [InlineKeyboardButton("Tributos", callback_data='tema_tributos'),
             InlineKeyboardButton("Aduana", callback_data='tema_aduana')],
        ]
        await query.edit_message_text("¿Sobre qué tema es tu nueva consulta?", reply_markup=InlineKeyboardMarkup(keyboard))
        return TEMA
    else:
        await query.edit_message_text("Indica tus apellidos:")
        return APELLIDOS


async def tipo_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data
    user_id = query.from_user.id
    usuarios_contexto[query.from_user.id]['modo'] = modo
    if modo == "consulta_libre":
        await query.edit_message_text("Perfecto, puedes comenzar tu consulta escribiéndola aquí.")
        return ConversationHandler.END

async def iniciar_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in usuarios_contexto and 'rango' in usuarios_contexto[user_id]:
        await update.message.reply_text("¿Sobre qué tema es tu nueva consulta?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Legitimación", callback_data='tema_capitales'),
             InlineKeyboardButton("Criptoactivos", callback_data='tema_cripto')],
            [InlineKeyboardButton("Tributos", callback_data='tema_tributos'),
             InlineKeyboardButton("Aduana", callback_data='tema_aduana')],
        ]))
        return TEMA
    else:
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
    await update.message.reply_text("Grado o Gerarquía:")
    return RANGO

async def guardar_rango(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['rango'] = update.message.text
    await update.message.reply_text("Unidad de adscripción:")
    return UNIDAD

def dividir_lineas(texto, largo=60):
    partes = texto.strip().split(". ", 1)
    if len(partes) > 1:
        return partes[0] + ".\n" + partes[1][:largo]
    return texto[:largo] + "\n"


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
        InlineKeyboardButton("Legitimación", callback_data='tema_capitales'),
        InlineKeyboardButton("Criptoactivos", callback_data='tema_cripto')
    ], [
        InlineKeyboardButton("Tributos", callback_data='tema_tributos'),
        InlineKeyboardButton("Aduana", callback_data='tema_aduana')
    ]]
    await update.message.reply_text("¿Sobre qué tema es tu consulta?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TEMA

async def continuar_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("Legitimación", callback_data='tema_capitales'),
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
    user_id = query.from_user.id
    usuarios_contexto[user_id]['tema'] = tema

    # Si el modo ya es guiado, no se pregunta de nuevo
    if usuarios_contexto[user_id].get("modo") == "guiado":
        return await mostrar_situaciones(update, context)
    await mostrar_situaciones(update, context)
    return "ELEGIR_SITUACION"


async def tipo_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    modo = query.data
    user_id = query.from_user.id
    usuarios_contexto[query.from_user.id]['modo'] = modo
    if modo == "consulta_guiada":
        return await mostrar_situaciones(update, context)
    await query.edit_message_text("Perfecto, puedes comenzar tu consulta escribiéndola aquí.")
    return ConversationHandler.END

def dividir_respuesta(texto, limite=4000):
    partes = []
    while len(texto) > limite:
        corte = texto.rfind("\n", 0, limite)
        if corte == -1:
            corte = limite
        partes.append(texto[:corte])
        texto = texto[corte:].lstrip()
    if texto:
        partes.append(texto)
    return partes


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
            respuesta_completa = prefijo + resultado_tabla
            for parte in dividir_respuesta(respuesta_completa):
                await update.message.reply_text(parte)
            return

        # Búsqueda por similitud en json_data
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
            respuesta_completa = prefijo + respuesta_json
            for parte in dividir_respuesta(respuesta_completa):
                await update.message.reply_text(parte)
            return

        # Si no encontró nada en el JSON ni tabla, se pregunta al modelo
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
                for parte in dividir_respuesta(prefijo + texto_respuesta):
                    await update.message.reply_text(parte)
                return
            else:
                texto_respuesta += "\n\nNota: El documento solicitado no está disponible. Contacta con el administrador."

        for parte in dividir_respuesta(prefijo + texto_respuesta):
            await update.message.reply_text(parte)

    except openai.RateLimitError:
        await update.message.reply_text("Has superado el límite de uso de OpenAI. Intenta más tarde.")
    except Exception as e:
        logging.exception("Error al procesar la pregunta")
        await update.message.reply_text("Lo siento, ha ocurrido un error procesando tu solicitud.")



from telegram.ext import CallbackContext  # Si no está importado aún
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.error import BadRequest

async def mostrar_procedimiento_y_referencia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tema = usuarios_contexto[user_id]['tema']
    situacion = usuarios_contexto[user_id]['situacion']
    index = int(query.data.replace("modalidad_", ""))
    modalidad = usuarios_contexto[user_id]['modalidades'][index]


    for item in json_data:
        if item.get("origen") == tema and item.get("situacion") == situacion and item.get("modalidad") == modalidad:
            procedimiento = item.get("procedimiento", "No se encontró el procedimiento.")
            referencia = item.get("referencia_legal", "No hay referencias legales.")
            texto = f"✅ *Procedimiento:*\n{procedimiento}\n\n📜 *Referencia Legal:*\n{referencia}"
            partes = dividir_respuesta(texto)
            try:
                await query.edit_message_text(partes[0], parse_mode="Markdown")
                for parte in partes[1:]:
                    await query.message.reply_text(parte, parse_mode="Markdown")
            except BadRequest as e:
                if "Message_too_long" in str(e):
                    for parte in partes:
                        await query.message.reply_text(parte, parse_mode="Markdown")
                else:
                    raise
            return
    await query.edit_message_text("No se encontró información detallada para esa modalidad.")


async def mostrar_situaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tema = usuarios_contexto[user_id]['tema']

    # Filtrar situaciones únicas del tema seleccionado
    situaciones = list(set(
        item['situacion'] for item in json_data if tema in item.get('origen', '').lower()
    ))
    situaciones.sort()

    if not situaciones:
        keyboard = [
            [InlineKeyboardButton("📄 Descargar un documento", callback_data="mostrar_documentos")],
            [InlineKeyboardButton("🔁 Nueva consulta guiada", callback_data="iniciar_consulta_callback")]
        ]
        await query.message.reply_text(
            "¿No se encontraron Situaciones para este tema, Desea realizar otra acción?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    
    situaciones_filtradas = sorted(set(item['situacion'] for item in json_data if item.get('origen', '').lower() == tema))
    usuarios_contexto[user_id]['situaciones'] = situaciones_filtradas  # Guardamos la lista completa

    keyboard = [
        [InlineKeyboardButton(dividir_lineas(s), callback_data=f"situacion_{i}")]
        for i, s in enumerate(situaciones_filtradas[:25])
    ]

    await query.edit_message_text("Selecciona la situación:", reply_markup=InlineKeyboardMarkup(keyboard))
    return "ELEGIR_SITUACION"


async def mostrar_modalidades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tema = usuarios_contexto[user_id]['tema']

    index = int(query.data.replace("situacion_", ""))
    situacion = usuarios_contexto[user_id]['situaciones'][index]
    usuarios_contexto[user_id]['situacion'] = situacion

    # Buscar modalidades relacionadas
    modalidades = [
        item['modalidad']
        for item in json_data
        if 'modalidad' in item and item.get('situacion') == situacion and item.get('origen', '').lower() == tema
    ]


    if not modalidades:
        keyboard = [
            [InlineKeyboardButton("📄 Descargar un documento", callback_data="mostrar_documentos")],
            [InlineKeyboardButton("🔁 Nueva consulta guiada", callback_data="iniciar_consulta_callback")]
        ]
        await query.message.reply_text(
            "¿No se encontraron Modalidades para esta situación, Desea realizar otra acción?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return ConversationHandler.END

    modalidades_filtradas = sorted(set(
        item['modalidad'] for item in json_data
        if item.get('situacion') == situacion and item.get('origen', '').lower() == tema
    ))
    usuarios_contexto[user_id]['modalidades'] = modalidades_filtradas


    usuarios_contexto[user_id]['modalidades'] = modalidades_filtradas  # Guardamos la lista completa
    botones = [
        [InlineKeyboardButton(dividir_lineas(s), callback_data=f"modalidad_{i}")]
        for i, s in enumerate(modalidades_filtradas[:25])
    ]

    context.user_data["modalidades_filtradas"] = modalidades
    await query.edit_message_text("Selecciona la modalidad/incidencia:", reply_markup=InlineKeyboardMarkup(botones))

    return "ELEGIR_MODALIDAD"

async def mostrar_resultado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    index = int(query.data.replace("modalidad_", ""))
    modalidad = usuarios_contexto[user_id]['modalidades'][index]
    situacion = usuarios_contexto[user_id]['situacion']
    tema = usuarios_contexto[user_id]['tema']

    encontrado = False

    for item in json_data:
        if (
            item.get('situacion') == situacion and
            item.get('modalidad') == modalidad and
            item.get('origen', '').lower() == tema
        ):
            texto = (
                f"📘 *Consulta guiada completada*\n"
                f"────────────────────────────\n"
                f"🗂 *Tema:* {tema.capitalize()}\n"
                f"📌 *Situación:* {situacion}\n"
                f"🧷 *Modalidad / Incidencia:* {modalidad}\n"
                f"────────────────────────────\n"
                f"✅ *Procedimiento:*\n{item.get('procedimiento', 'No disponible')}\n\n"
                f"📜 *Referencia Legal:*\n{item.get('referencia_legal', 'No disponible')}"
            )
            await query.edit_message_text(texto, parse_mode="Markdown")
            encontrado = True
            break

    if not encontrado:
        await query.edit_message_text("⚠️ No se encontró información detallada para esa combinación.")

    # Mensaje para continuar
    # Mensaje para continuar
    keyboard = [
        [InlineKeyboardButton("📄 Descargar un documento", callback_data="mostrar_documentos")],
        [InlineKeyboardButton("🔁 Nueva consulta guiada", callback_data="iniciar_consulta_callback")]
    ]
    await query.message.reply_text(
        "¿Deseas realizar otra acción?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ConversationHandler.END

import os

async def ver_logs_oculto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ruta = "log.txt"

    if not os.path.exists(ruta):
        await update.message.reply_text("El archivo de registros no existe todavía.")
        return

    if os.path.getsize(ruta) == 0:
        await update.message.reply_text("El archivo de registros está vacío.")
        return

    await update.message.reply_document(document=open(ruta, "rb"), filename="log.txt", caption="📄 Registros de consultas guiadas.")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("(?i)^consulta$"), iniciar_consulta),
            CallbackQueryHandler(iniciar_consulta_callback, pattern="^iniciar_consulta_callback$")
        ],
        states={
            APELLIDOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_apellidos)],
            NOMBRES: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nombres)],
            CEDULA: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_cedula)],
            RANGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_rango)],
            UNIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_unidad)],
            TEMA: [CallbackQueryHandler(elegir_tema, pattern="^tema_")],
            "ELEGIR_SITUACION": [CallbackQueryHandler(mostrar_modalidades, pattern="^situacion_")],
            "ELEGIR_MODALIDAD": [CallbackQueryHandler(mostrar_resultado, pattern="^modalidad_")],
        },
        fallbacks=[
            CallbackQueryHandler(volver_al_menu, pattern="^volver_menu$")
        ]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verlog", ver_logs_oculto))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    app.add_handler(CallbackQueryHandler(iniciar_consulta, pattern="^iniciar_consulta$"))
    app.add_handler(CallbackQueryHandler(volver_al_menu, pattern="^volver_menu$"))
    app.add_handler(CallbackQueryHandler(mostrar_modalidades, pattern="^situacion_"))
    app.add_handler(CallbackQueryHandler(mostrar_resultado, pattern="^modalidad_"))
    app.add_handler(CallbackQueryHandler(iniciar_consulta_callback, pattern="^iniciar_consulta_callback$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.message.reply_text("Perfecto, puedes comenzar tu consulta escribiéndola aquí."), pattern="^consulta_libre$"))
    app.add_handler(CallbackQueryHandler(mostrar_documentos, pattern="^mostrar_documentos$"))
    app.add_handler(CallbackQueryHandler(descargar_documento, pattern="^descargar_\\d+$"))




    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 18443)),
        webhook_url="https://bot-telegram-yzpk.onrender.com"
    )