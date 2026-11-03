"""Passline — ticketera, sobre todo música/recitales.

Passline no lista por ciudad: se organiza por 'productora'. Se scrapea una lista
curada de productoras que son salas platenses (empezando por Espacio Live). Cada
página de productora trae sus eventos ya con fecha, lugar, imagen y link de compra.

Para sumar una sala nueva: agregar su slug de productora a PRODUCTORAS
(con lugares=None si la cuenta es de la sala, o la tupla de salas platenses).
"""
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from core.normalizar import (EXCLUIR, _sin_acentos, detectar_categoria, es_futuro,
                             es_la_plata, evento)

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}
BASE = "https://www.passline.com/productora/"

# Productoras de Passline del Gran La Plata: slug -> (categoría por defecto, lugares).
# Passline muestra como lugar solo el nombre de la sala ("Espacio Live", "Casa
# Suiza"), sin ciudad, así que es_la_plata(lugar) daba siempre False y se
# descartaba todo. Ahora:
#   - lugares = None: la productora ES una sala platense, entra todo salvo que el
#     título o el lugar nombren otra ciudad.
#   - lugares = (...): la cuenta vende también en otras ciudades; entra solo si el
#     lugar es una de esas salas platenses o si título/lugar dicen La Plata.
PRODUCTORAS = {
    "live-club-la-plata": ("musica", None),                          # Espacio Live
    # Relevadas el 01/11/2026.
    "7831099-casa-suiza": ("musica", None),                          # Casa Suiza
    "13880381-diego-martin-yuma": ("musica", ("rene favaloro",)),    # Carpo Producciones
    "137690-rc_shows": ("musica", ("hopeless",)),                    # Hopeless (Bye Henry)
    "8724325-danny-brichetti": ("musica", ("guajira", "nuevos vientos")),
    "13571230-tomas-munoz": ("musica", ("vonharv",)),                # LA TM +35
    "la-magica": ("musica", ("estadio uno",)),                       # La Mágica
    "10361152-jacob-scattini-aldana": ("otros", ("pampa cultural",)),  # La Cruzada Poética
    "veronica-bassus": ("otros", ("la nonna",)),                     # ¿Por qué somos así?
}


def es_local(titulo: str, lugar: str, lugares) -> bool:
    """Decide si un evento de una productora curada es del Gran La Plata."""
    texto = f"{titulo} {lugar}"
    t = _sin_acentos(texto.lower())
    if any(x in t for x in EXCLUIR):
        return False
    if lugares is None or es_la_plata(texto):
        return True
    l = _sin_acentos((lugar or "").lower())
    return any(v in l for v in lugares)


MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
RE_FECHA = re.compile(
    r"(\d{1,2})\s+de\s+([A-Za-zñÑáéíóú]+)\s+(\d{4}).*?(\d{1,2}):(\d{2})", re.I | re.S
)


def _fecha(texto: str) -> str:
    """De '25 de Julio 2026 a las 21:00' arma 'YYYY-MM-DD HH:MM:SS'."""
    m = RE_FECHA.search(texto or "")
    if not m:
        return ""
    mes = MESES.get(m.group(2).lower())
    if not mes:
        return ""
    try:
        return f"{date(int(m.group(3)), mes, int(m.group(1))).isoformat()} " \
               f"{int(m.group(4)):02d}:{m.group(5)}:00"
    except ValueError:
        return ""


def _scrapear_productora(slug: str, categoria_def: str, lugares=None) -> list:
    eventos = []
    try:
        r = requests.get(BASE + slug, headers=HEADERS, timeout=25)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  passline/{slug}: error {e}")
        return eventos

    soup = BeautifulSoup(r.text, "html.parser")
    for li in soup.select("#grid li"):
        titulo_el = li.select_one("h3")
        if not titulo_el:
            continue
        titulo = titulo_el.get_text(" ", strip=True)

        cal = li.find("i", class_="icon-calendar")
        fecha = _fecha(cal.parent.get_text(" ", strip=True) if cal else "")
        if not es_futuro(fecha):
            continue

        loc = li.find("i", class_="icon-location")
        lugar = loc.parent.get_text(" ", strip=True) if loc else ""
        if not es_local(titulo, lugar, lugares):
            continue

        img = li.select_one("img")
        imagen = (img.get("src") or "").strip() if img else ""

        a = li.select_one('a[href*="/eventos/"]')
        url = a["href"].strip() if a and a.get("href") else ""

        eventos.append(evento(
            titulo,
            fecha,
            lugar or "La Plata",
            categoria=detectar_categoria(titulo, default=categoria_def),
            url=url,
            fuente="passline",
            imagen=imagen,
        ))
    return eventos


def scrape() -> list:
    eventos = []
    for slug, (categoria_def, lugares) in PRODUCTORAS.items():
        eventos.extend(_scrapear_productora(slug, categoria_def, lugares))
    print(f"  passline: {len(eventos)} eventos en La Plata")
    return eventos
