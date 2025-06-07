import os
import logging
import fitz  # PyMuPDF
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI, APIError, RateLimitError
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicializar cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Cargar texto desde PDF
def cargar_pdf(ruta):
    texto = ""
    with fitz.open(ruta) as pdf:
        for pagina in pdf:
            texto += pagina.get_text()
    return texto

# Detectar si la pregunta requiere plantilla
def detectar_plantilla(pregunta):
    palabras_clave = {
        "informe técnico": "plantillas/informe_tecnico.pdf",
        "formulario de reclamación": "plantillas/formulario_reclamacion.pdf",
        "modelo de contrato": "plantillas/modelo_contrato.pdf",
        # Añadir más como quieras
    }
    for clave, ruta in palabras_clave.items():
        if clave.lower() in pregunta.lower():
            return ruta, clave
    return None, None

# Buscar respuesta con GPT-4o
def buscar_respuesta(pregunta, contexto):
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente que responde con base en un documento PDF proporcionado."},
                {"role": "user", "content": f"Pregunta: {pregunta}\n\nTexto de referencia:\n{contexto}"}
            ]
        )
        return respuesta.choices[0].message.content.strip()
    except RateLimitError:
        return "❗ Has superado el límite de uso de OpenAI. Intenta más tarde."
    except APIError as e:
        return f"❗ Error de la API de OpenAI: {str(e)}"
    except Exception as e:
        return f"❗ Error inesperado: {str(e)}"

# Manejador de mensajes
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    texto_pdf = cargar_pdf("documentos/datos_1.pdf")
    respuesta = buscar_respuesta(pregunta, texto_pdf)

    # Enviar respuesta
    await update.message.reply_text(respuesta)

    # Revisar si necesita una plantilla
    ruta, nombre = detectar_plantilla(pregunta)
    if ruta and os.path.exists(ruta):
        await update.message.reply_document(document=open(ruta, "rb"), filename=os.path.basename(ruta), caption=f"Aquí tienes la plantilla de {nombre} 📄")

# Iniciar bot
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()
