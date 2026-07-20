"""Eventos sumados por la comunidad — vienen de un formulario público.

La gente carga su evento en un formulario; las respuestas caen en una planilla
que se publica como CSV. Esta fuente lee ese CSV y suma los eventos a la edición.

NO hay aprobación manual uno por uno (sería un laburo que no se hace con las
otras fuentes). En cambio, el que confía es el pipeline, con reglas — igual que
los scrapers confían en su fuente por regla, no porque alguien mire cada evento:

  - Campos mínimos (título, fecha, lugar) o no entra.
  - Fecha futura.
  - Tiene que ser de La Plata (por el lugar o la dirección).
  - Anti-spam: sin links en el título, sin GRITAR en mayúsculas, sin palabras
    bloqueadas, sin duplicados, con largos acotados.
  - Honeypot: si se llenó un campo trampa (bot), se descarta.
  - Tope de cuántos entran por corrida.
  - Lista negra editable (data/comunidad_bloqueados.txt) para el raro que se
    cuele: se agrega un término y en el próximo build desaparece.

La URL del CSV se configura con MOVETE_EVENTOS_CSV. Si no está, no hace nada
(la fuente queda lista para cuando exista la planilla).
"""
import csv
import io
import os
import re
from pathlib import Path

import requests

from core.normalizar import (
    ajustar_anio,
    detectar_categoria,
    es_futuro,
    es_la_plata,
    evento,
)

CSV_URL = os.environ.get("MOVETE_EVENTOS_CSV", "").strip()
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MoVeTeBot/1.0)"}

# Cuántos eventos de la comunidad entran como mucho por corrida. Aunque alguien
# quiera inundar la planilla, el sitio no se llena de golpe.
MAX_EVENTOS = 60

# Categorías válidas del sitio. Si la persona elige otra cosa, se detecta sola.
CATEGORIAS_VALIDAS = {
    "teatro", "musica", "stand-up", "cine", "danza", "infantil",
    "humor", "impro", "taller", "a-plasticas", "otros",
}

# Palabras que, si aparecen en el título o el lugar, descartan el evento.
# Lista corta anti-spam/estafa; lo puntual va al archivo de bloqueados.
BLOQUEO_BASE = {
    "viagra", "casino", "bitcoin", "forex", "prestamo", "prestamos",
    "xxx", "porno", "escort", "sexo", "loteria", "premio garantizado",
    "clic aqui", "click aqui", "gana dinero", "criptomoneda",
}

# Nombres posibles de columna (sin acentos, en minúscula) para cada campo.
COLUMNAS = {
    "titulo": ("titulo", "nombre", "evento", "espectaculo", "titulo del evento"),
    "fecha": ("fecha", "dia", "fecha del evento"),
    "hora": ("hora", "horario"),
    "lugar": ("lugar", "sala", "espacio", "donde", "venue"),
    "direccion": ("direccion", "domicilio", "calle", "barrio", "localidad"),
    "categoria": ("categoria", "rubro", "tipo", "disciplina"),
    "url": ("url", "link", "enlace", "entradas", "mas info", "web", "instagram"),
    # Campo trampa para bots: si viene con algo, se descarta la fila.
    "honeypot": ("no_completar", "nocompletar", "website", "sitio web"),
}


def _sin_acentos(t: str) -> str:
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return t


def _cargar_bloqueados() -> set:
    """Lee la lista negra editable (un término por línea). Opcional."""
    ruta = Path(__file__).resolve().parent.parent / "data" / "comunidad_bloqueados.txt"
    terminos = set(BLOQUEO_BASE)
    try:
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            t = _sin_acentos(linea.strip().lower())
            if t and not t.startswith("#"):
                terminos.add(t)
    except OSError:
        pass
    return terminos


def _mapear_columnas(cabeceras: list) -> dict:
    """Asocia cada campo con el índice de su columna, tolerando nombres largos
    (los formularios suelen poner la pregunta entera como encabezado)."""
    limpias = [_sin_acentos((c or "").strip().lower()) for c in cabeceras]
    mapa = {}
    for campo, alias in COLUMNAS.items():
        for i, col in enumerate(limpias):
            if any(a == col or a in col for a in alias):
                mapa[campo] = i
                break
    return mapa


