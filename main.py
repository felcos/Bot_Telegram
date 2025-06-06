import os
import fitz  # PyMuPDF
import openai
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import telegram.error

# Inicializar cliente de OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Leer el contenido del PDF
def extraer_texto_pdf(ruta_pdf):
    texto = ""
    with fitz.open(ruta_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto

texto_pdf = extraer_texto_pdf("datos.pdf")

# Buscar respuesta usando el modelo de OpenAI
def buscar_respuesta(pregunta):
    prompt = f"Con base en el siguiente texto, responde la pregunta:\n\n{texto_pdf[:3000]}\n\nPregunta: {pregunta}"
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente experto que responde basándote exclusivamente en el contenido proporcionado."},
                {"role": "user", "content": prompt}
            ]
        )
        return respuesta.choices[0].message.content.strip()

    except openai.RateLimitError:
        return "⚠️ No puedo responder ahora mismo: se ha superado el límite de uso de OpenAI. Intenta más tarde."

    except openai.NotFoundError:
        return "❌ Error: El modelo solicitado no está disponible. Revisa si tienes acceso a gpt-4o."

    except openai.APIError as e:
        return f"❌ Error de OpenAI: {e}"

    except openai.OpenAIError as e:
        return f"❌ Error general de OpenAI: {e}"

# Manejo de mensajes en Telegram
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    respuesta = buscar_respuesta(pregunta)
    await update.message.reply_text(respuesta)

# Ejecutar el bot con protección de conflicto
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    try:
        app.run_polling()
    except telegram.error.Conflict:
        print("⚠️ El bot ya está ejecutándose en otra parte (Render, Codespace o local).")
        print("💡 Detén todas las demás instancias antes de volver a ejecutar este bot.")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    main()
