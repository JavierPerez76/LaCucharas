import streamlit as st
import pyodbc

# Configuración de la base de datos
DB_SERVER = "menuserver.database.windows.net"
DB_DATABASE = "menudb"
DB_USERNAME = "usuario"
DB_PASSWORD = "Javi123+"

def crear_restaurante():
    st.title("Crear Restaurante")

    # Formulario para ingresar los datos del restaurante
    restaurante_nombre = st.text_input("Nombre del restaurante")
    restaurante_direccion = st.text_input("Dirección")
    restaurante_telefono = st.text_input("Teléfono")
    restaurante_email = st.text_input("Email")
    restaurante_categorias = st.text_input("Categorías (separadas por comas)")

    # Botón para guardar los datos del restaurante
    if st.button("Crear Restaurante"):
        if restaurante_nombre and restaurante_direccion and restaurante_telefono and restaurante_email:
            try:
                # Conectar a la base de datos
                conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
                cursor = conn.cursor()

                # Insertar el restaurante en la base de datos
                cursor.execute("""
                    INSERT INTO Restaurante (Nombre, Direccion, Telefono, Email, Categorias)
                    VALUES (?, ?, ?, ?, ?)
                """, restaurante_nombre, restaurante_direccion, restaurante_telefono, restaurante_email, restaurante_categorias)

                conn.commit()
                cursor.close()
                conn.close()

                st.success("Restaurante creado correctamente.")
            except Exception as e:
                st.error(f"Error al crear el restaurante: {e}")
        else:
            st.error("Por favor, complete todos los campos.")
