"""Teatro Ópera La Plata — agenda WordPress (operalp.com.ar).

Cada evento de la agenda es un contenedor .item con título, fecha DD/MM/YYYY,
imagen (flyer) y link de compra. Se parsea eso: más robusto que buscar la
fecha en el texto suelto, y ahora trae imagen.
"""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import detectar_categoria, es_futuro, evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
URL = 'https://operalp.com.ar/agenda/'
DIRECCION = 'Calle 58 entre 10 y 11, La Plata'
RE_FECHA = re.compile(r'(\d{2})/(\d{2})/(\d{4})')


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
    for item in soup.select('.item'):
        h2 = item.find('h2')
        if not h2:
            continue
        titulo = re.sub(r'\s+en el Teatro [ÓO]pera.*$', '', h2.get_text(' ', strip=True), flags=re.I)
        if len(titulo) < 4:
            continue

        m = RE_FECHA.search(item.get_text(' '))
        if not m:
            continue
        fecha = f'{m.group(3)}-{m.group(2)}-{m.group(1)} 21:00:00'
        if not es_futuro(fecha):
            continue

        img = item.select_one('img')
        imagen = (img.get('src') or img.get('data-src') or img.get('data-lazy-src') or '').strip() if img else ''
        a = item.find('a', href=True)
        url = a['href'] if a else ''

        eventos.append(evento(
            titulo, fecha, 'Teatro Ópera La Plata',
            categoria=detectar_categoria(titulo, default='musica'),
            direccion=DIRECCION, url=url, fuente='opera', imagen=imagen,
        ))

    # Dedup por título + día.
    vistos, unicos = set(), []
    for ev in eventos:
        k = ev['titulo'].lower() + ev['fecha'][:10]
        if k not in vistos:
            vistos.add(k)
            unicos.append(ev)
    print(f'  opera: {len(unicos)} eventos')
    return unicos
