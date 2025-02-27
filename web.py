from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
import json
import pyodbc

# Configurar la conexión a Azure Key Vault
key_vault_url = "https://<nombre-de-tu-keyvault>.vault.azure.net/"
credential = DefaultAzureCredential()
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)

# Obtener secretos desde Key Vault
AZURE_STORAGE_CONNECTION_STRING = secret_client.get_secret("AZURE_STORAGE_CONNECTION_STRING").value
CONTAINER_NAME = secret_client.get_secret("CONTAINER_NAME").value
DOCUMENT_INTELLIGENCE_ENDPOINT = secret_client.get_secret("DOCUMENT_INTELLIGENCE_ENDPOINT").value
DOCUMENT_INTELLIGENCE_KEY = secret_client.get_secret("DOCUMENT_INTELLIGENCE_KEY").value
MODEL_ID = secret_client.get_secret("MODEL_ID").value

DB_SERVER = secret_client.get_secret("DB_SERVER").value
DB_DATABASE = secret_client.get_secret("DB_DATABASE").value
DB_USERNAME = secret_client.get_secret("DB_USERNAME").value
DB_PASSWORD = secret_client.get_secret("DB_PASSWORD").value

# Conectar con el Blob Storage
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(CONTAINER_NAME)

# Obtener la lista de blobs que terminan en .pdf.labels.json
blobs = [blob.name for blob in container_client.list_blobs() if blob.name.endswith(".pdf.labels.json")]

# Conectar con la base de datos SQL Server
conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
cursor = conn.cursor()

# Función para procesar cada blob
def procesar_json(blob_name):
    try:
        blob_client = container_client.get_blob_client(blob_name)
        blob_data = blob_client.download_blob().readall()
        menu_data = json.loads(blob_data.decode('utf-8'))

        restaurante = None
        primeros, segundos, postres, bebidas = [], [], [], []
        precio = "No especificado"

        for label in menu_data.get("labels", []):
            label_name = label.get("label", "").lower()
            if label_name == "restaurante":
                restaurante = label.get("value", [{}])[0].get("text", "Desconocido").strip()
            elif label_name == "primeros":
                primeros.extend([item["text"] for item in label.get("value", [])])
            elif label_name == "segundos":
                segundos.extend([item["text"] for item in label.get("value", [])])
            elif label_name == "postres":
                postres.extend([item["text"] for item in label.get("value", [])])
            elif label_name == "bebida":
                bebidas.extend([item["text"] for item in label.get("value", [])])
            elif label_name == "precio":
                precio = label.get("value", [{}])[0].get("text", "No especificado").strip()

        if not restaurante:
            restaurante = "Desconocido"

        # Inserción en la tabla Restaurante (evitar duplicados)
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM Restaurante WHERE Nombre = ?)
            BEGIN
                INSERT INTO Restaurante (Nombre, Ubicacion, Telefono, Email, Tipo_Restaurante) 
                VALUES (?, 'Desconocida', 'Desconocido', 'info@desconocido.com', 'General')
            END
        """, restaurante, restaurante)
        conn.commit()

        cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
        ID_Restaurante = cursor.fetchone()[0]

        # Inserción de platos (evitar duplicados)
        for nombre_plato in primeros + segundos + postres + bebidas:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM Plato WHERE ID_Restaurante = ? AND Nombre = ?)
                BEGIN
                    INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                    VALUES (?, ?, 'Desconocido', ?)
                END
            """, ID_Restaurante, nombre_plato, ID_Restaurante, nombre_plato, precio)
        conn.commit()

        # Inserción en MenuDiario y obtención del ID_Menu
        cursor.execute("""
            INSERT INTO MenuDiario (ID_Restaurante, Fecha, Precio, Tipo_Menu)
            OUTPUT INSERTED.ID_Menu
            VALUES (?, GETDATE(), ?, 'Diario')
        """, ID_Restaurante, precio)
        ID_Menu = cursor.fetchone()[0]
        conn.commit()

        # Inserción en MenuPlato (evitar duplicados)
        for nombre_plato in primeros + segundos + postres + bebidas:
            cursor.execute("""
                SELECT ID_Plato FROM Plato WHERE Nombre = ? AND ID_Restaurante = ?
            """, nombre_plato, ID_Restaurante)
            ID_Plato = cursor.fetchone()[0]

            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM MenuPlato WHERE ID_Menu = ? AND ID_Plato = ?)
                BEGIN
                    INSERT INTO MenuPlato (ID_Menu, ID_Plato, Categoria)
                    VALUES (?, ?, ?)
                END
            """, ID_Menu, ID_Plato, ID_Menu, ID_Plato, 'Desconocido')
        conn.commit()

        # Inserción en PDFMenu
        cursor.execute("""
            INSERT INTO PDFMenu (ID_Restaurante, Fecha, Archivo)
            VALUES (?, GETDATE(), ?)
        """, ID_Restaurante, blob_name)
        conn.commit()

        print(f"Se procesaron correctamente los datos de {blob_name}")
    except Exception as e:
        print(f"Error al procesar el blob {blob_name}: {e}")

# Procesar cada blob
for blob_name in blobs:
    procesar_json(blob_name)

cursor.close()
conn.close()
print("Los datos se han insertado correctamente en la base de datos.")
