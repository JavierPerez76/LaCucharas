import streamlit as st
import pyodbc
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import requests
import json
import time
import re

# Configuración de la base de datos
DB_SERVER = st.secrets["DB"]["DB_SERVER"]
DB_DATABASE = st.secrets["DB"]["DB_DATABASE"]
DB_USERNAME = st.secrets["DB"]["DB_USERNAME"]
DB_PASSWORD = st.secrets["DB"]["DB_PASSWORD"]

# Configuración de Azure Blob Storage
BLOB_CONNECTION_STRING = st.secrets["AZURE"]["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = st.secrets["AZURE"]["CONTAINER_NAME"]

# Configuración de Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT = st.secrets["AZURE"]["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DOCUMENT_INTELLIGENCE_KEY = st.secrets["AZURE"]["DOCUMENT_INTELLIGENCE_KEY"]

def segmentar_texto(texto):
    segmentos = []
    palabras = texto.split()
    if not palabras:
        return []
    segmento_actual = palabras[0]
    for palabra in palabras[1:]:
        if palabra[0].isupper():
            segmentos.append(segmento_actual.strip())
            segmento_actual = palabra
        else:
            segmento_actual += f" {palabra}"
    segmentos.append(segmento_actual.strip())
    return segmentos

def limpiar_datos(data, restaurante_usuario):
    cleaned_data = {
        "restaurante": restaurante_usuario.strip(),  
        "primeros": segmentar_texto(data.get("primeros", "")),
        "segundos": segmentar_texto(data.get("segundos", "")),
        "postres": segmentar_texto(data.get("postres", "")),
        "bebidas": segmentar_texto(data.get("bebidas", "")),
        "precio": data.get("precio", "No especificado").strip()
    }
    return cleaned_data

def verificar_restaurante(restaurante_usuario):
    try:
        conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
        cursor = conn.cursor()
        cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante_usuario)
        result = cursor.fetchone()
        conn.close()
        return (result[0], True) if result else (None, False)
    except pyodbc.Error as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None, False

def limpiar_y_guardar_datos(data, restaurante_nombre):
    data = limpiar_datos(data, restaurante_nombre)
    ID_Restaurante, existe = verificar_restaurante(data["restaurante"])
    if not existe:
        st.error(f"El restaurante '{data['restaurante']}' no existe en la base de datos. No se puede registrar el menú.")
        return
    try:
        conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Plato WHERE ID_Restaurante = ?", ID_Restaurante)
        for categoria in ['primeros', 'segundos', 'postres', 'bebidas']:
            for plato in data[categoria]:
                if plato:
                    cursor.execute("""
                        INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                        VALUES (?, ?, ?, ?)
                    """, ID_Restaurante, plato, categoria, data["precio"])
        if data["precio"]:
            fecha = datetime.now().date()
            cursor.execute(""" 
                INSERT INTO MenuDiario (ID_Restaurante, Fecha, Precio, Tipo_Menu)
                VALUES (?, ?, ?, ?)
            """, ID_Restaurante, fecha, data["precio"], "Menú Diario")
        conn.commit()
        cursor.close()
        conn.close()
        st.success("Datos del restaurante y menú diario registrados correctamente.")
    except pyodbc.Error as e:
        st.error(f"Error al ejecutar la consulta SQL: {e}")

def extraer_texto_desde_document_intelligence(blob_url):
    headers = {
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
        "Content-Type": "application/json"
    }
    body = {"urlSource": blob_url}
    response = requests.post(
        f"{DOCUMENT_INTELLIGENCE_ENDPOINT}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2022-08-31",
        headers=headers, json=body
    )
    if response.status_code != 202:
        st.error("Error al analizar el documento.")
        return None
    operation_location = response.headers["Operation-Location"]
    for _ in range(10):
        time.sleep(2)
        result_response = requests.get(operation_location, headers=headers)
        result_json = result_response.json()
        if "status" in result_json and result_json["status"] == "succeeded":
            return result_json
    st.error("Error: El análisis del documento no se completó a tiempo.")
    return None

def subir_archivo_a_blob(file):
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=file.name)
    blob_client.upload_blob(file, overwrite=True)
    return blob_client.url

def analizar_menu_desde_documento(file, restaurante_usuario):
    blob_url = subir_archivo_a_blob(file)
    resultado_document = extraer_texto_desde_document_intelligence(blob_url)
    if not resultado_document:
        return
    texto_extraido = " ".join([line["content"] for page in resultado_document["analyzeResult"]["pages"] for line in page["lines"]])
    menu = {"primeros": "", "segundos": "", "postres": "", "bebidas": "", "precio": ""}
    if "primeros" in texto_extraido.lower():
        menu["primeros"] = texto_extraido.split("primeros")[-1].split("segundos")[0].strip()
    if "segundos" in texto_extraido.lower():
        menu["segundos"] = texto_extraido.split("segundos")[-1].split("postres")[0].strip()
    if "postres" in texto_extraido.lower():
        menu["postres"] = texto_extraido.split("postres")[-1].split("bebidas")[0].strip()
    if "bebidas" in texto_extraido.lower():
        menu["bebidas"] = texto_extraido.split("bebidas")[-1].strip()
    limpiar_y_guardar_datos(menu, restaurante_usuario)

st.title("Subir archivo PDF de menú")
restaurante_usuario = st.text_input("Nombre del restaurante")
uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])
if uploaded_file is not None:
    if restaurante_usuario:
        analizar_menu_desde_documento(uploaded_file, restaurante_usuario)
    else:
        st.error("Por favor, ingrese el nombre del restaurante antes de subir el archivo.")
