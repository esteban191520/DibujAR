-- ============================================================
-- DibujAR - Esquema SQLite (14 tablas)
-- Este archivo crea SOLO la estructura. Los datos iniciales
-- (catalogos) los inserta crear_bd.py.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ---------- CATALOGOS ----------

CREATE TABLE FRECUENCIA_DIBUJO (
    id_frecuencia  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL UNIQUE,
    descripcion    TEXT
);

CREATE TABLE ESTILO (
    id_estilo      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL UNIQUE,
    descripcion    TEXT
);

CREATE TABLE TEMATICA (
    id_tematica    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL UNIQUE,
    descripcion    TEXT
);

-- ---------- USUARIO ----------

CREATE TABLE USUARIO (
    id_usuario        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL,
    apellido          TEXT NOT NULL,
    correo            TEXT NOT NULL UNIQUE,
    contrasena        TEXT NOT NULL,          -- aqui se guarda el HASH, nunca la contrasena real
    pais              TEXT NOT NULL,
    fecha_nacimiento  DATE NOT NULL,
    foto_perfil       TEXT,
    id_frecuencia     INTEGER,
    CONSTRAINT CK_USUARIO_CORREO CHECK (length(correo) > 3),
    CONSTRAINT FK_USUARIO_FRECUENCIA FOREIGN KEY (id_frecuencia)
        REFERENCES FRECUENCIA_DIBUJO (id_frecuencia) ON DELETE SET NULL
);

CREATE TABLE USUARIO_ESTILO (
    id_usuario  INTEGER NOT NULL,
    id_estilo   INTEGER NOT NULL,
    PRIMARY KEY (id_usuario, id_estilo),
    CONSTRAINT FK_USUESTILO_USUARIO FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_USUESTILO_ESTILO FOREIGN KEY (id_estilo)
        REFERENCES ESTILO (id_estilo) ON DELETE CASCADE
);

CREATE TABLE USUARIO_TEMATICA (
    id_usuario   INTEGER NOT NULL,
    id_tematica  INTEGER NOT NULL,
    PRIMARY KEY (id_usuario, id_tematica),
    CONSTRAINT FK_USUTEMATICA_USUARIO FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_USUTEMATICA_TEMATICA FOREIGN KEY (id_tematica)
        REFERENCES TEMATICA (id_tematica) ON DELETE CASCADE
);

-- ---------- DIBUJOS Y PUBLICACIONES ----------

CREATE TABLE DIBUJO (
    id_dibujo           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario          INTEGER NOT NULL,
    nombre              TEXT NOT NULL,
    archivo             TEXT NOT NULL,
    fecha_creacion      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT CK_DIBUJO_NOMBRE CHECK (length(trim(nombre)) > 0),
    CONSTRAINT FK_DIBUJO_USUARIO FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE
);

CREATE TABLE PUBLICACION (
    id_publicacion     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario         INTEGER NOT NULL,
    id_dibujo          INTEGER UNIQUE,        -- opcional (NULL si no viene de un dibujo)
    tipo               TEXT NOT NULL,
    archivo            TEXT NOT NULL,
    descripcion        TEXT,
    fecha_publicacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT CK_PUBLICACION_TIPO CHECK (tipo IN ('imagen', 'video')),
    CONSTRAINT FK_PUBLICACION_USUARIO FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_PUBLICACION_DIBUJO FOREIGN KEY (id_dibujo)
        REFERENCES DIBUJO (id_dibujo) ON DELETE SET NULL
);

-- ---------- INTERACCIONES ----------

CREATE TABLE LIKE_PUBLICACION (
    id_usuario      INTEGER NOT NULL,
    id_publicacion  INTEGER NOT NULL,
    fecha_like      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario, id_publicacion),
    CONSTRAINT FK_LIKE_USUARIO FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_LIKE_PUBLICACION FOREIGN KEY (id_publicacion)
        REFERENCES PUBLICACION (id_publicacion) ON DELETE CASCADE
);

CREATE TABLE COMENTARIO (
    id_comentario     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario        INTEGER NOT NULL,
    id_publicacion    INTEGER NOT NULL,
    contenido         TEXT NOT NULL,
    fecha_comentario  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT CK_COMENTARIO_CONTENIDO CHECK (length(trim(contenido)) > 0),
    CONSTRAINT FK_COMENTARIO_USUARIO FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_COMENTARIO_PUBLICACION FOREIGN KEY (id_publicacion)
        REFERENCES PUBLICACION (id_publicacion) ON DELETE CASCADE
);

-- ---------- HASHTAGS ----------

CREATE TABLE HASHTAG (
    id_hashtag  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,         -- sin '#' y en minusculas
    CONSTRAINT CK_HASHTAG_NOMBRE CHECK (length(trim(nombre)) > 0 AND nombre = lower(nombre))
);

CREATE TABLE PUBLICACION_HASHTAG (
    id_publicacion  INTEGER NOT NULL,
    id_hashtag      INTEGER NOT NULL,
    PRIMARY KEY (id_publicacion, id_hashtag),
    CONSTRAINT FK_PUBHASH_PUBLICACION FOREIGN KEY (id_publicacion)
        REFERENCES PUBLICACION (id_publicacion) ON DELETE CASCADE,
    CONSTRAINT FK_PUBHASH_HASHTAG FOREIGN KEY (id_hashtag)
        REFERENCES HASHTAG (id_hashtag) ON DELETE CASCADE
);

-- ---------- AMISTADES Y MENSAJES ----------

CREATE TABLE AMISTAD (
    id_amistad       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario       INTEGER NOT NULL,        -- quien envia la solicitud
    id_amigo         INTEGER NOT NULL,        -- quien la recibe
    estado           TEXT NOT NULL DEFAULT 'pendiente',
    fecha_solicitud  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT UQ_AMISTAD_PAR UNIQUE (id_usuario, id_amigo),
    CONSTRAINT CK_AMISTAD_DISTINTOS CHECK (id_usuario <> id_amigo),
    CONSTRAINT CK_AMISTAD_ESTADO CHECK (estado IN ('pendiente', 'aceptada', 'rechazada')),
    CONSTRAINT FK_AMISTAD_SOLICITANTE FOREIGN KEY (id_usuario)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_AMISTAD_RECEPTOR FOREIGN KEY (id_amigo)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE
);

CREATE TABLE MENSAJE (
    id_mensaje      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_emisor       INTEGER NOT NULL,
    id_receptor     INTEGER NOT NULL,
    id_publicacion  INTEGER,                  -- publicacion compartida (opcional)
    contenido       TEXT,
    archivo         TEXT,
    fecha_envio     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    leido           BOOLEAN NOT NULL DEFAULT 0,
    CONSTRAINT CK_MENSAJE_DISTINTOS CHECK (id_emisor <> id_receptor),
    CONSTRAINT CK_MENSAJE_LEIDO CHECK (leido IN (0, 1)),
    CONSTRAINT FK_MENSAJE_EMISOR FOREIGN KEY (id_emisor)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_MENSAJE_RECEPTOR FOREIGN KEY (id_receptor)
        REFERENCES USUARIO (id_usuario) ON DELETE CASCADE,
    CONSTRAINT FK_MENSAJE_PUBLICACION FOREIGN KEY (id_publicacion)
        REFERENCES PUBLICACION (id_publicacion) ON DELETE SET NULL
);
