"""
DibujAR - Backend con FastAPI + SQLite
Ejecutar desde la carpeta DibujAR:
    uvicorn backend.main:app --reload
Documentacion automatica: http://127.0.0.1:8000/docs
"""

import hashlib
import os
import re
import secrets
import shutil
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import jwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent.parent
RUTA_BD = RAIZ / "database" / "dibujar.db"
UPLOADS = RAIZ / "uploads"
CLAVE_JWT = os.getenv("DIBUJAR_SECRET", "cambia-esta-clave-antes-de-publicar")
HORAS_TOKEN = 24

app = FastAPI(title="DibujAR API")
(UPLOADS / "publicaciones").mkdir(parents=True, exist_ok=True)
(UPLOADS / "perfiles").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")
seguridad = HTTPBearer(auto_error=False)


# ---------- Base de datos ----------
def get_db():
    if not RUTA_BD.exists():
        raise HTTPException(500, "Falta la base de datos: ejecuta python database/crear_bd.py")
    con = sqlite3.connect(RUTA_BD, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
    finally:
        con.close()


# ---------- Contrasenas y JWT ----------
def hashear(contrasena: str) -> str:
    sal = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", contrasena.encode(), bytes.fromhex(sal), 200_000)
    return f"{sal}${h.hex()}"


def verificar(contrasena: str, guardado: str) -> bool:
    sal, h = guardado.split("$")
    nuevo = hashlib.pbkdf2_hmac("sha256", contrasena.encode(), bytes.fromhex(sal), 200_000)
    return secrets.compare_digest(nuevo.hex(), h)


def crear_token(id_usuario: int) -> str:
    vence = datetime.now(timezone.utc) + timedelta(hours=HORAS_TOKEN)
    return jwt.encode({"sub": str(id_usuario), "exp": vence}, CLAVE_JWT, algorithm="HS256")


def usuario_actual(cred: Optional[HTTPAuthorizationCredentials] = Depends(seguridad),
                   db: sqlite3.Connection = Depends(get_db)):
    if cred is None:
        raise HTTPException(401, "Debes iniciar sesion")
    try:
        datos = jwt.decode(cred.credentials, CLAVE_JWT, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token invalido o vencido")
    fila = db.execute("SELECT * FROM USUARIO WHERE id_usuario = ?", (int(datos["sub"]),)).fetchone()
    if fila is None:
        raise HTTPException(401, "El usuario ya no existe")
    return fila


# ---------- Username: validacion y sugerencias ----------
PATRON_USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.]{2,29}$")


def normalizar_texto(texto: str) -> str:
    """Quita acentos, pasa a minusculas, deja solo a-z0-9._"""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9_.]", "", texto)
    return texto


def username_disponible(db, username: str) -> bool:
    fila = db.execute("SELECT 1 FROM USUARIO WHERE username = ?", (username,)).fetchone()
    return fila is None


def generar_sugerencias(db, base: str, cantidad: int = 4) -> list:
    """Genera sugerencias respetando lo que el usuario escribio.
    Ej: si escribio 'esteban_leyva12131', prueba con 'esteban_leyva12131_1', etc.
    """
    base = base[:26]  # dejar espacio para sufijos
    sugerencias = []
    intentos = 0
    max_intentos = 50

    # Estrategias variadas para que se vean naturales
    estrategias = [
        lambda n: f"{base}_{n}",
        lambda n: f"{base}{n}",
        lambda n: f"{base}.{n}",
        lambda n: f"soy_{base}",
        lambda n: f"{base}_oficial",
        lambda n: f"{base}_art",
        lambda n: f"the_{base}",
        lambda n: f"{base}.oficial",
        lambda n: f"{base}_{n}0",
        lambda n: f"real_{base}",
    ]

    import random
    random.shuffle(estrategias)

    n = 1
    while len(sugerencias) < cantidad and intentos < max_intentos:
        for estrategia in estrategias:
            if len(sugerencias) >= cantidad:
                break
            if callable(estrategia) and estrategia.__code__.co_argcount == 1:
                # Si la estrategia no usa numero, solo se prueba una vez
                candidato = estrategia(0)
                if candidato in sugerencias:
                    continue
            else:
                candidato = estrategia(n)

            if len(candidato) > 30 or len(candidato) < 3:
                continue
            if not PATRON_USERNAME.match(candidato):
                continue
            if candidato in sugerencias:
                continue
            if username_disponible(db, candidato):
                sugerencias.append(candidato)
        n += 1
        intentos += 1

    return sugerencias[:cantidad]


