"""Plan B por sitemap: la puerta de atrás común a todas las fuentes.

Cuando el camino normal de un scraper devuelve cero, casi siempre queda una
segunda entrada: el sitemap. Es un solo pedido, lista las páginas de evento
una por una, y esas páginas suelen traer los datos en formato estándar
(schema.org/Event en un <script type="application/ld+json">), que es mejor
material que el HTML de la cartelera.

Tres funciones:

    urls_de_sitemap()  encuentra el sitemap y devuelve las URLs que importan
    evento_jsonld()    saca el evento del JSON-LD de una página
    recorrer()         pide las páginas de a una y arma la lista de eventos

Lo que aprendimos mirando las 12 fuentes (15/09/2026):

* El sitemap que declara robots.txt puede estar roto. Genda declara
  /genda/sitemap.php, que da 404, mientras /sitemap.xml anda perfecto. Por eso
  se prueba lo declarado Y las rutas de siempre.
* Vienen comprimidos (.gz) y anidados (un índice que apunta a otros sitemaps).
* lastmod sirve para no pedir 3.000 páginas: el Coliseo lista todas las
  actividades desde 2020, pero solo ~60 se tocaron en los últimos meses.
"""
import gzip
import json
import re
import time
from urllib.parse import urljoin, urlparse

import requests

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0'}
RUTAS_HABITUALES = ('/sitemap.xml', '/sitemap_index.xml', '/sitemap.xml.gz',
                    '/wp-sitemap.xml', '/sitemap-index.xml')
MAX_SITEMAPS_HIJOS = 12


