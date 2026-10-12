"""
DibujAR - Script para crear la base de datos SQLite.

Que hace:
1. Crea la carpeta uploads/ (y sus subcarpetas).
2. Crea el archivo database/dibujar.db con las 14 tablas (usa schema.sql).
3. Inserta los datos iniciales de los catalogos:
   frecuencias de dibujo, estilos y tematicas.

Como ejecutarlo (desde la carpeta principal DibujAR):
    python database/crear_bd.py
"""

import sqlite3
from pathlib import Path

# ---------- Rutas ----------
CARPETA_DATABASE = Path(__file__).resolve().parent      # .../DibujAR/database
CARPETA_PROYECTO = CARPETA_DATABASE.parent              # .../DibujAR
ARCHIVO_BD = CARPETA_DATABASE / "dibujar.db"
ARCHIVO_SCHEMA = CARPETA_DATABASE / "schema.sql"
CARPETA_UPLOADS = CARPETA_PROYECTO / "uploads"

# ---------- Datos iniciales de los catalogos ----------
FRECUENCIAS = [
    ("Todos los días", "Dibujo a diario"),
    ("Varias veces por semana", "Dibujo entre 2 y 6 días a la semana"),
    ("Una vez por semana", "Dibujo aproximadamente una vez por semana"),
    ("Algunas veces al mes", "Dibujo de forma ocasional"),
    ("Casi nunca", "Dibujo muy de vez en cuando"),
]

ESTILOS = [
    ("Anime", "Estilo inspirado en la animación japonesa"),
    ("Manga", "Estilo de historieta japonesa"),
    ("Realista", "Dibujos que imitan la realidad"),
    ("Cartoon", "Estilo de caricatura y dibujos animados"),
    ("Pixel Art", "Arte hecho con píxeles"),
    ("Arte digital", "Ilustración hecha con herramientas digitales"),
    ("Boceto", "Dibujos a lápiz y bocetos rápidos"),
    ("Chibi", "Personajes pequeños y tiernos"),
]

TEMATICAS = [
    ("Marvel", "Superhéroes y personajes del universo Marvel"),
    ("Videojuegos", "Personajes y escenas de videojuegos"),
    ("Animales", "Dibujos de animales y mascotas"),
    ("Naturaleza", "Paisajes, plantas y escenas naturales"),
    ("Fantasía", "Criaturas, magia y mundos imaginarios"),
    ("Anime", "Series y personajes de anime"),
    ("Ciencia ficción", "Espacio, robots y tecnología futurista"),
    ("Personajes originales", "Personajes creados por el propio artista"),
]


def preparar_carpetas():
    """Crea la carpeta uploads/ con una subcarpeta por tipo de archivo."""
    for nombre in ("perfiles", "dibujos", "publicaciones", "mensajes"):
        (CARPETA_UPLOADS / nombre).mkdir(parents=True, exist_ok=True)
    print("OK: carpeta uploads/ lista.")


def crear_base_de_datos():
    """Crea dibujar.db y todas sus tablas."""
    if ARCHIVO_BD.exists():
        respuesta = input(
            "Ya existe dibujar.db. Si continuas se BORRARAN todos sus datos.\n"
            "Escribe 'si' para recrearla: "
        )
        if respuesta.strip().lower() != "si":
            print("Cancelado. No se modifico nada.")
            return False
        ARCHIVO_BD.unlink()

    esquema = ARCHIVO_SCHEMA.read_text(encoding="utf-8")

    conexion = sqlite3.connect(ARCHIVO_BD)
    try:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(esquema)

        conexion.executemany(
            "INSERT INTO FRECUENCIA_DIBUJO (nombre, descripcion) VALUES (?, ?)", FRECUENCIAS
        )
        conexion.executemany(
            "INSERT INTO ESTILO (nombre, descripcion) VALUES (?, ?)", ESTILOS
        )
        conexion.executemany(
            "INSERT INTO TEMATICA (nombre, descripcion) VALUES (?, ?)", TEMATICAS
        )
        conexion.commit()
    except Exception as error:
        conexion.close()
        if ARCHIVO_BD.exists():
            ARCHIVO_BD.unlink()
        print("ERROR al crear la base de datos:", error)
        return False

    conexion.close()
    print(f"OK: base de datos creada en {ARCHIVO_BD}")
    return True


def mostrar_resumen():
    """Muestra las tablas creadas y cuantos registros tiene cada una."""
    conexion = sqlite3.connect(ARCHIVO_BD)
    tablas = conexion.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    print(f"\nTablas creadas: {len(tablas)}")
    for (nombre,) in tablas:
        total = conexion.execute(f"SELECT COUNT(*) FROM {nombre}").fetchone()[0]
        print(f"  - {nombre}: {total} registros")
    conexion.close()


if __name__ == "__main__":
    preparar_carpetas()
    if crear_base_de_datos():
        mostrar_resumen()
