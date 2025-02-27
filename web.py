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

def verificar_restaurante(restaurante):
    # Conectar a la base de datos
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
    result = cursor.fetchone()
    
    if result:
        # Restaurante ya existe, devolver el ID
        return result[0], True
    else:
        # Restaurante no existe, devolver False
        return None, False

def registrar_restaurante(nombre, direccion, telefono, tipo_cocina):
    # Conectar a la base de datos
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    # Insertar el nuevo restaurante
    cursor.execute("""
        INSERT INTO Restaurante (Nombre, Direccion, Telefono, Tipo_Cocina)
        VALUES (?, ?, ?, ?)
    """, nombre, direccion, telefono, tipo_cocina)
    
    conn.commit()
    
    # Obtener el ID del restaurante recién registrado
    cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", nombre)
    ID_Restaurante = cursor.fetchone()[0]
    
    conn.close()
    return ID_Restaurante

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

# Función que limpia los datos y los inserta en la base de datos
def limpiar_y_guardar_datos(data):
    # Limpiar los datos antes de insertarlos
    data = limpiar_datos(data)

    # Verificar y registrar el restaurante
    ID_Restaurante = verificar_restaurante(data["restaurante"])[0]
    
    # Limpiar e insertar los datos como antes, pero ahora con el ID_Restaurante
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    # Insertar los platos en la tabla Plato
    for categoria, platos in data.items():
        if categoria not in ["restaurante", "precio"]:
            for plato in platos:
                # Insertar solo si el plato no está vacío
                if plato:
                    cursor.execute(""" 
                        INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                        VALUES (?, ?, ?, ?)
                    """, ID_Restaurante, plato, categoria, data.get("precio", "No especificado"))
    
    # Insertar en MenuDiario si hay precios válidos
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

# --- Interfaz de usuario ---
st.title("Subir PDF y extraer información con Document Intelligence")

# Formulario de creación de restaurante
st.subheader("Crear o seleccionar un restaurante")
restaurante_nombre = st.text_input("Nombre del restaurante")

if st.button("Crear Restaurante"):
    if restaurante_nombre:
        ID_Restaurante, existe = verificar_restaurante(restaurante_nombre)
        if existe:
            st.success(f"Restaurante '{restaurante_nombre}' ya registrado con ID: {ID_Restaurante}")
        else:
            # Si no existe, pedir más detalles
            st.info(f"Restaurante '{restaurante_nombre}' no encontrado. Por favor, ingrese los detalles.")
            
            direccion = st.text_input("Dirección del restaurante")
            telefono = st.text_input("Teléfono del restaurante")
            tipo_cocina = st.text_input("Tipo de cocina del restaurante")
            
            if st.button("Registrar Restaurante"):
                if direccion and telefono and tipo_cocina:
                    ID_Restaurante = registrar_restaurante(restaurante_nombre, direccion, telefono, tipo_cocina)
                    st.success(f"Restaurante '{restaurante_nombre}' registrado exitosamente con ID: {ID_Restaurante}")
                else:
                    st.error("Por favor, complete todos los campos antes de registrar el restaurante.")
    else:
        st.error("Por favor, ingrese un nombre para el restaurante.")

# Subir y analizar el archivo PDF
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
