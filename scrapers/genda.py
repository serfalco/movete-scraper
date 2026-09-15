"""GENDA (agendalaplata.ar) — agenda cultural completa de La Plata.

Se recorre día por día (?fecha=YYYY-MM-DD) los próximos 30 días. Si ese
camino no devuelve nada, se entra por la puerta de atrás: el sitemap.xml
lista todas las páginas de evento y cada una trae lugar, fecha y hora en sus
meta tags. Ver _scrape_sitemap().

OJO con la URL: la agenda vivía en /genda/ y desde agosto de 2026 ese path
devuelve un 301 a la raíz. El redirect se come el ?fecha= (termina pidiendo
/%3Ffecha=...) y responde 200 con una página vacía, así que el scraper devolvía
cero sin ningún error visible. La agenda por día ahora se sirve desde la raíz.
"""
import html as _html
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from core.normalizar import detectar_categoria, evento

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
BASE = 'https://agendalaplata.ar/'
# 30 y no 14: la caché de respaldo guarda exactamente lo que se scrapea, así
# que con 14 días, dos semanas de caída la vaciaban del todo. Fue lo que pasó
# en agosto de 2026. Con 30 días una caída de dos semanas pasa sin que se note.
DIAS_A_SCRAPEAR = 30

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


def _pedir(url, params=None, etiqueta=''):
    """Devuelve el HTML/XML, o None si no se pudo despues de reintentar."""
    etiqueta = etiqueta or url
    for intento in range(REINTENTOS):
        queda = intento + 1 < REINTENTOS
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=25)
            if r.status_code == 200:
                return r.text
            print(f'  genda/{etiqueta}: HTTP {r.status_code}'
                  f'{" (reintento)" if queda else ""}')
        except requests.RequestException as e:
            print(f'  genda/{etiqueta}: error {e}{" (reintento)" if queda else ""}')
        if queda:
            time.sleep(ESPERA_REINTENTO[intento])
    return None


def _pedir_dia(dia):
    return _pedir(BASE, params={'fecha': dia.isoformat()}, etiqueta=str(dia))



# --- Plan B: entrar por el sitemap --------------------------------------
# El camino normal depende de que ?fecha= siga funcionando. Ya nos rompió una
# vez (el 301 de /genda/) y en agosto de 2026 Genda devolvió cero dos semanas
# seguidas. El sitemap es otra puerta a la misma casa: un solo pedido lista
# todas las páginas de evento, y cada una trae lugar, fecha y hora en sus meta
# tags, con este formato:
#
#   og:title       = Pez
#   og:description = Casa Suiza  - Viernes 11 de septiembre (21:00 hs)
#   og:image       = https://agendalaplata.ar/_fotos/20260805211832.jpg
#
# Encima trae url e imagen, que el camino por día no da. El robots.txt de
# Genda es Allow: / y publica el sitemap, así que esto es uso previsto.
SITEMAP = urljoin(BASE, 'sitemap.xml')

# Tope de páginas a pedir. Es un plan B: no vale la pena tardar diez minutos.
MAX_PAGINAS_SITEMAP = 200

MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5,
         'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9,
         'octubre': 10, 'noviembre': 11, 'diciembre': 12}

DIAS_SEMANA = {'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
               'viernes': 4, 'sabado': 5, 'domingo': 6}

# "Casa Suiza  - Viernes 11 de septiembre (21:00 hs) | Sábado 12 ... (20:00 hs)"
# El lugar se separa con DOS espacios + guion, y el nombre del lugar puede
# tener su propio " - " adentro ("Teatro Argentino - Centro Provincial de las
# Artes"), por eso además se exige que después venga un día de la semana.
PATRON_CORTE = re.compile(
    r'\s\s+-\s+(?=(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\b)',
    re.I)
PATRON_FUNCION = re.compile(
    r'(lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\s+'
    r'(\d{1,2})\s+de\s+([a-zá-ú]+)\s*\((\d{1,2}):(\d{2})',
    re.I)
