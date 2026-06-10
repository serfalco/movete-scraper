"""Teatro Coliseo Podestá — cartelera oficial municipal (Drupal)."""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, ajustar_anio, es_futuro, MESES

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
URL = 'https://coliseopodesta.laplata.gob.ar/cartelera'

CAT_SLUGS = {
    'stand': 'stand-up', 'recital': 'musica', 'infantil': 'infantil',
    'comedia': 'teatro', 'teatro': 'teatro', 'danza': 'danza',
    'musica': 'musica', 'opera': 'musica',
}


def scrape() -> list:
    eventos = []
    try:
        r = requests.get(URL, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f'  coliseo: HTTP {r.status_code}')
            return []
    except requests.RequestException as e:
        print(f'  coliseo: error {e}')
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    for a in soup.find_all('a', href=re.compile(r'actividad')):
        titulo = a.get('title', '') or a.get_text(' ', strip=True)
        titulo = titulo.strip()
        if len(titulo) < 3 or len(titulo) > 120:
            continue

        # Buscar fecha "4 de Mayo" + hora "| 20:30" cerca del link
        pos = str(soup).find(str(a))
        contexto = str(soup)[pos:pos + 800]
        m = re.search(r'(\d{1,2})\s+de\s+(\w+)', contexto, re.I)
        h = re.search(r'\|\s*(\d{1,2}:\d{2})', contexto)
        if not m:
            continue
        mes = MESES.get(m.group(2).lower())
        if not mes:
            continue
        hora = h.group(1) if h else '20:00'
        fecha = ajustar_anio(mes, int(m.group(1)), hora)
        if not es_futuro(fecha):
            continue

        href = a.get('href', '')
        categoria = ''
        for kw, slug in CAT_SLUGS.items():
            if kw in href.lower():
                categoria = slug
                break

        url_full = href if href.startswith('http') else f'https://coliseopodesta.laplata.gob.ar{href}'
        eventos.append(evento(
            titulo, fecha, 'Teatro Coliseo Podestá',
            categoria=categoria,
            direccion='Calle 10 entre 46 y 47, La Plata',
            url=url_full, fuente='coliseo'))

    # Dedup local (el mismo evento aparece varias veces en la página)
    vistos = set()
    unicos = []
    for ev in eventos:
        k = ev['titulo'].lower() + ev['fecha'][:10]
        if k not in vistos:
            vistos.add(k)
            unicos.append(ev)
    print(f'  coliseo: {len(unicos)} eventos')
    return unicos
