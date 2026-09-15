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


def _sin_tildes(t: str) -> str:
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u')):
        t = t.replace(a, b)
    return t


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
    lugar, direccion = _canonizar(datos['lugar'], datos['direccion'])
    categoria = detectar_categoria(titulo, default='')
    if not categoria:
        categoria = detectar_categoria(
            f"{titulo} {datos['descripcion']}", default='musica')

    eventos = []
    for fecha in datos['fechas']:
        if not es_futuro(fecha):
            continue
        eventos.append(evento(
            titulo, fecha, lugar or 'La Plata',
            categoria=categoria,
            direccion=direccion, url=datos['url'] or url,
            fuente='livepass', imagen=datos['imagen']))
    return eventos


# Nombres de sala que delatan La Plata en la propia URL del evento. Sirven
# para no entrar a las páginas que seguro no son de acá: de las ~179 que lista
# el sitemap, el 80% son de Buenos Aires (Café Berlín, CCNU, San Miguel) y la
# URL ya lo dice —'...-en-cafe-berlin' contra '...-en-el-teatro-opera-lp'.
# Medido el 15/09/2026: 33 pedidos en vez de 179, con los mismos 33 eventos.
# 'estadio-uno', 'hirschi' y 'estadio-unico' salieron de correr el barrido
# completo y mirar qué se le escapaba al prefiltro: el estadio de Estudiantes
# se llama "Jorge Luis Hirschi" en la ficha pero en la URL figura como
# 'tan-bionica-en-estadio-uno'. Ese es el punto débil del atajo —una sala con
# nombre propio que no esté en esta lista pasa de largo— y por eso el plan B,
# cuando la fuente se cae, barre las 179 sin filtrar.
PISTAS_LA_PLATA = ('la-plata', '-lp', 'opera', 'teatro-argentino', 'hipodromo',
                   'atenas', 'guajira', 'ginastera', 'hirschi', 'estadio-uno',
                   'estadio-unico', 'ciudad-de-la-plata')


# El JSON-LD escribe los nombres a su manera y sin tildes: "Teatro Opera La
# Plata", "Hipodromo de La Plata", "Teatro Argentino Centro Provincial de las
# Artes". Si quedan así, la misma sala aparece con dos nombres distintos en la
# revista segun de que camino vino el evento. Se unifican con los nombres y
# direcciones que ya tenia VENUES.
CANONICAS = (
    ('opera', 'opera'),
    ('argentino', 'teatro-argentino'),
    ('ginastera', 'teatro-argentino'),
    ('hipodromo', 'hipodromo-la-plata'),
)


def _canonizar(lugar: str, direccion: str):
    """Pasa el nombre del JSON-LD al nombre de siempre de esa sala."""
    l = _sin_tildes(lugar.lower())
    for pista, slug in CANONICAS:
        if pista in l:
            return VENUES[slug]
    return lugar, direccion


def _tiene_pista(url: str) -> bool:
    u = url.lower()
    return '/events/' in u and any(p in u for p in PISTAS_LA_PLATA)


def _scrape_sitemap(completo: bool = False) -> list:
    """Recorre las páginas de evento del sitemap.

    completo=False (el modo de todas las semanas) entra solo a las URLs que
    nombran una sala platense. Es barato y no se pierde nada de lo que hoy
    sabemos mirar.

    completo=True es para cuando el camino normal se cayó: ahí el costo ya no
    importa y conviene mirar las 179, porque el prefiltro se apoya en una
    lista de nombres y una sala nueva no estaría en ella.
    """
    filtro = '/events/' if completo else _tiene_pista
    urls = urls_de_sitemap('https://livepass.com.ar/', filtro=filtro,
                           limite=400, etiqueta='livepass')
    if not urls:
        print('  livepass: el sitemap tampoco responde')
        return []
    eventos = recorrer(urls, _evento_de_pagina, etiqueta='livepass', pausa=0.2)
    modo = 'barrido completo' if completo else 'prefiltrado por URL'
    print(f'  livepass: sitemap ({modo}) trajo {len(eventos)} eventos '
          f'en La Plata desde {len(urls)} paginas')
    return eventos



def _clave_titulo(t: str) -> str:
    return re.sub(r'[^a-z0-9]', '', _sin_tildes(t.lower()))


def _fusionar(de_venues: list, de_sitemap: list) -> list:
    """Junta los dos caminos sin repetir el mismo show.

    Las tarjetas del HTML de Livepass cortan los títulos largos con '...'
    ("ROMPIENDO ESPEJOS - Tributo a Callej ...") mientras el JSON-LD los da
    enteros ("... a Callejeros"). Como deduplicar() en main.py compara el
    título entero, los veía distintos y el mismo show salía dos veces en la
    revista. Acá gana el del sitemap, que además trae url e imagen.
    """
    por_dia = {}
    for ev in de_sitemap:
        por_dia.setdefault((ev['fecha'][:10], ev['lugar'].lower()), []).append(ev)

    salida = []
    for ev in de_venues:
        recorte = re.sub(r'\s*(\.\.\.|…)\s*$', '', ev['titulo']).strip()
        clave = _clave_titulo(recorte)
        gemelos = por_dia.get((ev['fecha'][:10], ev['lugar'].lower()), [])
        if len(clave) >= 10 and any(
                _clave_titulo(g['titulo']).startswith(clave) for g in gemelos):
            continue
        salida.append(ev)
    return salida + de_sitemap


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
        return _scrape_sitemap(completo=True)

    # Con el camino normal sano, el sitemap igual se suma: las tres páginas de
    # venue no miran Guajira ni la Sala Ginastera del Argentino, y el sitemap
    # sí. Los repetidos los junta deduplicar() en main.py, que además completa
    # imagen y link.
    antes = len(eventos)
    eventos = _fusionar(eventos, _scrape_sitemap())
    print(f'  livepass: {len(eventos)} eventos '
          f'({antes} de las paginas de venue antes de fusionar)')
    return eventos
