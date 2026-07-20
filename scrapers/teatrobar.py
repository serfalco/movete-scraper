"""El Teatro Bar (La Plata) — agenda Drupal, paginada por mes.

La agenda (/agenda-eventos?month=YYYY-MM) es server-rendered: cada evento trae
título, día, hora e imagen; el mes y el año salen del parámetro de la URL. Se
recorren varios meses hacia adelante para levantar toda la agenda publicada.
"""
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from core.normalizar import detectar_categoria, es_futuro, evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
BASE = 'https://www.elteatrobar.com.ar'
AGENDA = BASE + '/agenda-eventos'
MESES_ADELANTE = 6
DIRECCION = 'Calle 43 N° 632 e/ 7 y 8, La Plata'
# Del texto "Sábado 04 21:00 hs." saca día (04) y hora (21:00).
RE_DIA_HORA = re.compile(r'(\d{1,2})\D+?(\d{1,2}):(\d{2})')


def _meses(n: int):
    """Genera 'YYYY-MM' desde el mes actual, n meses hacia adelante."""
    hoy = date.today()
    y, m = hoy.year, hoy.month
    for _ in range(n):
        yield f'{y:04d}-{m:02d}'
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _scrapear_mes(ym: str) -> list:
    eventos = []
    try:
        r = requests.get(AGENDA, params={'month': ym}, headers=HEADERS, timeout=25)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f'  teatrobar/{ym}: error {e}')
        return eventos

    soup = BeautifulSoup(r.text, 'html.parser')
    anio, mes = ym.split('-')
    for h3 in soup.select('h3.artistaAgenda'):
        titulo = h3.get_text(' ', strip=True)
        if not titulo:
            continue
        cont = h3.find_parent('div', class_='col-md-4') or h3.parent
        resto = cont.get_text(' ', strip=True).replace(titulo, '', 1)
        m = RE_DIA_HORA.search(resto)
        if not m:
            continue
        hora = f'{int(m.group(2)):02d}:{m.group(3)}'
        try:
            fecha = f'{date(int(anio), int(mes), int(m.group(1))).isoformat()} {hora}:00'
        except ValueError:
            continue
        if not es_futuro(fecha):
            continue

        img = cont.select_one('img')
        imagen = (img.get('src') or '').strip() if img else ''
        a = h3.find('a')
        url = (a.get('href') if a else '') or ''
        if url.startswith('/'):
            url = BASE + url

        eventos.append(evento(
            titulo, fecha, 'El Teatro Bar',
            categoria=detectar_categoria(titulo, default='musica'),
            direccion=DIRECCION, url=url, fuente='teatrobar', imagen=imagen,
        ))
    return eventos


def scrape() -> list:
    eventos = []
    for ym in _meses(MESES_ADELANTE):
        eventos.extend(_scrapear_mes(ym))
    print(f'  teatrobar: {len(eventos)} eventos')
    return eventos
