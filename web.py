import streamlit as st
import requests
import json
import time

# Configuración de Azure Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT = st.secrets["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DOCUMENT_INTELLIGENCE_KEY = st.secrets["DOCUMENT_INTELLIGENCE_KEY"]
MODEL_ID = st.secrets["MODEL_ID"]

def analyze_pdf(blob_name):
    # Aquí colocarías la lógica para obtener la URL del archivo en Azure Blob Storage
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

    # Extraemos las páginas del resultado
    pages = result_data.get("analyzeResult", {}).get("pages", [])
    
    for page in pages:
        for field in page.get("fields", {}).values():
            label = field.get("label", "").lower()
            text = field.get("text", "")
            
            # Aquí estamos imprimiendo el JSON del resultado para verificar
            st.write(f"Etiqueta: {label}, Texto: {text}")

            # Lógica de clasificación por etiquetas
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
