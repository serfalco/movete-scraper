"""GENDA (agendalaplata.ar) — agenda cultural completa de La Plata.

Se recorre día por día (?fecha=YYYY-MM-DD) los próximos 14 días.

OJO con la URL: la agenda vivía en /genda/ y desde agosto de 2026 ese path
devuelve un 301 a la raíz. El redirect se come el ?fecha= (termina pidiendo
/%3Ffecha=...) y responde 200 con una página vacía, así que el scraper devolvía
cero sin ningún error visible. La agenda por día ahora se sirve desde la raíz.
"""
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from core.normalizar import detectar_categoria, evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
BASE = 'https://agendalaplata.ar/'
DIAS_A_SCRAPEAR = 14

PATRON_EVENTO = re.compile(r'(\d{1,2}):(\d{2})\s*hs\s*\|[ \t]*([^\n]{0,100})')
PATRON_HORA = re.compile(r'^\d{1,2}:\d{2}\s*hs')

# Solo elementos de interfaz (NO nombres de categorías de eventos)
PALABRAS_UI = {'cartelera', 'cómo llegar', 'como llegar', 'alerta',
               'invitalo/a', '¿con quién irías?', 'con quien irias',
               'sucediendo ahora', 'finalizadas', 'línea de tiempo',
               '▼', '‹', '›', '06h', '12h', '18h', '24h'}


def _mapear_categoria(cat_genda: str, titulo: str, venue: str = '') -> str:
    categoria = detectar_categoria(f'{cat_genda} {titulo}', default='otros')
    if categoria != 'otros':
        return categoria
    if 'actividad' in cat_genda.lower():
        return 'otros'
    return detectar_categoria(venue, default='otros')


def _imagen_card(card) -> str:
    """La miniatura viene como background-image en un estilo inline; se pasa a
    URL absoluta (../_fotos/x.jpg -> https://agendalaplata.ar/_fotos/x.jpg)."""
    el = card.select_one('[style*="background-image"]')
    if not el:
        return ''
    m = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", el.get('style', ''))
    if not m:
        return ''
    return urljoin(BASE, m.group(1).strip())


def _parsear_tarjetas(soup: BeautifulSoup, fecha_dia: date) -> list:
    eventos = []
    for card in soup.select('.card.card-custom'):
        link_datos = card.select_one('[data-title][data-sitio]')
        if not link_datos:
            continue

        titulo = (link_datos.get('data-title') or '').strip()
        venue = (link_datos.get('data-sitio') or '').strip()
        texto_card = card.get_text(' ', strip=True)
        hora_match = re.search(r'\b(\d{1,2}):(\d{2})\s*hs\b', texto_card)
        if not titulo or not hora_match:
            continue

        hora = f'{int(hora_match.group(1)):02d}:{hora_match.group(2)}'
        etiquetas = ' '.join(
            badge.get_text(' ', strip=True)
            for badge in card.select('.evento-tabs .badge')
        )
        url_match = re.search(
            r'https://agendalaplata\.ar/evento/[^\'"\s]+',
            str(card),
        )

        eventos.append(evento(
            titulo,
            f'{fecha_dia.isoformat()} {hora}:00',
            venue or 'La Plata',
            categoria=_mapear_categoria(etiquetas, titulo, venue),
            url=url_match.group(0) if url_match else '',
            fuente='genda',
            imagen=_imagen_card(card),
        ))
    return eventos


def _parsear_dia(html: str, fecha_dia: date) -> list:
    eventos = []
    soup = BeautifulSoup(html, 'html.parser')
    eventos = _parsear_tarjetas(soup, fecha_dia)
    if eventos:
        return eventos

    # Respaldo para una version antigua o simplificada del HTML de la fuente.
    texto = soup.get_text('\n')
    texto = re.sub(r'(\d{1,2}:\d{2}\s*hs)\s*\|\s*', r'\1 | ', texto)

    for m in PATRON_EVENTO.finditer(texto):
        hora = f'{int(m.group(1)):02d}:{m.group(2)}'
        venue = m.group(3).strip()
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
        if '????' in titulo:
            continue
        eventos.append(evento(
            titulo, f'{fecha_dia.isoformat()} {hora}:00',
            venue or 'La Plata',
            categoria=_mapear_categoria(cat_genda, titulo, venue),
            fuente='genda'))
    return eventos


# Genda aguanta mal las rafagas desde un runner de GitHub: se cayo entera en
# las corridas del 27/08 y 03/09 de 2026 y volvio sola el 10/09, sin que el
# codigo cambiara. Como es ~58% de la cartelera, conviene insistir antes de
# darla por muerta: cada dia se reintenta con espera creciente.
REINTENTOS = 3
ESPERA_REINTENTO = (2, 5)  # segundos antes del 2do y del 3er intento


def _pedir_dia(dia):
    """Devuelve el HTML del dia, o None si no se pudo despues de reintentar."""
    for intento in range(REINTENTOS):
        try:
            r = requests.get(BASE, params={'fecha': dia.isoformat()},
                             headers=HEADERS, timeout=25)
            if r.status_code == 200:
                return r.text
            print(f'  genda/{dia}: HTTP {r.status_code}'
                  f'{" (reintento)" if intento + 1 < REINTENTOS else ""}')
        except requests.RequestException as e:
            print(f'  genda/{dia}: error {e}'
                  f'{" (reintento)" if intento + 1 < REINTENTOS else ""}')
        if intento + 1 < REINTENTOS:
            time.sleep(ESPERA_REINTENTO[intento])
    return None


def scrape() -> list:
    eventos = []
    hoy = date.today()
    fallos_consecutivos = 0
    for offset in range(DIAS_A_SCRAPEAR):
        dia = hoy + timedelta(days=offset)
        html = _pedir_dia(dia)
        if html is None:
            fallos_consecutivos += 1
            # Antes cortaba a los 2 dias fallados seguidos. Con reintentos,
            # 2 dias caidos ya son 6 pedidos fallados: si aguanta hasta 4,
            # un bache corto no se lleva puesta la semana entera.
            if fallos_consecutivos >= 4:
                print('  genda: fuente inaccesible; se corta el intento diario')
                break
        else:
            fallos_consecutivos = 0
            eventos.extend(_parsear_dia(html, dia))
        time.sleep(0.5)
    if not eventos:
        print('  genda: la fuente respondió pero no se parseó ningún evento; '
              f'revisar el HTML de {BASE} y los selectores de _parsear_tarjetas')
    print(f'  genda: {len(eventos)} eventos en {DIAS_A_SCRAPEAR} días')
    return eventos
