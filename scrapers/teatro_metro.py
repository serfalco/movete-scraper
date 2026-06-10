"""Teatro Metro La Plata — cartelera con fechas DD/MM/YYYY - HH:MM hs."""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, es_futuro

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
PAGINAS = [
    'https://www.teatrometrolp.com.ar/entradas/cartelera/',
    'https://www.teatrometrolp.com.ar/entradas/cartelera/1/',
]


def scrape() -> list:
    eventos = []
    for url in PAGINAS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code != 200:
                continue
        except requests.RequestException:
            continue

        soup = BeautifulSoup(r.text, 'html.parser')
        for h in soup.find_all('h3'):
            titulo = h.get_text(' ', strip=True)
            if len(titulo) < 3:
                continue
            # Buscar fecha "08/05/2026 - 19:00" en los siguientes elementos
            contexto = ''
            for sib in h.find_all_next(string=True, limit=20):
                contexto += ' ' + sib
                if len(contexto) > 500:
                    break
            m = re.search(r'(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{1,2}:\d{2})', contexto)
            if not m:
                continue
            fecha = f'{m.group(3)}-{m.group(2)}-{m.group(1)} {m.group(4)}:00'
            if not es_futuro(fecha):
                continue
            eventos.append(evento(
                titulo, fecha, 'Teatro Metro La Plata',
                direccion='Calle 4 entre 51 y 53, La Plata', fuente='teatro-metro'))
    print(f'  teatro-metro: {len(eventos)} eventos')
    return eventos