# ---------- Esquemas ----------
class Registro(BaseModel):
    nombre: str
    apellido: str
    username: str
    correo: str
    contrasena: str
    pais: str
    fecha_nacimiento: str
    id_frecuencia: Optional[int] = None
    estilos: List[int] = []
    tematicas: List[int] = []


class Login(BaseModel):
    correo: str
    contrasena: str


class NuevoComentario(BaseModel):
    contenido: str


class EditarPerfil(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    bio: Optional[str] = None
    username: Optional[str] = None
    id_frecuencia: Optional[int] = None
    estilos: Optional[List[int]] = None
    tematicas: Optional[List[int]] = None


# ---------- Autenticacion ----------
@app.post("/auth/registro", status_code=201)
def registro(d: Registro, db: sqlite3.Connection = Depends(get_db)):
    if len(d.contrasena) < 6:
        raise HTTPException(400, "La contrasena debe tener al menos 6 caracteres")

    username = normalizar_texto(d.username)
    if not PATRON_USERNAME.match(username):
        raise HTTPException(400, "El @usuario debe tener entre 3 y 30 caracteres: solo letras minusculas, numeros, _ y .")
    if not username_disponible(db, username):
        raise HTTPException(409, "Ese @usuario ya esta en uso")

    try:
        cur = db.execute(
            "INSERT INTO USUARIO (nombre, apellido, username, correo, contrasena, pais, fecha_nacimiento, id_frecuencia) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d.nombre.strip(), d.apellido.strip(), username, d.correo.strip().lower(),
             hashear(d.contrasena), d.pais.strip(), d.fecha_nacimiento, d.id_frecuencia))
        id_usuario = cur.lastrowid
        for e in set(d.estilos):
            db.execute("INSERT INTO USUARIO_ESTILO VALUES (?, ?)", (id_usuario, e))
        for t in set(d.tematicas):
            db.execute("INSERT INTO USUARIO_TEMATICA VALUES (?, ?)", (id_usuario, t))
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        if "USUARIO.correo" in str(error):
            raise HTTPException(409, "Ese correo ya esta registrado")
        if "USUARIO.username" in str(error):
            raise HTTPException(409, "Ese @usuario ya esta en uso")
        raise HTTPException(400, "Datos invalidos (revisa frecuencia, estilos o tematicas)")
    return {"id_usuario": id_usuario, "token": crear_token(id_usuario)}


@app.post("/auth/login")
def login(d: Login, db: sqlite3.Connection = Depends(get_db)):
    u = db.execute("SELECT * FROM USUARIO WHERE correo = ?", (d.correo.strip().lower(),)).fetchone()
    if u is None or not verificar(d.contrasena, u["contrasena"]):
        raise HTTPException(401, "Correo o contrasena incorrectos")
    return {"token": crear_token(u["id_usuario"]), "id_usuario": u["id_usuario"]}


# ---------- Catalogos ----------
@app.get("/frecuencias")
def frecuencias(db: sqlite3.Connection = Depends(get_db)):
    return [dict(f) for f in db.execute("SELECT * FROM FRECUENCIA_DIBUJO")]


@app.get("/estilos")
def estilos(db: sqlite3.Connection = Depends(get_db)):
    return [dict(f) for f in db.execute("SELECT * FROM ESTILO")]


@app.get("/tematicas")
def tematicas(db: sqlite3.Connection = Depends(get_db)):
    return [dict(f) for f in db.execute("SELECT * FROM TEMATICA")]


