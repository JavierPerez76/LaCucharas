import pyodbc
from datetime import datetime

# Configuración de la base de datos SQL Server
DB_SERVER = "tu_db_server"
DB_DATABASE = "tu_db_database"
DB_USERNAME = "tu_db_username"
DB_PASSWORD = "tu_db_password"

def limpiar_y_guardar_datos(data):
    # Conectar a la base de datos
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};PORT=1433;DATABASE={DB_DATABASE};UID={DB_USERNAME};PWD={DB_PASSWORD}')
    cursor = conn.cursor()
    
    # Insertar los datos en la tabla Restaurante
    restaurante = data["restaurante"]
    cursor.execute("""INSERT INTO Restaurante (Nombre) VALUES (?)""", restaurante)
    conn.commit()
    
    cursor.execute("SELECT ID_Restaurante FROM Restaurante WHERE Nombre = ?", restaurante)
    ID_Restaurante = cursor.fetchone()[0]
    
    # Insertar los platos en la tabla Plato
    for categoria, platos in data.items():
        if categoria not in ["restaurante", "precio"]:
            for plato in platos:
                cursor.execute(""" 
                    INSERT INTO Plato (ID_Restaurante, Nombre, Tipo, Precio)
                    VALUES (?, ?, ?, ?)
                """, ID_Restaurante, plato, categoria, data.get("precio", "No especificado"))
    
    conn.commit()
    
    # Si el menú es un menú diario, insertamos en MenuDiario
    fecha = datetime.now().date()
    cursor.execute("""
        INSERT INTO MenuDiario (ID_Restaurante, Fecha, Precio, Tipo_Menu)
        VALUES (?, ?, ?, ?)
    """, ID_Restaurante, fecha, data["precio"], "Menú Diario")
    
    conn.commit()
    
    cursor.close()
    conn.close()
