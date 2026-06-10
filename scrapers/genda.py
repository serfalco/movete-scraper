"""GENDA (agendalaplata.ar) — agenda cultural completa de La Plata.

Se recorre día por día (?fecha=YYYY-MM-DD) los próximos 14 días.
El servidor devuelve todos los eventos del día en el HTML.
"""
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from core.normalizar import evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
BASE = 'https://agendalaplata.ar/genda/'
DIAS_A_SCRAPEAR = 14

# "21:00 hs |  Venue"  (el venue puede faltar)
PATRON_EVENTO = re.compile(r'(\d{1,2}):(\d{2})\s*hs\s*\|[ \t]*([^\n]{0,100})')
PATRON_HORA = re.compile(r'^\d{1,2}:\d{2}\s*hs')

# Categorías GENDA → MoVeTe, en orden de prioridad
# (las compuestas como "Teatro Stand Up" matchean lo más específico primero)
PRIORIDAD_CATS = [
    ('stand up', 'stand-up'), ('standup', 'stand-up'), ('humor', 'stand-up'),
    ('impro', 'impro'),
    ('danza', 'danza'),
    ('infantil', 'infantil'), ('títeres', 'infantil'), ('titeres', 'infantil'),
    ('cine', 'cine'),
    ('exposicion', 'a-plasticas'), ('exposición', 'a-plasticas'),
    ('muestra', 'a-plasticas'), ('feria', 'a-plasticas'),
    ('taller', 'taller'),
    ('musica', 'musica'), ('música', 'musica'), ('en vivo', 'musica'),
    ('peña', 'musica'), ('pena', 'musica'),
    ('teatro', 'teatro'),
]

# Aperturas permanentes que se repiten todos los días → ruido
CATS_EXCLUIDAS = ('museo', 'visita', 'recreativo')

PALABRAS_UI = {'cartelera', 'cómo llegar', 'como llegar', 'alerta',
               'invitalo/a', '¿con quién irías?', 'con quien irias',
               'sucediendo ahora', 'finalizadas', 'línea de tiempo',
               'cine', 'teatro', 'música', 'musica', 'infantil', '▼', '‹', '›'}


def _mapear_categoria(cat_genda: str, titulo: str) -> str:
    texto = f'{cat_genda} {titulo}'.lower()
    for kw, slug in PRIORIDAD_CATS:
        if kw in texto:
            return slug
    return 'teatro'


def _parsear_dia(html: str, fecha_dia: date) -> list:
    eventos = []
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text('\n')
    # Unir "HH:MM hs" + "|" + venue aunque queden en líneas separadas
    texto = re.sub(r'(\d{1,2}:\d{2}\s*hs)\s*\|\s*', r'\1 | ', texto)

    for m in PATRON_EVENTO.finditer(texto):
        hora = f'{int(m.group(1)):02d}:{m.group(2)}'
        venue = m.group(3).strip()
        # Si lo capturado como venue es en realidad otra hora → no hay venue
        if PATRON_HORA.match(venue):
            venue = ''

        contexto_previo = texto[max(0, m.start() - 400):m.start()]
        previas = [l.strip() for l in contexto_previo.split('\n')
                   if l.strip()
                   and not PATRON_HORA.match(l.strip())
                   and l.strip().lower() not in PALABRAS_UI]
        if not previas:
            continue
        titulo = previas[-1]
        cat_genda = previas[-2] if len(previas) >= 2 else ''

        if len(titulo) < 3 or len(titulo) > 120:
            continue
        if titulo.lower() == venue.lower():
            continue
        cat_lower = cat_genda.lower()
        if any(x in cat_lower for x in CATS_EXCLUIDAS):
            continue

        eventos.append(evento(
            titulo, f'{fecha_dia.isoformat()} {hora}:00',
            venue or 'La Plata',
            categoria=_mapear_categoria(cat_genda, titulo),
            fuente='genda'))
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
            if offset == 0 and not evs:
                total = len(re.findall(r'\d{1,2}:\d{2}\s*hs', r.text))
                print(f'  genda DEBUG: 0 eventos pero {total} horas en el HTML del {dia}')
        except requests.RequestException as e:
            print(f'  genda/{dia}: error {e}')
        time.sleep(0.5)
    print(f'  genda: {len(eventos)} eventos en {DIAS_A_SCRAPEAR} días')
    return eventos