# ---------- Disponibilidad de username ----------
@app.get("/usuarios/disponible/{username}")
def check_username(username: str, db: sqlite3.Connection = Depends(get_db)):
    username = normalizar_texto(username)

    if len(username) < 3:
        return {"disponible": False, "error": "Minimo 3 caracteres", "sugerencias": []}
    if len(username) > 30:
        return {"disponible": False, "error": "Maximo 30 caracteres", "sugerencias": []}
    if not PATRON_USERNAME.match(username):
        return {
            "disponible": False,
            "error": "Solo letras minusculas, numeros, _ y . (no puede empezar con . ni _)",
            "sugerencias": []
        }

    if username_disponible(db, username):
        return {"disponible": True, "username": username, "sugerencias": []}

    sugerencias = generar_sugerencias(db, username)
    return {
        "disponible": False,
        "error": "Ese @usuario ya esta en uso",
        "sugerencias": sugerencias
    }


# ---------- Publicaciones SQL base ----------
SQL_PUBLICACIONES = """
SELECT p.id_publicacion, p.id_usuario, u.nombre || ' ' || u.apellido AS autor,
       u.username, u.foto_perfil,
       p.tipo, p.archivo, p.descripcion, p.fecha_publicacion,
       (SELECT COUNT(*) FROM LIKE_PUBLICACION l WHERE l.id_publicacion = p.id_publicacion) AS likes,
       (SELECT COUNT(*) FROM COMENTARIO c WHERE c.id_publicacion = p.id_publicacion) AS comentarios,
       EXISTS(SELECT 1 FROM LIKE_PUBLICACION l
              WHERE l.id_publicacion = p.id_publicacion AND l.id_usuario = :yo) AS yo_di_like
FROM PUBLICACION p JOIN USUARIO u ON u.id_usuario = p.id_usuario
"""


def con_hashtags(db, filas):
    resultado = []
    for f in filas:
        pub = dict(f)
        pub["yo_di_like"] = bool(pub["yo_di_like"])
        pub["hashtags"] = [h["nombre"] for h in db.execute(
            "SELECT h.nombre FROM HASHTAG h JOIN PUBLICACION_HASHTAG ph ON ph.id_hashtag = h.id_hashtag "
            "WHERE ph.id_publicacion = ?", (pub["id_publicacion"],))]
        resultado.append(pub)
    return resultado


# ---------- Usuario: leer, editar, foto ----------
def _perfil_publico(db, fila_usuario, incluir_correo=False):
    u = dict(fila_usuario)
    u.pop("contrasena", None)
    if not incluir_correo:
        u.pop("correo", None)

    idu = u["id_usuario"]

    u["estilos"] = [dict(f) for f in db.execute(
        "SELECT e.id_estilo, e.nombre FROM ESTILO e "
        "JOIN USUARIO_ESTILO ue ON ue.id_estilo = e.id_estilo "
        "WHERE ue.id_usuario = ? ORDER BY e.nombre", (idu,))]
    u["tematicas"] = [dict(f) for f in db.execute(
        "SELECT t.id_tematica, t.nombre FROM TEMATICA t "
        "JOIN USUARIO_TEMATICA ut ON ut.id_tematica = t.id_tematica "
        "WHERE ut.id_usuario = ? ORDER BY t.nombre", (idu,))]

    u["frecuencia"] = None
    if u.get("id_frecuencia"):
        f = db.execute("SELECT nombre FROM FRECUENCIA_DIBUJO WHERE id_frecuencia = ?",
                       (u["id_frecuencia"],)).fetchone()
        if f:
            u["frecuencia"] = f["nombre"]

    u["total_publicaciones"] = db.execute(
        "SELECT COUNT(*) FROM PUBLICACION WHERE id_usuario = ?", (idu,)).fetchone()[0]

    u["total_amigos"] = db.execute(
        "SELECT COUNT(*) FROM AMISTAD WHERE estado = 'aceptada' "
        "AND (id_usuario = ? OR id_amigo = ?)", (idu, idu)).fetchone()[0]

    return u


@app.get("/usuarios/yo")
def mi_usuario(u=Depends(usuario_actual), db: sqlite3.Connection = Depends(get_db)):
    return _perfil_publico(db, u, incluir_correo=True)


