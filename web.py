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
    url = f"{DOCUMENT_INTELLIGENCE_ENDPOINT}/formrecognizer/documentModels/{MODEL_ID}:analyze?api-version=2023-07-31"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    data = {"urlSource": f"https://{st.secrets['AZURE_STORAGE_ACCOUNT_NAME']}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"}
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 202:
        result_url = response.headers["Operation-Location"]
        return result_url
    else:
        st.error("Error al analizar el documento.")
        return None

def get_analysis_result(result_url):
    # Esperamos 1 segundo antes de hacer la solicitud, para que la operación se procese
    time.sleep(1)
    
    # Realizamos la solicitud para obtener el resultado del análisis
    response = requests.get(result_url, headers={"Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY})
    
    if response.status_code == 200:
        return response.json()  # Devuelve el resultado como un diccionario
    else:
        st.error("Error al obtener el resultado del análisis.")
        return None

st.title("Subir PDF y extraer información con Document Intelligence")

uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    st.write(f"Archivo cargado: {uploaded_file.name}")
    
    if st.button("Subir y analizar PDF"):
        blob_name = upload_to_blob(uploaded_file)
        if blob_name:
            result_url = analyze_pdf(blob_name)
            if result_url:
                st.success("Análisis en proceso. Verifica los resultados más tarde.")
                
                # Obtener el resultado del análisis
                result_data = get_analysis_result(result_url)
                
                if result_data:
                    st.write("Datos extraídos del PDF:")
                    st.json(result_data)  # Muestra el JSON con los datos extraídos
