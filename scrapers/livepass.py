"""Livepass — Ópera, Teatro Argentino, Hipódromo, CCNU, Club RE, Atenas LP."""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, ajustar_anio, es_futuro, MESES

VENUES = {
    'opera': ('Teatro Ópera La Plata', 'Calle 58 entre 10 y 11, La Plata'),
    'teatro-argentino': ('Teatro Argentino La Plata', 'Av. 51 entre 9 y 10, La Plata'),
    'hipodromo-la-plata': ('Hipódromo de La Plata', 'Av. 44 y 115, La Plata'),
    'centro-cultural-nueva-uriarte': ('CCNU', 'La Plata'),
    'club-re': ('Club RE La Plata', 'La Plata'),
}

MES_ABREV = {'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
             'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12}

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}


def _parsear_pagina(html: str, venue_nombre: str, venue_dir: str) -> list:
    eventos = []
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text(' ', strip=False)

    # Buscar pares fecha + título: "08 MAY" cerca de un heading
    for h in soup.find_all(['h1', 'h2', 'h3']):
        titulo = h.get_text(' ', strip=True).lstrip('#').strip()
        if len(titulo) < 4 or len(titulo) > 120:
            continue
        # Buscar fecha en los 300 caracteres anteriores al heading en el HTML
        pos = str(soup).find(str(h))
        contexto = str(soup)[max(0, pos - 400):pos]
        m = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)',
                      contexto, re.I)
        if not m:
            continue
        fecha = ajustar_anio(MES_ABREV[m.group(2).upper()], int(m.group(1)))
        if not es_futuro(fecha):
            continue
        eventos.append(evento(titulo, fecha, venue_nombre,
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
            evs = _parsear_pagina(r.text, 'Estadio Atenas La Plata', 'Av. 13, La Plata')
            evs = [e for e in evs if re.search(r'atenas\s+lp', e['titulo'], re.I)]
            print(f'  livepass/atenas: {len(evs)} eventos')
            eventos.extend(evs)
    except requests.RequestException as e:
        print(f'  livepass/home: error {e}')

    return eventos
