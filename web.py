import streamlit as st
from azure.storage.blob import BlobServiceClient
import requests
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
    # Extraer el nombre de la cuenta desde la cadena de conexión
    storage_account_name = AZURE_STORAGE_CONNECTION_STRING.split(';')[1].split('=')[1]  # Obtén el AccountName
    url = f"https://{storage_account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    
    # Continuar con la lógica del análisis de PDF
    request_url = f"{DOCUMENT_INTELLIGENCE_ENDPOINT}/formrecognizer/documentModels/{MODEL_ID}:analyze?api-version=2023-07-31"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    data = {"urlSource": url}
    response = requests.post(request_url, headers=headers, json=data)
    
    if response.status_code == 202:
        # Si la solicitud fue exitosa, obtenemos la URL de operación
        result_url = response.headers["Operation-Location"]
        return result_url
    else:
        st.error(f"Error al analizar el documento: {response.text}")
        return None

def get_analysis_result(result_url):
    # Hacer una solicitud GET a la URL de la operación para obtener los resultados finales
    headers = {
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    
    max_retries = 10
    attempts = 0

    while attempts < max_retries:
        response = requests.get(result_url, headers=headers)
        
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get("status") == "succeeded":
                return format_result(result_data)
            elif result_data.get("status") == "failed":
                st.error("El análisis falló.")
                return None
            else:
                time.sleep(5)  # Esperamos 5 segundos antes de volver a verificar
                attempts += 1
        else:
            st.error(f"Error al obtener los resultados del análisis: {response.text}")
            return None

    st.error("El análisis no se completó dentro del tiempo esperado.")
    return None

def format_result(result_data):
    # Crear un diccionario para almacenar los resultados extraídos
    menu_data = {
        "restaurante": "Desconocido",
        "primeros": [],
        "segundos": [],
        "postres": [],
        "bebidas": [],
        "precio": "No especificado"
    }
    
    # Extraer la información relevante del análisis
    pages = result_data.get("analyzeResult", {}).get("pages", [])
    
    for page in pages:
        for field in page.get("fields", {}).values():
            label = field.get("label", "").lower()
            text = field.get("text", "")
            
            if "restaurante" in label:
                menu_data["restaurante"] = text
            elif "primeros" in label:
                menu_data["primeros"].append(text)
            elif "segundos" in label:
                menu_data["segundos"].append(text)
            elif "postres" in label:
                menu_data["postres"].append(text)
            elif "bebidas" in label:
                menu_data["bebidas"].append(text)
            elif "precio" in label:
                menu_data["precio"] = text

    return menu_data

def insert_into_db(menu_data):
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    restaurante = menu_data.get("restaurante", "Desconocido")
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
        if categoria not in ["restaurante", "precio"]:
            for plato in platos:
                cursor.execute(""" 
                    INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                    VALUES (?, ?, ?, ?)
                """, ID_Restaurante, plato, categoria, menu_data.get("precio", "No especificado"))
    conn.commit()
    cursor.close()
    conn.close()

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
                    # Mostrar los resultados específicos: restaurante, primeros, segundos, postres, bebidas y precio
                    st.write("Información extraída:")
                    st.write(f"Restaurante: {result_data['restaurante']}")
                    st.write(f"Primeros: {', '.join(result_data['primeros'])}")
                    st.write(f"Segundos: {', '.join(result_data['segundos'])}")
                    st.write(f"Postres: {', '.join(result_data['postres'])}")
                    st.write(f"Bebidas: {', '.join(result_data['bebidas'])}")
                    st.write(f"Precio: {result_data['precio']}")
                    st.success("Análisis completado.")
