"""Teatro Cerca — cartelera de teatro de zona sur, filtrada a La Plata.

teatrocerca.com.ar publica una página por localidad (/localidad/la-plata) y
cada función tiene su propia URL (/obra/<obra>/funcion/la-plata/<lugar>/<fecha>)
con un Event JSON-LD completo: título, fecha y hora, lugar, dirección e imagen.

El listado general trae solo una parte de la cartelera, así que se recorren
también los filtros por categoría (independiente, comercial, standup) y
se juntan las URLs de función sin repetir. (Kids vive en otro subdominio y
el filtro ?categoria=kids no filtra: no se usa.) La categoría sale del filtro en el
que apareció la función. Las obras las cargan los propios teatros, por eso la
semana ya está casi completa desde el lunes.
"""
import re
import time

import requests

from core.normalizar import es_futuro, evento
from core.sitemap import evento_jsonld

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
SITIO = 'https://teatrocerca.com.ar'
LISTADO = SITIO + '/localidad/la-plata'
MAX_FUNCIONES = 250  # tope defensivo

# filtro de la página -> categoría de MoVeTe ('' = el listado general)
FILTROS = {
    '': 'teatro',
    'independiente': 'teatro',
    'comercial': 'teatro',
    'standup': 'stand-up',
}
# Si una función aparece en varios filtros manda el más específico.
PRIORIDAD = ['standup', 'independiente', 'comercial', '']

RE_FUNCION = re.compile(
    r'https://teatrocerca\.com\.ar/obra/[^"\'\s<>]+/funcion/la-plata/[^"\'\s<>]+')


def _pedir(url: str, params=None):
    for intento in range(2):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=25)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if intento == 1:
                print(f'  teatrocerca: error en {url}: {e}')
            time.sleep(1)
    return None


def urls_de_funciones(html_listado: str) -> list:
    """URLs de función de La Plata que aparecen en un listado, sin repetir."""
    return sorted(set(RE_FUNCION.findall(html_listado)))


def _describir(html: str) -> str:
    """Qué devolvió una página sin funciones, para diagnosticar desde el log."""
    t = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
    titulo = re.sub(r'\s+', ' ', t.group(1)).strip()[:80] if t else 'sin <title>'
    return f'{len(html)} bytes, titulo: {titulo!r}'


def _recolectar() -> dict:
    """{url_de_funcion: categoria}, uniendo el listado general y los filtros."""
    categoria_de: dict = {}
    mejor: dict = {}
    for filtro, categoria in FILTROS.items():
        html = _pedir(LISTADO, {'categoria': filtro} if filtro else None)
        if not html:
            continue
        if not filtro and not urls_de_funciones(html):
            print(f'  teatrocerca: listado sin funciones ({_describir(html)})')
        for u in urls_de_funciones(html):
            rango = PRIORIDAD.index(filtro)
            if u not in mejor or rango < mejor[u]:
                mejor[u] = rango
                categoria_de[u] = categoria
        time.sleep(0.3)
    return categoria_de


def parsear_funcion(html_pagina: str, url: str, categoria: str = 'teatro') -> list:
    """Evento de una página de función. [] si no tiene fecha futura."""
    d = evento_jsonld(html_pagina)
    if not d:
        return []
    salida = []
    for fecha in d['fechas']:
        if not es_futuro(fecha):
            continue
        salida.append(evento(
            d['titulo'], fecha, d['lugar'] or 'La Plata',
            categoria=categoria, direccion=d['direccion'],
            url=d['url'] or url, fuente='teatrocerca', imagen=d['imagen'],
        ))
    return salida


def scrape(espera_reintento: float = 45) -> list:
    funciones = _recolectar()
    if not funciones:
        # El 19/11/2026 el listado respondió 200 sin ninguna función y a las
        # pocas horas andaba bien: se le da una segunda oportunidad antes de
        # caer al respaldo.
        print(f'  teatrocerca: listado vacío, se reintenta en {espera_reintento:.0f} s')
        time.sleep(espera_reintento)
        funciones = _recolectar()
    if not funciones:
        print('  teatrocerca: el listado de La Plata no devolvio funciones')
        return []

    eventos, fallos = [], 0
    for url, categoria in list(funciones.items())[:MAX_FUNCIONES]:
        html = _pedir(url)
        if html is None:
            fallos += 1
            if fallos >= 6:
                print('  teatrocerca: demasiadas paginas caidas, se corta')
                break
            continue
        fallos = 0
        try:
            eventos.extend(parsear_funcion(html, url, categoria))
        except Exception as e:  # noqa: BLE001
            print(f'  teatrocerca: no se pudo parsear {url}: {e}')
        time.sleep(0.3)

    print(f'  teatrocerca: {len(eventos)} funciones de {len(funciones)} paginas')
    return eventos
