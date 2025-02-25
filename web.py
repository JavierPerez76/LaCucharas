import streamlit as st
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from sqlalchemy import create_engine
import json

# Función para autenticarte en Azure Document Intelligence
def authenticate_azure():
    endpoint = st.secrets["azure"]["form_recognizer_endpoint"]
    api_key = st.secrets["azure"]["form_recognizer_api_key"]
    client = DocumentAnalysisClient(
        endpoint=endpoint, 
        credential=AzureKeyCredential(api_key)
    )
    return client

# Función para analizar el documento con Azure Form Recognizer
def analyze_document(client, file):
    poller = client.begin_analyze_document("prebuilt-document", file)
    result = poller.result()
    return result

# Función para almacenar los datos en la base de datos
def store_in_database(data_json):
    # Conexión a la base de datos (Asegúrate de tener las credenciales en 'secrets.toml')
    db_user = st.secrets["database"]["user"]
    db_password = st.secrets["database"]["password"]
    db_host = st.secrets["database"]["host"]
    db_name = st.secrets["database"]["database_name"]
    
    DATABASE_URI = f'mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}'
    engine = create_engine(DATABASE_URI)
    
    # Parsear el JSON devuelto por Form Recognizer y almacenar en la base de datos
    with engine.connect() as conn:
        # Procesa el JSON aquí según el formato del documento que estés utilizando
        for field in data_json['fields']:
            # Ejemplo de almacenamiento en la base de datos, modifica según tu esquema
            campo = field['field_name']
            valor = field['value']
            query = f"INSERT INTO tu_tabla (campo1, campo2) VALUES ('{campo}', '{valor}')"
            conn.execute(query)

    st.success("Datos almacenados correctamente en la base de datos")

# Interfaz de Streamlit
st.title("Sube tu archivo para procesarlo")
pdf_file = st.file_uploader("Sube el archivo PDF", type="pdf")

if pdf_file:
    st.write("Procesando el archivo...")

    # Autenticarse en Azure
    client = authenticate_azure()

    # Analizar el documento
    result = analyze_document(client, pdf_file)

    # Convertir el resultado en un formato JSON
    result_json = json.dumps(result.to_dict(), indent=4)

    # Mostrar un vistazo del JSON
    st.json(result_json)

    # Almacenar el JSON en la base de datos
    if st.button("Almacenar en base de datos"):
        store_in_database(result.to_dict())
