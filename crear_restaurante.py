import streamlit as st
import pyodbc

# Configuración de la base de datos SQL Server
DB_SERVER = st.secrets["DB"]["DB_SERVER"]
DB_DATABASE = st.secrets["DB"]["DB_DATABASE"]
DB_USERNAME = st.secrets["DB"]["DB_USERNAME"]
DB_PASSWORD = st.secrets["DB"]["DB_PASSWORD"]

def crear_restaurante(nombre, direccion, telefono, tipo):
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Restaurante (Nombre, Direccion, Telefono, Tipo)
        VALUES (?, ?, ?, ?)
    """, nombre, direccion, telefono, tipo)
    
    conn.commit()
    cursor.close()
    conn.close()

    st.success(f"Restaurante {nombre} creado correctamente.")

st.title("Crear Restaurante")

nombre = st.text_input("Nombre del restaurante")
direccion = st.text_input("Dirección")
telefono = st.text_input("Teléfono")
tipo = st.selectbox("Tipo de restaurante", ["Fast Food", "Casual Dining", "Fine Dining", "Buffet"])

if st.button("Crear Restaurante"):
    if nombre and direccion and telefono and tipo:
        crear_restaurante(nombre, direccion, telefono, tipo)
    else:
        st.error("Por favor, completa todos los campos.")
