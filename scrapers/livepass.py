"""Livepass — Ópera, Teatro Argentino, Hipódromo, Atenas LP."""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, ajustar_anio, es_futuro, detectar_categoria

VENUES = {
    'opera': ('Teatro Ópera La Plata', 'Calle 58 entre 10 y 11, La Plata'),
    'teatro-argentino': ('Teatro Argentino La Plata', 'Av. 51 entre 9 y 10, La Plata'),
    'hipodromo-la-plata': ('Hipódromo de La Plata', 'Av. 44 y 115, La Plata'),
}

MES_ABREV = {'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
             'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12}

# Si el título dice "en <otra ciudad>", el evento no es en La Plata
CIUDADES_AJENAS = [
    'lanus', 'lanús', 'villa ballester', 'bahia blanca', 'bahía blanca',
    'quilmes', 'rosario', 'cordoba', 'córdoba', 'mendoza', 'mar del plata',
    'buenos aires', 'caba', 'avellaneda', 'banfield', 'san miguel',
    'monte grande', 'ituzaingo', 'ituzaingó', 'tandil', 'olavarria',
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}


def _limpiar_titulo(titulo: str):
    """Saca el sufijo ' en <lugar>' y descarta si es otra ciudad."""
    m = re.search(r'\sen\s+(.+)$', titulo, re.I)
    if m:
        lugar = m.group(1).lower()
        for ciudad in CIUDADES_AJENAS:
            if ciudad in lugar:
                return None  # evento de gira en otra ciudad
        titulo = titulo[:m.start()].strip()
    return titulo


def _parsear_pagina(html: str, venue_nombre: str, venue_dir: str) -> list:
    eventos = []
    soup = BeautifulSoup(html, 'html.parser')

    for h in soup.find_all(['h1', 'h2', 'h3']):
        titulo_crudo = h.get_text(' ', strip=True).lstrip('#').strip()
        if len(titulo_crudo) < 4 or len(titulo_crudo) > 120:
            continue
        titulo = _limpiar_titulo(titulo_crudo)
        if not titulo or len(titulo) < 3:
            continue
        pos = str(soup).find(str(h))
        contexto = str(soup)[max(0, pos - 400):pos]
        m = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)',
                      contexto, re.I)
        if not m:
            continue
        fecha = ajustar_anio(MES_ABREV[m.group(2).upper()], int(m.group(1)))
        if not es_futuro(fecha):
            continue
        categoria = detectar_categoria(titulo, default='musica')
        eventos.append(evento(titulo, fecha, venue_nombre, categoria=categoria,
                              direccion=venue_dir, fuente='livepass'))
    return eventos


def scrape() -> list:
    eventos = []
    for slug, (nombre, direccion) in VENUES.items():
        try:
            r = requests.get(f'https://livepass.com.ar/t/{slug}',
                             headers=HEADERS, timeout=25)
            if r.status_code != 200:
                print(f'  livepass/{slug}: HTTP {r.status_code}')
                continue
            evs = _parsear_pagina(r.text, nombre, direccion)
            print(f'  livepass/{slug}: {len(evs)} eventos')
            eventos.extend(evs)
        except requests.RequestException as e:
            print(f'  livepass/{slug}: error {e}')

    # Atenas LP — desde la home, filtrando por título
    try:
        r = requests.get('https://livepass.com.ar/', headers=HEADERS, timeout=25)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            evs = []
            for h in soup.find_all(['h1', 'h2', 'h3']):
                t = h.get_text(' ', strip=True)
                if not re.search(r'atenas\s+lp', t, re.I):
                    continue
                pos = str(soup).find(str(h))
                contexto = str(soup)[max(0, pos - 400):pos]
                m = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)',
                              contexto, re.I)
                if not m:
                    continue
                fecha = ajustar_anio(MES_ABREV[m.group(2).upper()], int(m.group(1)))
                if not es_futuro(fecha):
                    continue
                titulo = re.sub(r'\sen\s+estadio\s+atenas.*$', '', t, flags=re.I).strip()
                evs.append(evento(titulo, fecha, 'Estadio Atenas La Plata',
                                  categoria=detectar_categoria(titulo, default='musica'),
                                  direccion='Av. 13, La Plata', fuente='livepass'))
            print(f'  livepass/atenas: {len(evs)} eventos')
            eventos.extend(evs)
    except requests.RequestException as e:
        print(f'  livepass/home: error {e}')

    return eventos
