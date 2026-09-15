"""Livepass — Ópera, Teatro Argentino, Hipódromo, Atenas LP."""
import re

import requests
from bs4 import BeautifulSoup

from core.normalizar import (evento, ajustar_anio, es_futuro, detectar_categoria,
                             es_la_plata)
from core.sitemap import urls_de_sitemap, evento_jsonld, recorrer

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


# --------------------------------------------------------------- plan B
# El camino normal mira tres páginas de venue (/t/opera, /t/teatro-argentino,
# /t/hipodromo-la-plata) y saca la fecha de un contexto de 400 caracteres
# alrededor del título: si Livepass cambia el maquetado, devuelve cero sin
# error. El sitemap lista las ~170 páginas de evento y cada una publica un
# schema.org/Event completo, así que el plan B trae mejor material que el
# camino normal —y además cubre salas que la lista de tres no mira: Guajira,
# la Sala Ginastera del Argentino.
#
# Livepass vende en todo el país, así que hay que filtrar: el 80% de esas
# páginas son de Café Berlín y otras salas porteñas.


def _evento_de_pagina(html_pagina: str, url: str) -> list:
    datos = evento_jsonld(html_pagina)
    if not datos:
        return []
    contexto = f"{datos['lugar']} {datos['direccion']} {datos['titulo']}"
    if not es_la_plata(contexto):
        return []

    titulo = _limpiar_titulo(datos['titulo']) or datos['titulo']
    categoria = detectar_categoria(titulo, default='')
    if not categoria:
        categoria = detectar_categoria(
            f"{titulo} {datos['descripcion']}", default='musica')

    eventos = []
    for fecha in datos['fechas']:
        if not es_futuro(fecha):
            continue
        eventos.append(evento(
            titulo, fecha, datos['lugar'] or 'La Plata',
            categoria=categoria,
            direccion=datos['direccion'], url=datos['url'] or url,
            fuente='livepass', imagen=datos['imagen']))
    return eventos


def _scrape_sitemap() -> list:
    urls = urls_de_sitemap('https://livepass.com.ar/', filtro='/events/',
                           limite=400, etiqueta='livepass')
    if not urls:
        print('  livepass: el sitemap tampoco responde')
        return []
    eventos = recorrer(urls, _evento_de_pagina, etiqueta='livepass', pausa=0.2)
    print(f'  livepass: plan B recupero {len(eventos)} eventos en La Plata')
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

    if not eventos:
        print('  livepass: las paginas de venue no devolvieron nada; '
              'se entra por el sitemap')
        eventos = _scrape_sitemap()
    return eventos
