import streamlit as st
import pyodbc
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import requests
import json
import time

# Función de limpieza de datos
def limpiar_datos(data, restaurante_usuario):
    cleaned_data = {
        "restaurante": restaurante_usuario.strip(),  # Usamos el restaurante que ingresa el usuario
        "primeros": [plato.strip() for plato in data.get("primeros", []) if plato.strip()],
        "segundos": [plato.strip() for plato in data.get("segundos", []) if plato.strip()],
        "postres": [plato.strip() for plato in data.get("postres", []) if plato.strip()],
        "bebidas": [plato.strip() for plato in data.get("bebidas", []) if plato.strip()],
        "precio": data.get("precio", "No especificado").strip()
    }
    
    if cleaned_data["restaurante"] == "Desconocido" or not cleaned_data["restaurante"]:
        cleaned_data["restaurante"] = "Desconocido"

    return cleaned_data

# Configuración de la conexión a Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE"]["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = st.secrets["AZURE"]["CONTAINER_NAME"]

# Configuración de Azure Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT = st.secrets["AZURE"]["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DOCUMENT_INTELLIGENCE_KEY = st.secrets["AZURE"]["DOCUMENT_INTELLIGENCE_KEY"]
MODEL_ID = st.secrets["AZURE"]["MODEL_ID"]

# Configuración de la base de datos SQL Server
DB_SERVER = st.secrets["DB"]["DB_SERVER"]
DB_DATABASE = st.secrets["DB"]["DB_DATABASE"]
DB_USERNAME = st.secrets["DB"]["DB_USERNAME"]
DB_PASSWORD = st.secrets["DB"]["DB_PASSWORD"]

def verificar_restaurante(restaurante_usuario):
    try:
        conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
        cursor = conn.cursor()

        cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante_usuario)
        result = cursor.fetchone()

        if result:
            return result[0], True
        else:
            st.error(f"El restaurante '{restaurante_usuario}' no existe en la base de datos.")
            conn.close()
            return None, False
    except pyodbc.Error as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return None, False

def upload_to_blob(file):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        blob_client = container_client.get_blob_client(file.name)
        blob_client.upload_blob(file, overwrite=True)
        return file.name
    except Exception as e:
        st.error(f"Error al subir el archivo: {e}")
        return None

def analyze_pdf(blob_name):
    storage_account_name = AZURE_STORAGE_CONNECTION_STRING.split(';')[1].split('=')[1]  
    url = f"https://{storage_account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"

    request_url = f"{DOCUMENT_INTELLIGENCE_ENDPOINT}/formrecognizer/documentModels/{MODEL_ID}:analyze?api-version=2023-07-31"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    data = {"urlSource": url}
    response = requests.post(request_url, headers=headers, json=data)

    if response.status_code == 202:
        result_url = response.headers["Operation-Location"]
        return result_url
    else:
        st.error("Error al analizar el documento.")
        return None

def get_analysis_result(result_url):
    headers = {
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }

    while True:
        response = requests.get(result_url, headers=headers)
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get("status") == "succeeded":
                return result_data
            elif result_data.get("status") == "failed":
                st.error("El análisis falló.")
                return None
            else:
                st.info("El análisis aún está en proceso. Esperando...")
                time.sleep(5)
        else:
            st.error("Error al obtener los resultados del análisis.")
            return None

def extraer_informacion(result_data):
    data = {
        "restaurante": "Desconocido",
        "primeros": [],
        "segundos": [],
        "postres": [],
        "bebidas": [],
        "precio": "No especificado"
    }

    documents = result_data.get("analyzeResult", {}).get("documents", [])

    for document in documents:
        fields = document.get("fields", {})

        if "restaurante" in fields:
            data["restaurante"] = fields["restaurante"].get("valueString", "Desconocido")
        if "primeros" in fields:
            data["primeros"] = fields["primeros"].get("valueString", "").split(", ")
        if "segundos" in fields:
            data["segundos"] = fields["segundos"].get("valueString", "").split(", ")
        if "postres" in fields:
            data["postres"] = fields["postres"].get("valueString", "").split(", ")
        if "bebida" in fields:
            data["bebidas"] = fields["bebida"].get("valueString", "").split(", ")
        if "precio" in fields:
            data["precio"] = fields["precio"].get("valueString", "No especificado")

    return data

def limpiar_y_guardar_datos(data, restaurante_nombre):
    data = limpiar_datos(data, restaurante_nombre)

    ID_Restaurante, existe = verificar_restaurante(data["restaurante"])

    if not existe:
        st.error(f"El restaurante '{data['restaurante']}' no existe en la base de datos. No se puede registrar el menú.")
        return

    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()

    # Borrar los menús anteriores
    cursor.execute("""
        DELETE FROM Plato WHERE ID_Restaurante = ?
    """, ID_Restaurante)

    # Guardar platos de 'primeros', 'segundos', 'postres', y 'bebidas' uno por uno
    categorias = ['primeros', 'segundos', 'postres', 'bebidas']
    for categoria in categorias:
        for plato in data[categoria]:
            if plato:  # Solo insertar platos no vacíos
                cursor.execute("""
                    INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                    VALUES (?, ?, ?, ?)
                """, ID_Restaurante, plato, categoria, data.get("precio", "No especificado"))

    # Insertar menú diario
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

st.title("Subir PDF y extraer información con Document Intelligence")

restaurante_nombre = st.text_input("Ingrese el nombre del restaurante")
uploaded_file = st.file_uploader("Subir archivo PDF de menú", type=["pdf"])

if uploaded_file is not None and restaurante_nombre:
    blob_name = upload_to_blob(uploaded_file)
    if blob_name:
        result_url = analyze_pdf(blob_name)
        if result_url:
            result_data = get_analysis_result(result_url)
            if result_data:
                data = extraer_informacion(result_data)
                limpiar_y_guardar_datos(data, restaurante_nombre)  # Pasamos el restaurante_nombre como argumento
