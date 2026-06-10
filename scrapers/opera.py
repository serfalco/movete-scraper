"""Teatro Ópera La Plata — agenda WordPress con fechas DD/MM/YYYY."""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, es_futuro

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
URL = 'https://operalp.com.ar/agenda/'


def scrape() -> list:
    eventos = []
    try:
        r = requests.get(URL, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f'  opera: HTTP {r.status_code}')
            return []
    except requests.RequestException as e:
        print(f'  opera: error {e}')
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    for h in soup.find_all('h2'):
        titulo = h.get_text(' ', strip=True)
        # Limpiar sufijo "en el Teatro Ópera LP"
        titulo = re.sub(r'\s+en el Teatro [ÓO]pera.*$', '', titulo, flags=re.I)
        if len(titulo) < 4:
            continue
        contexto = ''
        for sib in h.find_all_next(string=True, limit=15):
            contexto += ' ' + sib
            if len(contexto) > 400:
                break
        m = re.search(r'(\d{2})/(\d{2})/(\d{4})', contexto)
        if not m:
            continue
        fecha = f'{m.group(3)}-{m.group(2)}-{m.group(1)} 21:00:00'
        if not es_futuro(fecha):
            continue
        eventos.append(evento(
            titulo, fecha, 'Teatro Ópera La Plata',
            direccion='Calle 58 entre 10 y 11, La Plata', fuente='opera'))
    print(f'  opera: {len(eventos)} eventos')
    return eventos