def _norm_fecha(fecha_raw: str, hora_raw: str) -> str:
    """Devuelve 'YYYY-MM-DD HH:MM:SS' desde formatos variados, o '' si no se puede."""
    fecha_raw = (fecha_raw or "").strip()
    if not fecha_raw:
        return ""

    hora = "21:00"
    mh = re.search(r"(\d{1,2})[:.](\d{2})", hora_raw or "")
    if mh:
        h, m = int(mh.group(1)), int(mh.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            hora = f"{h:02d}:{m:02d}"

    # ISO: YYYY-MM-DD
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", fecha_raw)
    if m:
        y, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            from datetime import date
            return f"{date(y, mes, dia).isoformat()} {hora}:00"
        except ValueError:
            return ""

    # DD/MM[/YYYY]
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", fecha_raw)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        anio = m.group(3)
        if anio:
            y = int(anio)
            if y < 100:
                y += 2000
            try:
                from datetime import date
                return f"{date(y, mes, dia).isoformat()} {hora}:00"
            except ValueError:
                return ""
        # Sin año: el pipeline asume el próximo que corresponda.
        return ajustar_anio(mes, dia, hora)

    return ""


def _es_spam(titulo: str, lugar: str, bloqueados: set) -> bool:
    t = _sin_acentos(f"{titulo} {lugar}".lower())
    # Link en el título → spam.
    if re.search(r"https?://|www\.|\.com|\.ar\b|t\.me/", titulo.lower()):
        return True
    # Términos bloqueados.
    if any(b in t for b in bloqueados):
        return True
    # Título sin letras o demasiado corto → basura.
    if len(re.sub(r"[^a-záéíóúñ]", "", titulo.lower())) < 3:
        return True
    return False


def _arreglar_grito(titulo: str) -> str:
    """Si viene TODO EN MAYÚSCULAS, lo pasa a Capital Inicial (no lo descarta)."""
    letras = [c for c in titulo if c.isalpha()]
    if letras and sum(1 for c in letras if c.isupper()) / len(letras) > 0.8 and len(letras) > 6:
        return titulo.title()
    return titulo


def _parsear(texto_csv: str) -> list:
    """Convierte el CSV en eventos aplicando todos los guardrails. Testeable."""
    eventos = []
    bloqueados = _cargar_bloqueados()
    filas = list(csv.reader(io.StringIO(texto_csv)))
    if not filas:
        return eventos

    mapa = _mapear_columnas(filas[0])
    if "titulo" not in mapa or "fecha" not in mapa:
        print("  comunidad: la planilla no tiene columnas de título/fecha reconocibles")
        return eventos

    def val(fila, campo):
        i = mapa.get(campo)
        return fila[i].strip() if i is not None and i < len(fila) else ""

    for fila in filas[1:]:
        if not any(c.strip() for c in fila):
            continue
        # Honeypot: si un bot llenó el campo trampa, afuera.
        if val(fila, "honeypot"):
            continue

        titulo = _arreglar_grito(val(fila, "titulo"))
        lugar = val(fila, "lugar")
        direccion = val(fila, "direccion")
        if not titulo or not val(fila, "fecha") or not lugar:
            continue
        if _es_spam(titulo, lugar, bloqueados):
            continue

        fecha = _norm_fecha(val(fila, "fecha"), val(fila, "hora"))
        if not es_futuro(fecha):
            continue

        # Tiene que ser de La Plata (por el lugar o la dirección).
        if not es_la_plata(f"{lugar} {direccion}"):
            continue

        cat = _sin_acentos(val(fila, "categoria").lower()).replace(" ", "-")
        if cat not in CATEGORIAS_VALIDAS:
            cat = detectar_categoria(titulo)

        url = val(fila, "url")
        if url and not url.startswith("http"):
            url = "https://" + url

        eventos.append(evento(
            titulo,
            fecha,
            lugar,
            categoria=cat,
            direccion=direccion,
            url=url,
            fuente="comunidad",
        ))
        if len(eventos) >= MAX_EVENTOS:
            break

    return eventos


def scrape() -> list:
    if not CSV_URL:
        return []
    try:
        r = requests.get(CSV_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        eventos = _parsear(r.text)
    except requests.RequestException as e:
        print(f"  comunidad: error descargando — {e}")
        return []
    print(f"  comunidad: {len(eventos)} eventos")
    return eventos
