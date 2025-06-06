import os
import fitz  # PyMuPDF
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import telegram.error  # para capturar excepciones específicas

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cargar texto desde el PDF
def extraer_texto_pdf(ruta_pdf):
    texto = ""
    with fitz.open(ruta_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto

texto_pdf = extraer_texto_pdf("datos.pdf")

# Función que genera la respuesta con OpenAI
def buscar_respuesta(pregunta):
    prompt = f"Con base en el siguiente texto, responde la pregunta:\n\n{texto_pdf[:3000]}\n\nPregunta: {pregunta}"
    respuesta = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Eres un asistente experto que responde basándote exclusivamente en el contenido proporcionado."},
            {"role": "user", "content": prompt}
        ]
    )
    return respuesta.choices[0].message.content.strip()

# Función que responde a mensajes recibidos
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    respuesta = buscar_respuesta(pregunta)
    await update.message.reply_text(respuesta)

# Main con manejo de conflicto
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    try:
        app.run_polling()
    except telegram.error.Conflict:
        print("⚠️ ERROR: El bot ya está en ejecución en otra parte (Render, PC o Codespace).")
        print("💡 Detén las demás instancias antes de volver a ejecutar este bot.")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    main()