def _pedir(url: str, timeout: int = 25):
    """Devuelve el texto de la URL, o None. Descomprime .gz si hace falta."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    crudo = r.content
    if crudo[:2] == b'\x1f\x8b':          # firma gzip
        try:
            crudo = gzip.decompress(crudo)
        except OSError:
            return None
    return crudo.decode('utf-8', 'replace')


def _declarados_en_robots(base: str) -> list:
    txt = _pedir(urljoin(base, '/robots.txt'), timeout=15)
    if not txt:
        return []
    return re.findall(r'(?im)^\s*Sitemap:\s*(\S+)', txt)


def _locs(xml: str) -> list:
    return [u.strip() for u in re.findall(r'<loc>\s*([^<]+?)\s*</loc>', xml)]


def _es_indice(xml: str) -> bool:
    return '<sitemapindex' in xml[:2000].lower()


def urls_de_sitemap(base: str, filtro=None, limite: int = 400,
                    dias_lastmod: int = 0, etiqueta: str = '') -> list:
    """Encuentra el sitemap de `base` y devuelve las URLs que pasan el filtro.

    filtro       texto que debe aparecer en la URL, o una función url -> bool.
    limite       techo de URLs a devolver (para no pedir miles de páginas).
    dias_lastmod si es > 0 y el sitemap trae <lastmod>, descarta las páginas
                 que no se tocaron en esos días. Es lo que hace manejable al
                 Coliseo, que lista 3.364 actividades desde 2020.
    """
    if callable(filtro):
        pasa = filtro
    elif filtro:
        pasa = lambda u: filtro in u          # noqa: E731
    else:
        pasa = lambda u: True                 # noqa: E731

    corte = ''
    if dias_lastmod > 0:
        from datetime import date, timedelta
        corte = (date.today() - timedelta(days=dias_lastmod)).isoformat()

    candidatos = _declarados_en_robots(base)
    candidatos += [urljoin(base, r) for r in RUTAS_HABITUALES]

    vistos, encontradas = set(), []
    for sm in candidatos:
        if sm in vistos:
            continue
        vistos.add(sm)
        xml = _pedir(sm)
        if not xml or '<loc>' not in xml:
            continue

        hojas = [sm]
        if _es_indice(xml):
            hojas = _locs(xml)[:MAX_SITEMAPS_HIJOS]

        for hoja in hojas:
            texto = xml if hoja == sm and not _es_indice(xml) else _pedir(hoja)
            if not texto:
                continue
            # Lo normal es <url><loc>..</loc><lastmod>..</lastmod></url>. Si la
            # fuente no envuelve en <url>, se cae a leer los <loc> sueltos.
            bloques = re.findall(r'<url>(.*?)</url>', texto, re.S)
            if not bloques:
                bloques = [f'<loc>{u}</loc>' for u in _locs(texto)]
            for bloque in bloques:
                m = re.search(r'<loc>\s*([^<]+?)\s*</loc>', bloque)
                if not m:
                    continue
                u = m.group(1).strip()
                if not pasa(u) or u in vistos:
                    continue
                if corte:
                    lm = re.search(r'<lastmod>\s*([^<]+?)\s*</lastmod>', bloque)
                    if not lm or lm.group(1)[:10] < corte:
                        continue
                vistos.add(u)
                encontradas.append(u)
                if len(encontradas) >= limite:
                    break
            if len(encontradas) >= limite:
                break
        if encontradas:
            break

    if etiqueta:
        origen = urlparse(base).netloc
        print(f'  {etiqueta}: sitemap de {origen} -> {len(encontradas)} paginas')
    return encontradas


def _objetos_jsonld(html_pagina: str):
    """Recorre todos los <script ld+json>, entrando a @graph y a las listas."""
    for bloque in re.findall(
            r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
            html_pagina, re.S | re.I):
        try:
            dato = json.loads(bloque.strip())
        except (ValueError, TypeError):
            continue
        pila = [dato]
        while pila:
            o = pila.pop()
            if isinstance(o, list):
                pila.extend(o)
            elif isinstance(o, dict):
                if '@graph' in o:
                    pila.append(o['@graph'])
                yield o


def _es_evento(obj: dict) -> bool:
    t = obj.get('@type', '')
    tipos = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.endswith('Event') for x in tipos)


def _texto_lugar(loc):
    """Del campo location saca (nombre, dirección). Acepta dict, lista o texto."""
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, str):
        return loc.strip(), ''
    if not isinstance(loc, dict):
        return '', ''
    nombre = (loc.get('name') or '').strip()
    dom = loc.get('address')
    if isinstance(dom, list):
        dom = dom[0] if dom else None
    if isinstance(dom, str):
        return nombre, dom.strip()
    if isinstance(dom, dict):
        partes = [dom.get('streetAddress'), dom.get('addressLocality')]
        return nombre, ', '.join(p.strip() for p in partes if p and p.strip())
    return nombre, ''


def _primera_imagen(img):
    while isinstance(img, list):
        img = img[0] if img else ''
    if isinstance(img, dict):
        img = img.get('url', '')
    return img if isinstance(img, str) else ''


def _fechas_iso(valor) -> list:
    """startDate puede venir suelto o como lista (Coliseo publica todas las
    funciones de una obra en un solo Event). Normaliza a 'YYYY-MM-DD HH:MM:00'."""
    crudos = valor if isinstance(valor, list) else [valor]
    salida = []
    for c in crudos:
        if not isinstance(c, str) or len(c) < 10:
            continue
        fecha, hora = c[:10], '21:00'
        m = re.search(r'[T ](\d{2}:\d{2})', c)
        if m:
            hora = m.group(1)
        if not re.match(r'\d{4}-\d{2}-\d{2}$', fecha):
            continue
        iso = f'{fecha} {hora}:00'
        if iso not in salida:
            salida.append(iso)
    return salida


def evento_jsonld(html_pagina: str) -> dict:
    """Saca el schema.org/Event de una página. {} si no hay.

    Devuelve las piezas crudas -- titulo, fechas (lista, porque una obra puede
    tener varias funciones en el mismo Event), lugar, direccion, imagen, url.
    Cada scraper decide categoría, fuente y qué fechas se queda.
    """
    for obj in _objetos_jsonld(html_pagina):
        if not _es_evento(obj):
            continue
        titulo = (obj.get('name') or '').strip()
        fechas = _fechas_iso(obj.get('startDate'))
        if not titulo or not fechas:
            continue
        lugar, direccion = _texto_lugar(obj.get('location'))
        return {
            'titulo': titulo,
            'fechas': fechas,
            'lugar': lugar,
            'direccion': direccion,
            'imagen': _primera_imagen(obj.get('image')),
            'descripcion': (obj.get('description') or '').strip(),
            'url': (obj.get('url') or '').strip(),
        }
    return {}


def recorrer(urls: list, parser, etiqueta: str = '', pausa: float = 0.3,
             max_fallos: int = 6) -> list:
    """Pide cada página y junta lo que devuelve parser(html, url).

    Si se caen varias páginas seguidas corta: la fuente se cayó del todo y no
    tiene sentido seguir golpeándola.
    """
    eventos, fallos = [], 0
    for u in urls:
        pagina = _pedir(u)
        if pagina is None:
            fallos += 1
            if fallos >= max_fallos:
                print(f'  {etiqueta}: demasiadas paginas caidas, se corta el plan B')
                break
            continue
        fallos = 0
        try:
            eventos.extend(parser(pagina, u) or [])
        except Exception as e:                       # noqa: BLE001
            print(f'  {etiqueta}: no se pudo parsear {u}: {e}')
        time.sleep(pausa)
    return eventos


# ---------------------------------------------------------------- fechas
MESES = {
    'enero': 1, 'ene': 1, 'febrero': 2, 'feb': 2, 'marzo': 3, 'mar': 3,
    'abril': 4, 'abr': 4, 'mayo': 5, 'may': 5, 'junio': 6, 'jun': 6,
    'julio': 7, 'jul': 7, 'agosto': 8, 'ago': 8, 'septiembre': 9,
    'setiembre': 9, 'sep': 9, 'set': 9, 'octubre': 10, 'oct': 10,
    'noviembre': 11, 'nov': 11, 'diciembre': 12, 'dic': 12,
}
DIAS_SEMANA = {'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
               'viernes': 4, 'sabado': 5, 'domingo': 6}

# "Domingo 12 de Mayo | 15:00"  /  "10 de Octubre de 2026 . 21:00 hs"
# La hora es obligatoria a propósito: sin ella entran frases como
# "venta en boletería a partir del 17 de febrero", que no son funciones.
PATRON_FECHA = re.compile(
    r'(?:(lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)s?\s+)?'
    r'(\d{1,2})\s+de\s+([a-zá-úñ]{3,10})\.?'
    r'(?:\s+de\s+(\d{4}))?'
    r'\s*[|.,\-–]?\s*'
    r'(\d{1,2})[:.](\d{2})',
    re.I)


def _sin_tildes(t: str) -> str:
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'),
                 ('ú', 'u'), ('ñ', 'n')):
        t = t.replace(a, b)
    return t


def _con_anio(dia, mes, hh, mm, nombre_dia, hoy):
    """Arma la fecha. Si la página no dice el año, lo deduce.

    Se prueban el año pasado, el actual y el que viene, y gana el que caiga
    en el día de la semana que dice la página y no haya quedado atrás. Si la
    fuente escribió mal el día de la semana, queda la primera fecha futura,
    que en una cartelera es lo más probable.
    """
    from datetime import datetime
    esperado = DIAS_SEMANA.get(_sin_tildes((nombre_dia or '').lower()))
    candidatas = []
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


def fechas_en_texto(texto: str, hoy=None, limite: int = 12) -> list:
    """Saca las funciones de un texto en castellano -> ['YYYY-MM-DD HH:MM:00'].

    Sirve para las fuentes que no publican schema.org/Event y escriben la
    fecha en prosa: el Coliseo ("Domingo 12 de Mayo | 15:00") y el Teatro
    Metro ("10 de Octubre de 2026 . 21:00 hs").
    """
    from datetime import date
    hoy = hoy or date.today()
    salida = []
    for nombre_dia, d, mes_txt, anio, hh, mm in PATRON_FECHA.findall(texto):
        mes = MESES.get(_sin_tildes(mes_txt.lower()))
        if not mes or int(hh) > 23 or int(mm) > 59:
            continue
        if anio:
            from datetime import datetime
            try:
                f = datetime(int(anio), mes, int(d), int(hh), int(mm))
            except ValueError:
                continue
            if f.date() < hoy:
                continue
        else:
            f = _con_anio(int(d), mes, int(hh), int(mm), nombre_dia, hoy)
        if not f:
            continue
        iso = f.strftime('%Y-%m-%d %H:%M:00')
        if iso not in salida:
            salida.append(iso)
        if len(salida) >= limite:
            break
    return salida


def texto_visible(html_pagina: str) -> str:
    """El texto de la página sin scripts ni menús, en una sola línea."""
    from bs4 import BeautifulSoup
    sopa = BeautifulSoup(html_pagina, 'html.parser')
    for t in sopa(['script', 'style', 'nav', 'footer', 'head']):
        t.decompose()
    return re.sub(r'\s+', ' ', sopa.get_text(' ', strip=True))


def meta_og(html_pagina: str) -> dict:
    """Los og: de la página -> {'title':.., 'description':.., 'image':..}."""
    import html as _html
    pares = re.findall(
        r'<meta[^>]+property=["\']og:(title|description|image)["\']'
        r'[^>]+content=["\']([^"\']*)["\']', html_pagina, re.I)
    return {k.lower(): _html.unescape(v).strip() for k, v in pares}
