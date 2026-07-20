"""PlateaUno (plateaunotickets.com) — ticketera regional.

Fuente PROPIA (ticketera), para no depender solo de agendalaplata. La cartelera
es server-rendered y cubre muchas ciudades; se filtran los eventos de La Plata
(la sala trae el prefijo 'LaPlata'). Trae imagen y link de compra.
"""
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from core.normalizar import ajustar_anio, detectar_categoria, es_futuro, evento

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


def scrape() -> list:
    eventos = []
    try:
        r = requests.get(CARTELERA, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  plateauno: error {e}")
        return eventos

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

    print(f"  plateauno: {len(eventos)} eventos en La Plata")
    return eventos
