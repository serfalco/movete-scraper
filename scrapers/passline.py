"""Passline — ticketera, sobre todo música/recitales.

Passline no lista por ciudad: se organiza por 'productora'. Se scrapea una lista
curada de productoras que son salas platenses (empezando por Espacio Live). Cada
página de productora trae sus eventos ya con fecha, lugar, imagen y link de compra.

Para sumar una sala nueva: agregar su slug de productora a PRODUCTORAS.
"""
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from core.normalizar import es_futuro, es_la_plata, detectar_categoria, evento

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}
BASE = "https://www.passline.com/productora/"

# Productoras de Passline que son salas del Gran La Plata. slug -> categoría por
# defecto (la sala define el tono; las palabras clave del título mandan igual).
PRODUCTORAS = {
    "live-club-la-plata": "musica",   # Espacio Live
}

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


def _scrapear_productora(slug: str, categoria_def: str) -> list:
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
        # Curada como platense, pero si el evento nombra otra ciudad, afuera.
        if lugar and not es_la_plata(lugar):
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
    for slug, categoria_def in PRODUCTORAS.items():
        eventos.extend(_scrapear_productora(slug, categoria_def))
    print(f"  passline: {len(eventos)} eventos en La Plata")
    return eventos
