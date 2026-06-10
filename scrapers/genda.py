"""GENDA (agendalaplata.ar) — agenda cultural completa de La Plata.

Tratamiento especial: se recorre día por día (?fecha=YYYY-MM-DD)
los próximos 14 días.
"""
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento, detectar_categoria

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
BASE = 'https://agendalaplata.ar/genda/'
DIAS_A_SCRAPEAR = 14

PATRON_COMPLETO = re.compile(r'^(\d{1,2}):(\d{2})\s*hs\s*\|\s*(.{3,100})$')
PATRON_SOLO_HORA = re.compile(r'^(\d{1,2}):(\d{2})\s*hs\.?$')

CATS_GENDA = {
    'cine': 'cine', 'teatro': 'teatro',
    'musica': 'musica', 'música': 'musica',
    'infantil': 'infantil',
    'exposicion': 'a-plasticas', 'exposición': 'a-plasticas',
    'muestra': 'a-plasticas', 'feria': 'a-plasticas',
    'danza': 'danza',
    'stand up': 'stand-up', 'standup': 'stand-up', 'humor': 'stand-up',
    'impro': 'impro', 'taller': 'taller',
}

CATS_EXCLUIDAS = {'museo', 'visita', 'visita guiada'}


def _parsear_dia(html: str, fecha_dia: date) -> list:
    eventos = []
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text('\n')
    # Unir "HH:MM hs" + "|" + "Venue" cuando quedan en líneas separadas
    texto = re.sub(r'(\d{1,2}:\d{2}\s*hs)\s*\n?\s*\|\s*\n?\s*', r'\1 | ', texto)
    lineas = [l.strip() for l in texto.split('\n')]

    for i, linea in enumerate(lineas):
        m = PATRON_COMPLETO.match(linea)
        if not m:
            continue
        hora = f'{int(m.group(1)):02d}:{m.group(2)}'
        venue = m.group(3).strip()

        # Título = línea previa no vacía que no sea hora ni venue repetido
        previas = [l for l in lineas[max(0, i - 6):i]
                   if l and not PATRON_COMPLETO.match(l)
                   and not PATRON_SOLO_HORA.match(l)]
        if not previas:
            continue
        titulo = previas[-1]
        cat_genda = previas[-2].lower().strip() if len(previas) >= 2 else ''

        if len(titulo) < 3 or titulo.lower() == venue.lower():
            continue
        if cat_genda in CATS_EXCLUIDAS:
            continue

        categoria = CATS_GENDA.get(cat_genda) or detectar_categoria(
            f'{cat_genda} {titulo}', default='teatro')

        eventos.append(evento(
            titulo, f'{fecha_dia.isoformat()} {hora}:00', venue,
            categoria=categoria, fuente='genda'))
    return eventos


def scrape() -> list:
    eventos = []
    hoy = date.today()
    for offset in range(DIAS_A_SCRAPEAR):
        dia = hoy + timedelta(days=offset)
        try:
            r = requests.get(BASE, params={'fecha': dia.isoformat()},
                             headers=HEADERS, timeout=25)
            if r.status_code != 200:
                print(f'  genda/{dia}: HTTP {r.status_code}')
                continue
            evs = _parsear_dia(r.text, dia)
            eventos.extend(evs)
            # Debug del primer día si no encontró nada
            if offset == 0 and not evs:
                soup = BeautifulSoup(r.text, 'html.parser')
                muestra = re.sub(r'\n+', ' / ', soup.get_text('\n'))[:600]
                print(f'  genda DEBUG (0 eventos el {dia}): {muestra}')
        except requests.RequestException as e:
            print(f'  genda/{dia}: error {e}')
        time.sleep(0.5)
    print(f'  genda: {len(eventos)} eventos en {DIAS_A_SCRAPEAR} días')
    return eventos
