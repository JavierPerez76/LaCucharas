import streamlit as st
import requests
import json
import time

# Configuración de Azure Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT = st.secrets["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DOCUMENT_INTELLIGENCE_KEY = st.secrets["DOCUMENT_INTELLIGENCE_KEY"]
MODEL_ID = st.secrets["MODEL_ID"]
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = st.secrets["CONTAINER_NAME"]

def analyze_pdf(blob_name):
    # Obtener el nombre de la cuenta de almacenamiento desde la cadena de conexión
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
        st.error("Error al analizar el documento.")
        return None

def get_analysis_result(result_url):
    # Hacer una solicitud GET a la URL de la operación para obtener los resultados finales
    headers = {
        "Ocp-Apim-Subscription-Key": DOCUMENT_INTELLIGENCE_KEY,
    }
    
    while True:
        response = requests.get(result_url, headers=headers)
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get("status") == "succeeded":
                # Imprimir el JSON completo del resultado del análisis
                st.write("JSON del resultado del análisis:")
                st.json(result_data)  # Muestra el JSON completo
                return result_data
            elif result_data.get("status") == "failed":
                st.error("El análisis falló.")
                return None
            else:
                st.info("El análisis aún está en proceso. Esperando...")
                time.sleep(5)  # Esperamos 5 segundos antes de volver a verificar
        else:
            st.error("Error al obtener los resultados del análisis.")
            return None

def format_result(result_data):
    # Aquí vamos a extraer el contenido de restaurante, primeros, segundos, etc.
    menu_data = {
        "restaurante": "Desconocido",
        "primeros": [],
        "segundos": [],
        "postres": [],
        "bebidas": [],
        "precio": "No especificado"
    }

    # Extraemos los documentos
    documents = result_data.get("analyzeResult", {}).get("documents", [])
    
    for document in documents:
        # Recorremos los campos dentro de cada documento
        fields = document.get("fields", {})
        
        for field_name, field_data in fields.items():
            # Aquí extraemos el valor del campo
            field_value = field_data.get("valueString", "")
            
            # Lógica de clasificación por etiquetas
            if "restaurante" in field_name.lower():
                menu_data["restaurante"] = field_value
            elif "primeros" in field_name.lower():
                menu_data["primeros"].append(field_value)
            elif "segundos" in field_name.lower():
                menu_data["segundos"].append(field_value)
            elif "postres" in field_name.lower():
                menu_data["postres"].append(field_value)
            elif "bebidas" in field_name.lower():
                menu_data["bebidas"].append(field_value)
            elif "precio" in field_name.lower():
                menu_data["precio"] = field_value

    return menu_data

st.title("Subir PDF y extraer información con Document Intelligence")

uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    st.write(f"Archivo cargado: {uploaded_file.name}")
    
    if st.button("Subir y analizar PDF"):
        # Subir el archivo y analizarlo usando Document Intelligence
        result_url = analyze_pdf(uploaded_file.name)
        if result_url:
            # Obtener los resultados del análisis
            result_data = get_analysis_result(result_url)
            if result_data:
                # Formatear el resultado para extraer los datos
                menu_data = format_result(result_data)
                
                # Mostrar los resultados extraídos
                st.write("Información extraída:")
                st.write(f"Restaurante: {menu_data['restaurante']}")
                st.write(f"Primeros: {', '.join(menu_data['primeros'])}")
                st.write(f"Segundos: {', '.join(menu_data['segundos'])}")
                st.write(f"Postres: {', '.join(menu_data['postres'])}")
                st.write(f"Bebidas: {', '.join(menu_data['bebidas'])}")
                st.write(f"Precio: {menu_data['precio']}")
                st.success("Análisis completado.")