PATRON_META = re.compile(
    r'<meta\s+property="og:(title|description|image)"\s+content="([^"]*)"', re.I)


def _sin_tildes(t: str) -> str:
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u')):
        t = t.replace(a, b)
    return t


def _resolver_anio(dia: int, mes: int, hh: int, mm: int, nombre_dia: str, hoy: date):
    """La página no dice el año. Lo deduce del día de la semana.

    Se prueban el año pasado, el actual y el que viene: la combinación
    correcta es la que cae en el día de la semana que dice la página y no
    quedó atrás. Si ninguna coincide (Genda escribió mal el día), se cae en
    la primera fecha futura, que es lo más probable en una agenda.
    """
    esperado = DIAS_SEMANA.get(_sin_tildes(nombre_dia.lower()))
    candidatas = []
    from datetime import datetime
    for anio in (hoy.year - 1, hoy.year, hoy.year + 1):
        try:
            f = datetime(anio, mes, dia, hh, mm)
        except ValueError:
            continue
        if f.date() < hoy:
            continue
        candidatas.append(f)
    if not candidatas:
        return None
    if esperado is not None:
        for f in candidatas:
            if f.weekday() == esperado:
                return f
    return candidatas[0]


def _parsear_evento(html_pagina: str, url: str, hoy: date) -> list:
    metas = {k.lower(): _html.unescape(v).strip()
             for k, v in PATRON_META.findall(html_pagina)}
    titulo = metas.get('title', '')
    desc = metas.get('description', '')
    if not titulo or not desc:
        return []

    partes = PATRON_CORTE.split(desc, maxsplit=1)
    if len(partes) == 2:
        venue, cola = partes[0].strip(), partes[1]
    else:
        # Sin lugar: la descripción arranca directo con "- Jueves 05 de ..."
        venue, cola = '', desc.lstrip(' -')

    imagen = metas.get('image', '')
    eventos = []
    for nombre_dia, d, mes_txt, hh, mm in PATRON_FUNCION.findall(cola):
        mes = MESES.get(_sin_tildes(mes_txt.lower()))
        if not mes:
            continue
        f = _resolver_anio(int(d), mes, int(hh), int(mm), nombre_dia, hoy)
        if not f:
            continue
        eventos.append(evento(
            titulo, f.strftime('%Y-%m-%d %H:%M:00'),
            venue or 'La Plata',
            categoria=_mapear_categoria('', titulo, venue),
            url=url, imagen=imagen, fuente='genda'))
    return eventos


def _scrape_sitemap() -> list:
    """Plan B: sacar los eventos de las páginas sueltas listadas en el sitemap."""
    xml = _pedir(SITEMAP)
    if xml is None:
        print('  genda: el sitemap tampoco responde')
        return []
    urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', xml) if '/evento/' in u]
    if not urls:
        print('  genda: el sitemap no lista paginas de evento')
        return []
    urls = urls[:MAX_PAGINAS_SITEMAP]
    print(f'  genda: plan B, {len(urls)} paginas de evento desde el sitemap')

    hoy = date.today()
    limite = hoy + timedelta(days=DIAS_A_SCRAPEAR)
    eventos, fallos = [], 0
    for u in urls:
        pagina = _pedir(u)
        if pagina is None:
            fallos += 1
            if fallos >= 6:
                print('  genda: demasiadas paginas caidas, se corta el plan B')
                break
            continue
        fallos = 0
        for ev in _parsear_evento(pagina, u, hoy):
            if ev['fecha'][:10] <= limite.isoformat():
                eventos.append(ev)
        time.sleep(0.3)
    print(f'  genda: plan B recupero {len(eventos)} eventos')
    return eventos

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
        print('  genda: la agenda por dia no devolvio nada; '
              f'revisar el HTML de {BASE} y los selectores de _parsear_tarjetas')
        eventos = _scrape_sitemap()
    print(f'  genda: {len(eventos)} eventos en {DIAS_A_SCRAPEAR} días')
    return eventos
