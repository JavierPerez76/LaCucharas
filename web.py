import streamlit as st
from azure.storage.blob import BlobServiceClient
import requests
import json
import pyodbc
import time

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

# Función para subir el archivo al Blob Storage
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

# Función para analizar el PDF utilizando Document Intelligence
def analyze_pdf(blob_name):
    # Construir la URL del archivo en Azure Blob Storage
    blob_url = f"https://{st.secrets['AZURE_STORAGE_ACCOUNT_NAME']}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    
    # Configurar la solicitud a Azure Document Intelligence
    url = f"{DOCUMENT_INTELLIGENCE_ENDPOINT}/formrecognizer/documentModels/{MODEL_ID}:analyze?api-version=2023-07-31"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    data = {"urlSource": blob_url}
    
    # Realizar la solicitud POST para iniciar el análisis
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 202:
        # Esperar el resultado del análisis
        result_url = response.headers["Operation-Location"]
        return result_url
    else:
        st.error("Error al analizar el documento.")
        return None

# Función para consultar el resultado del análisis de Document Intelligence
def get_analysis_result(result_url):
    headers = {
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    
    # Esperar un poco antes de hacer la consulta, por ejemplo 10 segundos
    time.sleep(10)
    
    response = requests.get(result_url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Error al obtener el resultado del análisis.")
        return None

# Función para insertar datos en la base de datos SQL Server
def insert_into_db(menu_data):
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    restaurante = menu_data.get("restaurant", "Desconocido")
    cursor.execute(""" 
        IF NOT EXISTS (SELECT 1 FROM Restaurante WHERE Nombre = ?)
        BEGIN
            INSERT INTO Restaurante (Nombre) VALUES (?)
        END
    """, restaurante, restaurante)
    conn.commit()
    cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
    ID_Restaurante = cursor.fetchone()[0]
    
    for categoria, platos in menu_data.items():
        if categoria not in ["restaurant", "precio"]:
            for plato in platos:
                cursor.execute("""
                    INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                    VALUES (?, ?, ?, ?)
                """, ID_Restaurante, plato, categoria, menu_data.get("precio", "No especificado"))
    conn.commit()
    cursor.close()
    conn.close()

# Interfaz de usuario en Streamlit
st.title("Subir PDF y extraer información con Document Intelligence")

uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    st.write(f"Archivo cargado: {uploaded_file.name}")
    
    if st.button("Subir y analizar PDF"):
        # Subir el archivo a Blob Storage
        blob_name = upload_to_blob(uploaded_file)
        if blob_name:
            # Iniciar el análisis en Document Intelligence
            result_url = analyze_pdf(blob_name)
            if result_url:
                st.success("Análisis en proceso. Verifica los resultados más tarde.")
                
                # Obtener los resultados del análisis
                analysis_result = get_analysis_result(result_url)
                
                if analysis_result:
                    # Mostrar el resultado del análisis en la interfaz
                    st.json(analysis_result)
                    
                    # Suponiendo que el análisis extrae datos de menú, procesarlos e insertarlos en la base de datos
                    menu_data = {
                        "restaurant": "Restaurante Ejemplo",
                        "Primero": ["Plato 1", "Plato 2"],
                        "Segundo": ["Plato A", "Plato B"],
                        "postres": ["Postre 1"],
                        "precio": "10.99"
                    }
                    
                    insert_into_db(menu_data)
                    st.success("Datos insertados correctamente en la base de datos.")
