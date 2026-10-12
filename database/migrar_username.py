"""
DibujAR - Migracion: agregar columna 'username' a la tabla USUARIO.

Esta migracion NO borra datos. Solo agrega una columna nueva y
genera un username automatico para los usuarios que ya existen.

Ejecutar desde la carpeta DibujAR:
    python database/migrar_username.py
"""

import re
import sqlite3
import unicodedata
from pathlib import Path

CARPETA_DATABASE = Path(__file__).resolve().parent
ARCHIVO_BD = CARPETA_DATABASE / "dibujar.db"


def normalizar(texto):
    """Quita acentos, pasa a minusculas, deja solo letras/numeros/_/."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9_.]", "", texto)
    return texto


def generar_username_unico(con, nombre, apellido, correo):
    """Genera un username unico basado en nombre+apellido o correo."""
    base = normalizar(f"{nombre}_{apellido}")
    if len(base) < 3:
        base = normalizar(correo.split("@")[0])
    if len(base) < 3:
        base = "usuario"

    base = base[:20]

    # Verificar si esta libre
    existe = con.execute("SELECT 1 FROM USUARIO WHERE username = ?", (base,)).fetchone()
    if not existe:
        return base

    # Probar con numeros
    for n in range(1, 10000):
        candidato = f"{base}_{n}"
        if len(candidato) > 30:
            candidato = candidato[:30]
        existe = con.execute("SELECT 1 FROM USUARIO WHERE username = ?", (candidato,)).fetchone()
        if not existe:
            return candidato

    return f"usuario_{con.execute('SELECT COUNT(*) FROM USUARIO').fetchone()[0] + 1}"


def migrar():
    if not ARCHIVO_BD.exists():
        print("ERROR: no existe la base de datos.")
        print("Ejecuta primero: python database/crear_bd.py")
        return False

    con = sqlite3.connect(ARCHIVO_BD)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Ver si la columna ya existe
    columnas = [fila[1] for fila in cur.execute("PRAGMA table_info(USUARIO)")]
    if "username" in columnas:
        print("OK: la columna username ya existe.")
        con.close()
        return True

    print("Agregando columna username a la tabla USUARIO...")
    cur.execute("ALTER TABLE USUARIO ADD COLUMN username TEXT")
    con.commit()

    # Generar username para usuarios existentes
    print("Generando usernames para usuarios existentes...")
    usuarios = cur.execute("SELECT id_usuario, nombre, apellido, correo FROM USUARIO").fetchall()
    for u in usuarios:
        username = generar_username_unico(con, u["nombre"], u["apellido"], u["correo"])
        cur.execute("UPDATE USUARIO SET username = ? WHERE id_usuario = ?", (username, u["id_usuario"]))
        print(f"  id={u['id_usuario']}: {u['nombre']} {u['apellido']} -> @{username}")
    con.commit()

    # Crear indice unico
    print("Creando indice unico en username...")
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usuario_username ON USUARIO(username)")
        con.commit()
        print("OK: indice unico creado.")
    except sqlite3.IntegrityError as e:
        print(f"WARNING: no se pudo crear el indice unico: {e}")

    print("")
    print("OK: migracion completada.")
    total = cur.execute("SELECT COUNT(*) FROM USUARIO").fetchone()[0]
    print(f"Usuarios actualizados: {total}")
    con.close()
    return True


if __name__ == "__main__":
    migrar()