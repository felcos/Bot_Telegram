import os
import fitz  # PyMuPDF
import docx
import difflib

BASE_DIR = "documentos"
TEMPLATE_DIR = "templates"

# --- Utilidades de lectura ---
def leer_pdf(path):
    text = ""
    try:
        with fitz.open(path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception:
        pass
    return text

def leer_docx(path):
    text = ""
    try:
        doc = docx.Document(path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception:
        pass
    return text

# --- Lectura de tablas específicas ---
def extraer_tablas_docx(path):
    resultados = []
    try:
        doc = docx.Document(path)
        for table in doc.tables:
            encabezados = [cell.text.lower().strip() for cell in table.rows[0].cells]
            if all(col in encabezados for col in ["situación", "incidencias", "procedimiento", "referencia legal 2022"]):
                for row in table.rows[1:]:
                    fila = {encabezados[i]: cell.text.strip() for i, cell in enumerate(row.cells)}
                    resultados.append(fila)
    except Exception:
        pass
    return resultados

# --- Carga inicial de todos los documentos ---
def procesar_documentos():
    base_textos = []
    base_tablas = []

    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            path = os.path.join(root, file)
            if file.endswith(".pdf"):
                texto = leer_pdf(path)
                base_textos.append((file, texto))
            elif file.endswith(".docx"):
                texto = leer_docx(path)
                tablas = extraer_tablas_docx(path)
                base_textos.append((file, texto))
                base_tablas.extend(tablas)

    return base_textos, base_tablas

# --- Respuesta desde tablas ---
def buscar_en_tablas(pregunta, base_tablas):
    mejores = []
    for fila in base_tablas:
        texto = f"{fila['situación']} {fila['incidencias']}"
        simil = difflib.SequenceMatcher(None, pregunta.lower(), texto.lower()).ratio()
        if simil > 0.4:
            mejores.append((simil, fila))

    mejores.sort(reverse=True, key=lambda x: x[0])
    if mejores:
        mejor = mejores[0][1]
        return f"Situación: {mejor['situación']}\nIncidencias: {mejor['incidencias']}\nProcedimiento: {mejor['procedimiento']}\nReferencia Legal: {mejor['referencia legal 2022']}"
    return None

# --- Sugerencia de plantilla ---
def detectar_plantilla(pregunta):
    posibles = []
    for file in os.listdir(TEMPLATE_DIR):
        nombre = file.lower().replace("_", " ").replace("-", " ")
        simil = difflib.SequenceMatcher(None, pregunta.lower(), nombre).ratio()
        if simil > 0.4:
            posibles.append((simil, file))
    posibles.sort(reverse=True)
    return posibles[0][1] if posibles else None
