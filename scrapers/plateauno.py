"""PlateaUno (plateaunotickets.com) — ticketera regional.

Fuente PROPIA (ticketera), para no depender solo de agendalaplata. La cartelera
es server-rendered y cubre muchas ciudades; se filtran los eventos de La Plata
(la sala trae el prefijo 'LaPlata'). Trae imagen y link de compra.
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from core.normalizar import (ajustar_anio, detectar_categoria, es_futuro,
                             es_la_plata, evento)
from core.sitemap import urls_de_sitemap, evento_jsonld, recorrer

BASE = "https://www.plateaunotickets.com/"
CARTELERA = BASE + "cartelera.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}

MESES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}
RE_FECHA = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})\b.*?(\d{1,2}):(\d{2})", re.S)


def _fecha(texto: str) -> str:
    """De '20 JUL LUNES | 15:00hs' arma 'YYYY-MM-DD HH:MM:SS' (año asumido)."""
    m = RE_FECHA.search(texto or "")
    if not m:
        return ""
    mes = MESES.get(m.group(2).upper())
    if not mes:
        return ""
    hora = f"{int(m.group(3)):02d}:{m.group(4)}"
    return ajustar_anio(mes, int(m.group(1)), hora)


def _de_la_plata(texto: str) -> bool:
    # La sala viene como 'LaPlata Metro' (sin espacio en el prefijo).
    return "laplata" in texto.lower().replace(" ", "")


def _limpiar_sala(sala: str) -> str:
    return re.sub(r"^la\s*plata\s+", "", sala, flags=re.I).strip() or sala


# --------------------------------------------------------------- plan B
# cartelera.php es una sola página: si cambia el HTML o deja de responder, no
# queda nada. El sitemap (viene comprimido, .gz) lista las ~65 páginas de obra
# y cada una publica un schema.org/Event con dirección de la sala incluida,
# que es justo el dato que la cartelera no da.


def _obra_de_pagina(html_pagina: str, url: str) -> list:
    datos = evento_jsonld(html_pagina)
    if not datos:
        return []
    contexto = f"{datos['lugar']} {datos['direccion']}"
    if not (_de_la_plata(contexto) or es_la_plata(contexto)):
        return []

    sala = _limpiar_sala(datos['lugar']) or "La Plata"
    default_cat = "infantil" if "metro" in sala.lower() else "otros"
    # El título manda. Si no alcanza (el Metro cae por default en 'infantil',
    # y un homenaje sinfónico no es infantil), se mira la descripción, que el
    # camino normal no tiene: solo la publica el JSON-LD de la ficha.
    categoria = detectar_categoria(datos['titulo'], default="")
    if not categoria:
        categoria = detectar_categoria(
            f"{datos['titulo']} {datos['descripcion']}", default=default_cat)

    eventos = []
    for fecha in datos['fechas']:
        if not es_futuro(fecha):
            continue
        eventos.append(evento(
            datos['titulo'], fecha, sala,
            categoria=categoria,
            direccion=datos['direccion'], url=datos['url'] or url,
            fuente="plateauno", imagen=datos['imagen']))
    return eventos


def _scrape_sitemap() -> list:
    urls = urls_de_sitemap(BASE, filtro="/obra/", limite=300,
                           etiqueta="plateauno")
    if not urls:
        print("  plateauno: el sitemap tampoco responde")
        return []
    eventos = recorrer(urls, _obra_de_pagina, etiqueta="plateauno", pausa=0.2)
    print(f"  plateauno: plan B recupero {len(eventos)} eventos en La Plata")
    return eventos


def scrape() -> list:
    eventos = []
    try:
        r = requests.get(CARTELERA, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        # Que la cartelera esté caída es justo el caso para el que existe el
        # plan B: no hay que salir por acá, hay que entrar por el sitemap.
        print(f"  plateauno: error {e}")
        return _scrape_sitemap()

    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select(".event-card"):
        titulo_el = card.select_one(".card-title")
        if not titulo_el:
            continue
        titulo = titulo_el.get_text(" ", strip=True)

        b = card.select_one(".card-details b")
        badge = card.select_one(".card-badge")
        sala = (b.get_text(" ", strip=True) if b
                else badge.get_text(" ", strip=True) if badge else "")
        # Multi-ciudad: solo La Plata.
        if not _de_la_plata(f"{sala} {badge.get_text() if badge else ''}"):
            continue

        detalles = card.select_one(".card-details")
        fecha = _fecha(detalles.get_text(" ", strip=True) if detalles else "")
        if not es_futuro(fecha):
            continue

        img = card.select_one("img.card-img-top") or card.select_one("img")
        imagen = (img.get("src") or "").strip() if img else ""

        a = card.select_one('a[href*="/obra"]') or card.select_one("a[href]")
        url = urljoin(BASE, a["href"]) if a and a.get("href") else ""

        sala_limpia = _limpiar_sala(sala) or "La Plata"
        # La cartelera no trae categoría. El Teatro Metro es sala familiar, así
        # que sus shows sin palabra clave se asumen infantiles (las palabras
        # explícitas —música, teatro, etc.— igual mandan sobre este default).
        default_cat = "infantil" if "metro" in sala_limpia.lower() else "otros"

        eventos.append(evento(
            titulo,
            fecha,
            sala_limpia,
            categoria=detectar_categoria(titulo, default=default_cat),
            url=url,
            fuente="plateauno",
            imagen=imagen,
        ))

    if not eventos:
        print("  plateauno: la cartelera no devolvio nada; se entra por el sitemap")
        eventos = _scrape_sitemap()
    print(f"  plateauno: {len(eventos)} eventos en La Plata")
    return eventos
