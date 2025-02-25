import streamlit as st
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import json
import pandas as pd
from sqlalchemy import create_engine

# Configuración de Azure Form Recognizer
endpoint = "TU_ENDPOINT"  # Reemplaza con tu endpoint de Azure Form Recognizer
api_key = "TU_API_KEY"    # Reemplaza con tu clave de API de Azure
model_id = "TU_MODEL_ID"  # Reemplaza con tu ID de modelo entrenado

# Crear un cliente de Azure Form Recognizer
credential = AzureKeyCredential(api_key)
client = DocumentAnalysisClient(endpoint=endpoint, credential=credential)

# Conexión a la base de datos
DATABASE_URI = 'mysql+pymysql://usuario:contraseña@localhost/nombre_base_datos'
engine = create_engine(DATABASE_URI)

# Función para procesar el archivo cargado
def procesar_documento(uploaded_file):
    # Leer el archivo en bytes
    document = uploaded_file.read()

    # Enviar documento al servicio de Document Intelligence (Form Recognizer)
    poller = client.begin_analyze_document(model_id=model_id, document=document)
    result = poller.result()

    # Parsear el resultado en JSON
    resultado_json = result.to_dict()
    return resultado_json

# Función para almacenar los datos en la base de datos
def almacenar_en_base_de_datos(data):
    try:
        # Aquí puedes realizar las inserciones necesarias en la base de datos
        # Crear un DataFrame para los datos del restaurante (Ejemplo)
        restaurantes = []
        platos = []
        for item in data['restaurantes']:  # Asegúrate de adaptar según la estructura del JSON
            restaurantes.append((item['nombre'], item['ubicacion'], item['telefono'], item['email'], item['tipo_restaurante']))
            for plato in item['platos']:
                platos.append((plato['nombre'], plato['tipo'], plato['precio'], item['id']))

        # Insertar restaurantes en la base de datos
        df_restaurantes = pd.DataFrame(restaurantes, columns=['Nombre', 'Ubicacion', 'Telefono', 'Email', 'Tipo_Restaurante'])
        df_restaurantes.to_sql('Restaurante', con=engine, if_exists='append', index=False)

        # Insertar platos en la base de datos
        df_platos = pd.DataFrame(platos, columns=['Nombre', 'Tipo', 'Precio', 'ID_Restaurante'])
        df_platos.to_sql('Plato', con=engine, if_exists='append', index=False)

        st.success("Datos almacenados correctamente en la base de datos.")
    except Exception as e:
        st.error(f"Error al almacenar los datos: {e}")

# Interfaz de usuario de Streamlit
st.title("Sube tu archivo para procesarlo")
uploaded_file = st.file_uploader("Elige un archivo", type=["pdf", "jpg", "png"])

if uploaded_file:
    st.write("Procesando archivo...")

    # Procesar el documento
    resultado_json = procesar_documento(uploaded_file)
    
    # Mostrar el resultado
    st.write("Resultado procesado:")
    st.json(resultado_json)

    # Botón para almacenar los datos en la base de datos
    if st.button("Guardar en base de datos"):
        almacenar_en_base_de_datos(resultado_json)
