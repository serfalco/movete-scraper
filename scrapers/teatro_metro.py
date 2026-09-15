"""Teatro Metro La Plata — cartelera con fechas DD/MM/YYYY - HH:MM hs.

Si la cartelera no devuelve nada, se entra por el sitemap: lista las páginas
de /entrada/ y cada una escribe la función en prosa ("10 de Octubre de 2026 .
21:00 hs"). Es la única de las fuentes con plan B que no publica
schema.org/Event, así que la fecha se saca del texto.
"""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import detectar_categoria, evento, es_futuro
from core.sitemap import (fechas_en_texto, meta_og, recorrer, texto_visible,
                          urls_de_sitemap)

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
PAGINAS = [
    'https://www.teatrometrolp.com.ar/entradas/cartelera/',
    'https://www.teatrometrolp.com.ar/entradas/cartelera/1/',
]
SITIO = 'https://www.teatrometrolp.com.ar/'
DIRECCION = 'Calle 4 entre 51 y 53, La Plata'
# El sitemap mezcla las fichas de show con páginas institucionales
# (/entrada/sobre-nosotros-18313/). Las de show terminan en un id de 5-6
# dígitos sin barra final.
PATRON_FICHA = re.compile(r'/entrada/[^/]+-\d{5,6}/?$')


def _es_ficha(url: str) -> bool:
    return bool(PATRON_FICHA.search(url))


def _ficha_de_pagina(html_pagina: str, url: str) -> list:
    og = meta_og(html_pagina)
    titulo = og.get('title', '').strip()
    if not titulo or len(titulo) < 3:
        return []
    # Solo el cuerpo: el pie repite el horario de boletería ("calle 53 de
    # lunes a sábados de 10.00 a 20.00"), que no es una función.
    texto = texto_visible(html_pagina)
    texto = re.split(r'boleter[íi]a', texto, maxsplit=1, flags=re.I)[0]

    eventos = []
    for fecha in fechas_en_texto(texto, limite=6):
        if not es_futuro(fecha):
            continue
        eventos.append(evento(
            titulo, fecha, 'Teatro Metro La Plata',
            categoria=detectar_categoria(titulo, default='teatro'),
            direccion=DIRECCION, url=url, fuente='teatro-metro',
            imagen=og.get('image', '')))
    return eventos


def _scrape_sitemap() -> list:
    urls = urls_de_sitemap(SITIO, filtro=_es_ficha, limite=120,
                           etiqueta='teatro-metro')
    if not urls:
        print('  teatro-metro: el sitemap tampoco responde')
        return []
    eventos = recorrer(urls, _ficha_de_pagina, etiqueta='teatro-metro',
                       pausa=0.2)
    print(f'  teatro-metro: plan B recupero {len(eventos)} eventos')
    return eventos


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
                categoria=detectar_categoria(titulo, default='teatro'),
                direccion=DIRECCION, fuente='teatro-metro'))

    # Acá el sitemap no es solo plan B: se suma siempre. La cartelera pagina
    # de a poco (devuelve ~6 shows) mientras el sitemap lista los ~40 que el
    # teatro tiene publicados, y son 42 páginas, un costo chico. Los repetidos
    # los junta deduplicar() en main.py, que además completa imagen y link.
    antes = len(eventos)
    eventos.extend(_scrape_sitemap())
    if antes and len(eventos) == antes:
        print('  teatro-metro: el sitemap no agrego nada')
    print(f'  teatro-metro: {len(eventos)} eventos ({antes} de la cartelera)')
    return eventos
