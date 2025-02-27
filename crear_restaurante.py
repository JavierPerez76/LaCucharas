import streamlit as st
import pyodbc

# Obtener las credenciales desde Streamlit secrets
DB_SERVER = st.secrets["database"]["DB_SERVER"]
DB_DATABASE = st.secrets["database"]["DB_DATABASE"]
DB_USERNAME = st.secrets["database"]["DB_USERNAME"]
DB_PASSWORD = st.secrets["database"]["DB_PASSWORD"]

def verificar_restaurante(restaurante):
    # Conectar a la base de datos
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
    result = cursor.fetchone()
    
    if result:
        # Restaurante ya existe, devolver el ID
        conn.close()
        return result[0], True
    else:
        # Restaurante no existe, insertar y devolver el nuevo ID
        cursor.execute("INSERT INTO Restaurante (Nombre) VALUES (?)", restaurante)
        conn.commit()
        
        cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
        ID_Restaurante = cursor.fetchone()[0]
        
        conn.close()
        return ID_Restaurante, False

def crear_restaurante():
    st.title("Crear un nuevo Restaurante")
    
    restaurante_nombre = st.text_input("Nombre del Restaurante")
    
    if st.button("Verificar Restaurante"):
        if restaurante_nombre:
            ID_Restaurante, existe = verificar_restaurante(restaurante_nombre)
            if existe:
                st.success(f"El restaurante '{restaurante_nombre}' ya existe con ID: {ID_Restaurante}.")
            else:
                st.info(f"Restaurante '{restaurante_nombre}' creado con ID: {ID_Restaurante}.")
                
                # Aquí puedes continuar pidiendo más datos como dirección, contacto, etc.
                direccion = st.text_input("Dirección")
                telefono = st.text_input("Teléfono")
                categoria = st.selectbox("Categoría", ["Italiana", "Mexicana", "China", "Española", "Otros"])
                
                if st.button("Registrar Restaurante"):
                    if direccion and telefono:
                        # Registrar en la base de datos
                        conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
                        cursor = conn.cursor()
                        
                        cursor.execute("""
                            UPDATE Restaurante
                            SET Direccion = ?, Telefono = ?, Categoria = ?
                            WHERE ID_Restaurante = ?
                        """, direccion, telefono, categoria, ID_Restaurante)
                        
                        conn.commit()
                        conn.close()
                        
                        st.success("Restaurante registrado exitosamente con la información adicional.")
                    else:
                        st.warning("Por favor, ingrese todos los datos necesarios (dirección y teléfono).")
        else:
            st.warning("Por favor, ingrese el nombre del restaurante.")
    
if __name__ == "__main__":
    crear_restaurante()
