import os
import fitz  # PyMuPDF
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from dotenv import load_dotenv

# Carga variables de entorno desde un archivo .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicializa el cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Carga todos los PDFs desde la carpeta "documentos"
def cargar_todos_los_pdfs(ruta="documentos"):
    contenido = ""
    for archivo in os.listdir(ruta):
        if archivo.endswith(".pdf"):
            ruta_completa = os.path.join(ruta, archivo)
            with fitz.open(ruta_completa) as doc:
                for pagina in doc:
                    contenido += pagina.get_text()
    return contenido

# Cargamos el contenido de todos los PDFs al iniciar
contenido_documentos = cargar_todos_los_pdfs()

# Función que busca una respuesta en OpenAI
def buscar_respuesta(pregunta):
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": "Responde usando solo la información contenida en los documentos PDF proporcionados."},
        {"role": "user", "content": f"Contenido del documento:\n{contenido_documentos}"},
        {"role": "user", "content": f"Pregunta: {pregunta}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",  # Cambia a gpt-4o si tienes acceso
        messages=messages,
        temperature=0
    )

    return response.choices[0].message.content.strip()

# Manejador del bot de Telegram
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    respuesta = buscar_respuesta(pregunta)
    await update.message.reply_text(respuesta)

# Punto de entrada principal
if __name__ == "__main__":
    print("Bot arrancando...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()
