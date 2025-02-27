import streamlit as st
import pyodbc
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import requests
import json
import time
from limpieza_datos import limpiar_y_guardar_datos  # Importamos el script de limpieza de datos

# Configuración de la conexión a Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = st.secrets["CONTAINER_NAME"]

# Configuración de Azure Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT = st.secrets["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DOCUMENT_INTELLIGENCE_KEY = st.secrets["DOCUMENT_INTELLIGENCE_KEY"]
MODEL_ID = st.secrets["MODEL_ID"]

# Configuración de la base de datos SQL Server
DB_SERVER = st.secrets["DB_SERVER"]
DB_DATABASE = st.secrets["DB_DATABASE"]
DB_USERNAME = st.secrets["DB_USERNAME"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]

# Función de autenticación
def login(username, password):
    correct_username = st.secrets["USERNAME"]
    correct_password = st.secrets["PASSWORD"]
    return username == correct_username and password == correct_password

# Función para verificar y registrar un restaurante
def verificar_restaurante(restaurante):
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO Restaurante (Nombre) VALUES (?)", restaurante)
        conn.commit()
        
        cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
        ID_Restaurante = cursor.fetchone()[0]
        
        conn.close()
        return ID_Restaurante

# Función para subir el archivo a Azure Blob Storage
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

# Función para analizar el PDF usando Document Intelligence
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

# Función para obtener los resultados del análisis
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

# Función para extraer la información relevante del análisis
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

# Función que limpia los datos y los inserta en la base de datos
def limpiar_y_guardar_datos(data):
    # Verificar y registrar el restaurante
    ID_Restaurante = verificar_restaurante(data["restaurante"])
    
    # Limpiar e insertar los datos como antes, pero ahora con el ID_Restaurante
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    # Insertar los platos en la tabla Plato
    for categoria, platos in data.items():
        if categoria not in ["restaurante", "precio"]:
            for plato in platos:
                cursor.execute(""" 
                    INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                    VALUES (?, ?, ?, ?)
                """, ID_Restaurante, plato, categoria, data.get("precio", "No especificado"))
    
    # Insertar en MenuDiario
    fecha = datetime.now().date()
    cursor.execute(""" 
        INSERT INTO MenuDiario (ID_Restaurante, Fecha, Precio, Tipo_Menu)
        VALUES (?, ?, ?, ?)
    """, ID_Restaurante, fecha, data["precio"], "Menú Diario")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    st.success("Datos del restaurante y menú diario registrados correctamente.")

# Página de inicio de sesión
st.title("Iniciar sesión")

username = st.text_input("Usuario", "")
password = st.text_input("Contraseña", "", type="password")

if st.button("Iniciar sesión"):
    if login(username, password):
        st.success("¡Has iniciado sesión correctamente!")
        
        # Después de iniciar sesión, seleccionar o crear el restaurante
        restaurante = st.text_input("Nombre del restaurante")
        if st.button("Verificar o crear restaurante"):
            if restaurante:
                ID_Restaurante = verificar_restaurante(restaurante)
                st.write(f"ID del restaurante: {ID_Restaurante}")
            else:
                st.error("Por favor, ingresa un nombre para el restaurante.")
    else:
        st.error("Usuario o contraseña incorrectos.")

# Subir PDF y extraer información con Document Intelligence
st.title("Subir PDF y extraer información con Document Intelligence")

uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    st.write(f"Archivo cargado: {uploaded_file.name}")
    
    if st.button("Subir y analizar PDF"):
        # Subir el archivo al blob
        blob_name = upload_to_blob(uploaded_file)
        if blob_name:
            # Analizar el archivo usando Document Intelligence
            result_url = analyze_pdf(blob_name)
            if result_url:
                # Obtener los resultados del análisis
                result_data = get_analysis_result(result_url)
                if result_data:
                    # Extraer la información relevante del resultado
                    extracted_data = extraer_informacion(result_data)
                    st.write("Información extraída:")
                    st.write(extracted_data)
                    # Llamar a la función para limpiar y guardar los datos
                    limpiar_y_guardar_datos(extracted_data)
                    st.success("Análisis completado.")
