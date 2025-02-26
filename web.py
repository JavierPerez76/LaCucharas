import streamlit as st
from azure.storage.blob import BlobServiceClient

# Leer la cadena de conexión desde secrets
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = "cartasinsertadas"

# Crear cliente de servicio de Blob
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

def upload_to_blob(file):
    try:
        blob_client = container_client.get_blob_client(file.name)
        blob_client.upload_blob(file, overwrite=True)
        return True
    except Exception as e:
        st.error(f"Error al subir el archivo: {e}")
        return False

# Interfaz de Streamlit
st.title("Subir Menú")

uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"])

if uploaded_file is not None:
    st.write(f"Archivo cargado: {uploaded_file.name}")
    
    if st.button("Subir a Blob Storage"):
        success = upload_to_blob(uploaded_file)
        if success:
            st.success("Archivo subido correctamente a Azure Blob Storage.")