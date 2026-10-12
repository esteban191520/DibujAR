# DibujAR

Red social para personas que dibujan. Proyecto escolar con **Python + FastAPI + SQLite**.

## Estado actual
- Base de datos SQLite (14 tablas) - lista
- API FastAPI: registro/login (JWT), publicaciones, feed Inicio/Explorar, likes, comentarios - lista
- Frontend (HTML/CSS/JS + anime.js + Motion): login/registro, Inicio, Explorar, publicar, likes, comentarios, perfil basico - listo
- Pendiente: editor de dibujo, amistades, mensajes, buscar

## Tecnologias
Python 3.10+, FastAPI, Uvicorn, SQLite, PyJWT, python-multipart.

## Instalacion
```
python -m venv venv
venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
python database/crear_bd.py
```

## Ejecucion
```
uvicorn backend.main:app --reload
```
Abre http://127.0.0.1:8000 para usar la aplicacion y http://127.0.0.1:8000/docs para probar la API.

## Estructura
```
DibujAR/
  backend/main.py          API FastAPI
  database/schema.sql      Estructura de las 14 tablas
  database/crear_bd.py     Crea dibujar.db y carga los catalogos
  frontend/index.html      Aplicacion web (usa la API con fetch)
  frontend/vendor/         anime.js y Motion (incluidos, sin internet)
  uploads/                 Archivos subidos (solo se guarda la ruta en la BD)
  requirements.txt
```
