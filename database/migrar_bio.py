"""
DibujAR - Migracion: agregar columna 'bio' a la tabla USUARIO.

Esta migracion NO borra datos. Solo agrega una columna nueva
que queda vacia (NULL) para los usuarios existentes.

Ejecutar desde la carpeta DibujAR:
    python database/migrar_bio.py
"""

import sqlite3
from pathlib import Path

CARPETA_DATABASE = Path(__file__).resolve().parent
ARCHIVO_BD = CARPETA_DATABASE / "dibujar.db"


def migrar():
    if not ARCHIVO_BD.exists():
        print("ERROR: no existe la base de datos.")
        print("Ejecuta primero: python database/crear_bd.py")
        return False

    con = sqlite3.connect(ARCHIVO_BD)
    cur = con.cursor()

    columnas = [fila[1] for fila in cur.execute("PRAGMA table_info(USUARIO)")]
    if "bio" in columnas:
        print("OK: la columna bio ya existe. No hay nada que hacer.")
        con.close()
        return True

    print("Agregando columna bio a la tabla USUARIO...")
    cur.execute("ALTER TABLE USUARIO ADD COLUMN bio TEXT")
    con.commit()

    columnas = [fila[1] for fila in cur.execute("PRAGMA table_info(USUARIO)")]
    if "bio" in columnas:
        print("OK: columna bio agregada correctamente.")
        total = cur.execute("SELECT COUNT(*) FROM USUARIO").fetchone()[0]
        print(f"Usuarios conservados: {total}")
    else:
        print("ERROR: no se pudo agregar la columna.")

    con.close()
    return True


if __name__ == "__main__":
    migrar()