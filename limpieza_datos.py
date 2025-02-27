import streamlit as st
import pyodbc
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import requests
import json
import time

# Configuración de la base de datos (ajustar con tus credenciales)
DB_SERVER = "TU_SERVIDOR"
DB_DATABASE = "TU_BASE_DE_DATOS"
DB_USERNAME = "TU_USUARIO"
DB_PASSWORD = "TU_CONTRASEÑA"

# Configuración de Azure Blob Storage
BLOB_CONNECTION_STRING = "TU_CONEXION_AZURE_STORAGE"
CONTAINER_NAME = "TU_CONTENEDOR"

# Configuración de Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT = "TU_ENDPOINT"
DOCUMENT_INTELLIGENCE_KEY = "TU_CLAVE"

def limpiar_datos(data, restaurante_usuario):
    cleaned_data = {
        "restaurante": restaurante_usuario.strip(),  # Usamos el restaurante que ingresa el usuario
        "primeros": [plato.strip() for plato in data.get("primeros", "").split(",") if plato.strip()],
        "segundos": [plato.strip() for plato in data.get("segundos", "").split(",") if plato.strip()],
        "postres": [plato.strip() for plato in data.get("postres", "").split(",") if plato.strip()],
        "bebidas": [plato.strip() for plato in data.get("bebidas", "").split(",") if plato.strip()],
        "precio": data.get("precio", "No especificado").strip()
    }
    
    if not cleaned_data["restaurante"]:
        cleaned_data["restaurante"] = "Desconocido"

    return cleaned_data

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

def limpiar_y_guardar_datos(data, restaurante_nombre):
    data = limpiar_datos(data, restaurante_nombre)

    ID_Restaurante, existe = verificar_restaurante(data["restaurante"])

    if not existe:
        st.error(f"El restaurante '{data['restaurante']}' no existe en la base de datos. No se puede registrar el menú.")
        return

    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()

    # Borrar los menús anteriores del restaurante
    cursor.execute("DELETE FROM Plato WHERE ID_Restaurante = ?", ID_Restaurante)

    # Insertar cada plato correctamente
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
    
    # Esperar el procesamiento
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

    # Procesamiento simple del texto (se debe adaptar según el formato del menú)
    menu = {
        "primeros": "",
        "segundos": "",
        "postres": "",
        "bebidas": "",
        "precio": ""
    }

    if "primeros" in texto_extraido.lower():
        menu["primeros"] = texto_extraido.split("primeros")[-1].split("segundos")[0].strip()
    if "segundos" in texto_extraido.lower():
        menu["segundos"] = texto_extraido.split("segundos")[-1].split("postres")[0].strip()
    if "postres" in texto_extraido.lower():
        menu["postres"] = texto_extraido.split("postres")[-1].split("bebidas")[0].strip()
    if "bebidas" in texto_extraido.lower():
        menu["bebidas"] = texto_extraido.split("bebidas")[-1].split("11.90")[0].strip()
    if "11.90" in texto_extraido:
        menu["precio"] = "11.90"

    limpiar_y_guardar_datos(menu, restaurante_usuario)

# INTERFAZ DE USUARIO EN STREAMLIT
st.title("Subir archivo PDF de menú")

restaurante_usuario = st.text_input("Nombre del restaurante")

uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    if restaurante_usuario:
        analizar_menu_desde_documento(uploaded_file, restaurante_usuario)
    else:
        st.error("Por favor, ingrese el nombre del restaurante antes de subir el archivo.")