@app.get("/usuarios/u/{username}")
def ver_usuario_por_username(username: str, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    username = normalizar_texto(username)
    fila = db.execute("SELECT * FROM USUARIO WHERE username = ?", (username,)).fetchone()
    if fila is None:
        raise HTTPException(404, "Usuario no encontrado")
    return _perfil_publico(db, fila, incluir_correo=False)


@app.get("/usuarios/{id_usuario}")
def ver_usuario(id_usuario: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    fila = db.execute("SELECT * FROM USUARIO WHERE id_usuario = ?", (id_usuario,)).fetchone()
    if fila is None:
        raise HTTPException(404, "Usuario no encontrado")
    return _perfil_publico(db, fila, incluir_correo=False)


@app.put("/usuarios/yo")
def editar_perfil(d: EditarPerfil, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    idu = u["id_usuario"]
    campos = []
    valores = []

    if d.nombre is not None:
        campos.append("nombre = ?")
        valores.append(d.nombre.strip())
    if d.apellido is not None:
        campos.append("apellido = ?")
        valores.append(d.apellido.strip())
    if d.bio is not None:
        campos.append("bio = ?")
        valores.append(d.bio.strip() or None)
    if d.id_frecuencia is not None:
        campos.append("id_frecuencia = ?")
        valores.append(d.id_frecuencia)

    if d.username is not None:
        username = normalizar_texto(d.username)
        if not PATRON_USERNAME.match(username):
            raise HTTPException(400, "El @usuario debe tener entre 3 y 30 caracteres: solo letras minusculas, numeros, _ y .")
        if username != u["username"]:
            if not username_disponible(db, username):
                raise HTTPException(409, "Ese @usuario ya esta en uso")
            campos.append("username = ?")
            valores.append(username)

    if campos:
        valores.append(idu)
        try:
            db.execute(f"UPDATE USUARIO SET {', '.join(campos)} WHERE id_usuario = ?", valores)
        except sqlite3.IntegrityError as error:
            db.rollback()
            if "USUARIO.username" in str(error):
                raise HTTPException(409, "Ese @usuario ya esta en uso")
            raise HTTPException(400, "Datos invalidos")

    if d.estilos is not None:
        db.execute("DELETE FROM USUARIO_ESTILO WHERE id_usuario = ?", (idu,))
        for e in set(d.estilos):
            db.execute("INSERT INTO USUARIO_ESTILO VALUES (?, ?)", (idu, e))

    if d.tematicas is not None:
        db.execute("DELETE FROM USUARIO_TEMATICA WHERE id_usuario = ?", (idu,))
        for t in set(d.tematicas):
            db.execute("INSERT INTO USUARIO_TEMATICA VALUES (?, ?)", (idu, t))

    db.commit()
    fila = db.execute("SELECT * FROM USUARIO WHERE id_usuario = ?", (idu,)).fetchone()
    return _perfil_publico(db, fila, incluir_correo=True)


@app.post("/usuarios/yo/foto")
def subir_foto(archivo: UploadFile = File(...), db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    ext = Path(archivo.filename or "").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        raise HTTPException(400, "Formato no permitido (usa png, jpg, jpeg, gif o webp)")

    nombre = f"{uuid.uuid4().hex}{ext}"
    destino = UPLOADS / "perfiles" / nombre
    with open(destino, "wb") as f:
        shutil.copyfileobj(archivo.file, f)

    ruta_rel = f"uploads/perfiles/{nombre}"
    db.execute("UPDATE USUARIO SET foto_perfil = ? WHERE id_usuario = ?", (ruta_rel, u["id_usuario"]))
    db.commit()

    if u["foto_perfil"]:
        vieja = RAIZ / u["foto_perfil"]
        if vieja.exists() and "perfiles" in str(vieja):
            vieja.unlink(missing_ok=True)

    return {"foto_perfil": ruta_rel}


@app.get("/usuarios/{id_usuario}/publicaciones")
def publicaciones_de_usuario(id_usuario: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    filas = db.execute(SQL_PUBLICACIONES + " WHERE p.id_usuario = :id ORDER BY p.fecha_publicacion DESC",
                       {"yo": u["id_usuario"], "id": id_usuario}).fetchall()
    return con_hashtags(db, filas)


@app.get("/usuarios/yo/likes")
def mis_likes(db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    filas = db.execute(
        SQL_PUBLICACIONES + """
        WHERE p.id_publicacion IN (
            SELECT id_publicacion FROM LIKE_PUBLICACION WHERE id_usuario = :yo
        )
        ORDER BY p.fecha_publicacion DESC
        """, {"yo": u["id_usuario"]}).fetchall()
    return con_hashtags(db, filas)


# ---------- Publicaciones ----------
@app.get("/publicaciones")
def listar_publicaciones(modo: str = "inicio", limite: int = 20, desplazar: int = 0,
                         db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    yo = u["id_usuario"]
    if modo == "inicio":
        filtro = """WHERE p.id_usuario = :yo OR p.id_usuario IN (
                      SELECT id_amigo FROM AMISTAD WHERE id_usuario = :yo AND estado = 'aceptada'
                      UNION
                      SELECT id_usuario FROM AMISTAD WHERE id_amigo = :yo AND estado = 'aceptada')"""
    elif modo == "explorar":
        filtro = ""
    else:
        raise HTTPException(400, "modo debe ser 'inicio' o 'explorar'")
    sql = SQL_PUBLICACIONES + filtro + " ORDER BY p.fecha_publicacion DESC, p.id_publicacion DESC LIMIT :l OFFSET :o"
    filas = db.execute(sql, {"yo": yo, "l": limite, "o": desplazar}).fetchall()
    return con_hashtags(db, filas)


@app.get("/publicaciones/{id_publicacion}")
def obtener_publicacion(id_publicacion: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    fila = db.execute(SQL_PUBLICACIONES + " WHERE p.id_publicacion = :id",
                      {"yo": u["id_usuario"], "id": id_publicacion}).fetchall()
    if not fila:
        raise HTTPException(404, "Publicacion no encontrada")
    return con_hashtags(db, fila)[0]


@app.post("/publicaciones", status_code=201)
def crear_publicacion(descripcion: str = Form(""), hashtags: str = Form(""), archivo: UploadFile = File(...),
                      db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    ext = Path(archivo.filename or "").suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        tipo = "imagen"
    elif ext in (".mp4", ".webm", ".mov"):
        tipo = "video"
    else:
        raise HTTPException(400, "Formato no permitido (usa imagen o video)")

    nombre = f"{uuid.uuid4().hex}{ext}"
    with open(UPLOADS / "publicaciones" / nombre, "wb") as destino:
        shutil.copyfileobj(archivo.file, destino)

    cur = db.execute("INSERT INTO PUBLICACION (id_usuario, tipo, archivo, descripcion) VALUES (?, ?, ?, ?)",
                     (u["id_usuario"], tipo, f"uploads/publicaciones/{nombre}", descripcion.strip() or None))
    id_pub = cur.lastrowid
    for h in {x.strip().lstrip("#").lower() for x in hashtags.replace(",", " ").split()} - {""}:
        db.execute("INSERT OR IGNORE INTO HASHTAG (nombre) VALUES (?)", (h,))
        id_h = db.execute("SELECT id_hashtag FROM HASHTAG WHERE nombre = ?", (h,)).fetchone()[0]
        db.execute("INSERT INTO PUBLICACION_HASHTAG VALUES (?, ?)", (id_pub, id_h))
    db.commit()
    return {"id_publicacion": id_pub, "tipo": tipo}


@app.delete("/publicaciones/{id_publicacion}", status_code=204)
def eliminar_publicacion(id_publicacion: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    pub = db.execute("SELECT id_usuario, archivo FROM PUBLICACION WHERE id_publicacion = ?", (id_publicacion,)).fetchone()
    if pub is None:
        raise HTTPException(404, "Publicacion no encontrada")
    if pub["id_usuario"] != u["id_usuario"]:
        raise HTTPException(403, "Solo puedes eliminar tus propias publicaciones")
    db.execute("DELETE FROM PUBLICACION WHERE id_publicacion = ?", (id_publicacion,))
    db.commit()
    (RAIZ / pub["archivo"]).unlink(missing_ok=True)


# ---------- Likes ----------
@app.post("/publicaciones/{id_publicacion}/like", status_code=201)
def dar_like(id_publicacion: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    try:
        db.execute("INSERT INTO LIKE_PUBLICACION (id_usuario, id_publicacion) VALUES (?, ?)",
                   (u["id_usuario"], id_publicacion))
        db.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE" in str(error):
            raise HTTPException(409, "Ya diste like a esta publicacion")
        raise HTTPException(404, "Publicacion no encontrada")
    total = db.execute("SELECT COUNT(*) FROM LIKE_PUBLICACION WHERE id_publicacion = ?", (id_publicacion,)).fetchone()[0]
    return {"likes": total}


@app.delete("/publicaciones/{id_publicacion}/like")
def quitar_like(id_publicacion: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    db.execute("DELETE FROM LIKE_PUBLICACION WHERE id_usuario = ? AND id_publicacion = ?",
               (u["id_usuario"], id_publicacion))
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM LIKE_PUBLICACION WHERE id_publicacion = ?", (id_publicacion,)).fetchone()[0]
    return {"likes": total}


# ---------- Comentarios ----------
@app.get("/publicaciones/{id_publicacion}/comentarios")
def listar_comentarios(id_publicacion: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    filas = db.execute(
        "SELECT c.id_comentario, c.id_usuario, u.nombre || ' ' || u.apellido AS autor, "
        "u.username, c.contenido, c.fecha_comentario "
        "FROM COMENTARIO c JOIN USUARIO u ON u.id_usuario = c.id_usuario "
        "WHERE c.id_publicacion = ? ORDER BY c.fecha_comentario, c.id_comentario", (id_publicacion,))
    return [dict(f) for f in filas]


@app.post("/publicaciones/{id_publicacion}/comentarios", status_code=201)
def comentar(id_publicacion: int, d: NuevoComentario, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    if not d.contenido.strip():
        raise HTTPException(400, "El comentario no puede estar vacio")
    try:
        cur = db.execute("INSERT INTO COMENTARIO (id_usuario, id_publicacion, contenido) VALUES (?, ?, ?)",
                         (u["id_usuario"], id_publicacion, d.contenido.strip()))
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(404, "Publicacion no encontrada")
    return {"id_comentario": cur.lastrowid}


@app.delete("/comentarios/{id_comentario}", status_code=204)
def eliminar_comentario(id_comentario: int, db: sqlite3.Connection = Depends(get_db), u=Depends(usuario_actual)):
    c = db.execute("SELECT id_usuario FROM COMENTARIO WHERE id_comentario = ?", (id_comentario,)).fetchone()
    if c is None:
        raise HTTPException(404, "Comentario no encontrado")
    if c["id_usuario"] != u["id_usuario"]:
        raise HTTPException(403, "Solo puedes eliminar tus propios comentarios")
    db.execute("DELETE FROM COMENTARIO WHERE id_comentario = ?", (id_comentario,))
    db.commit()


# ---------- ENDPOINTS TEMPORALES DE PRUEBA (borrar antes de entregar) ----------
@app.get("/debug/usuarios")
def debug_usuarios(db: sqlite3.Connection = Depends(get_db)):
    filas = db.execute(
        "SELECT id_usuario, nombre, apellido, username, correo, bio, foto_perfil FROM USUARIO"
    ).fetchall()
    return {"total": len(filas), "usuarios": [dict(f) for f in filas]}


@app.get("/debug/mi-perfil")
def debug_mi_perfil(usuario_id: int, db: sqlite3.Connection = Depends(get_db)):
    fila = db.execute("SELECT * FROM USUARIO WHERE id_usuario = ?", (usuario_id,)).fetchone()
    if fila is None:
        raise HTTPException(404, "Usuario no encontrado")
    return _perfil_publico(db, fila, incluir_correo=True)


# ---------- Frontend (siempre al final) ----------
(RAIZ / "frontend").mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=RAIZ / "frontend", html=True), name="frontend")