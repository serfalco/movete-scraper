"""Normalización de eventos: fechas, categorías, deduplicación, filtro geográfico."""
from datetime import datetime, date, timedelta
import difflib
import hashlib
import html as _html
import re
import unicodedata

LOCALIDADES = [
    'la plata', 'laplata', 'ensenada', 'berisso', 'city bell',
    'gonnet', 'villa elisa', 'los hornos', 'tolosa', 'ringuelet',
    'brandsen', 'magdalena', 'punta indio',
]

EXCLUIR = [
    'buenos aires', 'caba', 'cordoba', 'rosario', 'mendoza',
    'quilmes', 'lanus', 'banfield', 'avellaneda', 'wilde',
    'san miguel', 'monte grande', 'ituzaingo', 'villa ballester',
    'palermo', 'belgrano', 'san telmo', 'recoleta',
]

MESES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}

# El orden importa: primero van las categorias mas especificas. Las expresiones
# usan limites de palabra para evitar coincidencias accidentales dentro de nombres.
REGLAS_CATEGORIA = [
    ('stand-up', (r'\bstand[ -]?up\b', r'\bopen mic\b')),
    ('impro', (r'\bimpro(?:visacion)?\b', r'\bmatch\b.*\bteatro deporte\b')),
    ('taller', (r'\btaller(?:es)?\b', r'\bworkshop\b', r'\bcurso\b',
                r'\bseminario\b', r'\bclinica\b', r'\bcapacitacion\b')),
    ('infantil', (r'\binfantil(?:es)?\b', r'\binfancias?\b', r'\bninos?\b',
                  r'\bbajitos\b', r'\btiteres\b')),
    ('danza', (r'\bdanza\b', r'\bballet\b', r'\bcoreograf')),
    ('a-plasticas', (r'\bexposicion\b', r'\bexpo\b', r'\bmuestra\b',
                     r'\bpintura\b', r'\bfotografia\b', r'\bescultura\b',
                     r'\bdibujo\b', r'\bmosaiquismo\b', r'\bartes? visual')),
    ('cine', (r'\bcine\b', r'\bfilm\b', r'\bpelicula\b', r'\bpantalla grande\b')),
    ('musica', (r'\bmusica\b', r'\brecital\b', r'\bconcierto\b', r'\bjazz\b',
                r'\btango\b', r'\brock\b', r'\bcumbia\b', r'\borquesta\b',
                r'\bbanda\b', r'\bacustic', r'\bpena\b')),
    ('humor', (r'\bhumor\b', r'\bhumorista\b')),
    ('teatro', (r'\bteatro\b', r'\bobra\b', r'\bdramaturg', r'\bclown',
                r'\bunipersonal\b', r'\bcomedia\b')),
]


def _sin_acentos(texto: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def es_la_plata(texto: str) -> bool:
    """True si el texto refiere al Gran La Plata y no a otra ciudad."""
    t = _sin_acentos(texto.lower())
    for x in EXCLUIR:
        if x in t:
            return False
    for loc in LOCALIDADES:
        if loc in t:
            return True
    return False


def detectar_categoria(texto: str, default: str = 'otros') -> str:
    t = _sin_acentos(texto.lower())
    for slug, patrones in REGLAS_CATEGORIA:
        if any(re.search(patron, t) for patron in patrones):
            return slug
    return default


def ajustar_anio(mes: int, dia: int, hora: str = '21:00') -> str:
    """Arma fecha YYYY-MM-DD HH:MM:SS asumiendo el próximo año si el mes ya pasó."""
    hoy = date.today()
    anio = hoy.year
    try:
        candidata = date(anio, mes, dia)
    except ValueError:
        return ''
    if candidata < hoy - timedelta(days=2):
        candidata = date(anio + 1, mes, dia)
    return f'{candidata.isoformat()} {hora}:00'


def es_futuro(fecha: str) -> bool:
    if not fecha:
        return False
    try:
        dt = datetime.strptime(fecha[:10], '%Y-%m-%d').date()
        return dt >= date.today()
    except ValueError:
        return False


def limpiar_titulo(titulo: str) -> str:
    # Algunas fuentes entregan el título con entidades HTML sin convertir
    # ("Camerata Rosario presenta &apos;Las 8 Estaciones&apos;"). Se hace dos
    # veces porque hay fuentes que escapan dos veces (&amp;apos;).
    t = _html.unescape(_html.unescape(titulo))
    t = re.sub(r'\s+', ' ', t).strip()
    # Las tarjetas cortan los títulos largos; los puntos suspensivos no son
    # parte del nombre del show y hacen que el mismo evento parezca dos.
    t = re.sub(r'\s*(\.\.\.|…)\s*$', '', t).strip()
    t = t.strip('·-– ')
    # Las comillas se sacan solo de a pares: si no, un título como
    # «Camerata presenta 'Las 8 Estaciones'» quedaba con la comilla de
    # apertura suelta y la de cierre comida.
    COMILLAS = '"\'“”‘’'
    while len(t) > 2 and t[0] in COMILLAS and t[-1] in COMILLAS:
        t = t[1:-1].strip('·-– ')
    return t[:120]


def _clave_titulo(titulo: str) -> str:
    return re.sub(r'[^a-z0-9]', '', _sin_acentos(titulo.lower()))


# Umbrales del segundo paso.
#
# La pista que de verdad separa un repetido de dos obras distintas NO es el
# parecido del título: es la sala y el horario. Medido sobre la cartelera real
# del 15/09/2026, los 13 repetidos estaban TODOS en la misma sala.
#
# Y una sala no puede tener dos cosas a la vez: si coinciden sala y hora, es
# el mismo evento aunque los títulos se parezcan poco ("Cuadriláteros 6"
# contra "Cuadriláteros 6, teatro breve reunido" da 0.61).
#
# Si la hora NO coincide hay que ser mucho más duro, porque ahí sí conviven
# cosas distintas: "Taller de teatro para adultos" y "Taller de teatro para
# niños", el mismo día en la misma sala a horas distintas, dan 0.83 y son dos
# talleres, no uno.
#
# Si alguna vez falta un show de la cartelera y se sospecha que se fusionó con
# otro, estos son los números que hay que subir. Vale más un repetido —que se
# ve— que un show que desaparece sin que nadie se entere.
MIN_LARGO_PARECIDO = 12
MIN_PARECIDO_MISMA_FUNCION = 0.72
MIN_PARECIDO_SUELTO = 0.90

ROMANOS = {'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'}


def _es_secuela(cola: str) -> bool:
    """True si lo único que agrega el título más largo es un número de parte.

    "Los juegos del hambre" y "Los juegos del hambre 2" son dos películas
    distintas y no hay que juntarlas. En cambio "NEW SENSATION" y "NEW
    SENSATION 2026" son el mismo show: un año es la edición, no la parte.
    """
    if not cola:
        return False
    if cola in ROMANOS:
        return True
    if cola.isdigit():
        return not (1900 <= int(cola) <= 2100)
    return False


def _clave_lugar(lugar: str) -> str:
    return re.sub(r'[^a-z0-9]', '', _sin_acentos(lugar.lower()))


def _misma_sala(a: str, b: str) -> bool:
    """Cada fuente escribe la sala a su manera: 'Teatro Metro', 'Teatro Metro
    La Plata', 'Metro'. Alcanza con que una esté contenida en la otra."""
    ka, kb = _clave_lugar(a), _clave_lugar(b)
    if len(ka) < 4 or len(kb) < 4:
        return False
    return ka in kb or kb in ka


def _mismo_evento(uno: dict, otro: dict) -> bool:
    """Decide si dos eventos del mismo día son en realidad el mismo show.

    Cada fuente lo escribe a su manera:

        Historias innecesarias - Damián Kuc     (genda)
        Historias Innecesarias En Vivo.         (teatro metro)
        HISTORIAS INNECESARIAS                  (plateauno)

    Se pide siempre la misma sala. Si además coincide la hora, alcanza con
    que los títulos se parezcan. Si la hora no coincide, se exige un parecido
    muy alto.
    """
    a = _clave_titulo(uno['titulo'])
    b = _clave_titulo(otro['titulo'])
    corto, largo = sorted((a, b), key=len)
    if len(corto) < MIN_LARGO_PARECIDO:
        return False
    if not _misma_sala(uno['lugar'], otro['lugar']):
        return False
    if largo.startswith(corto) and _es_secuela(largo[len(corto):]):
        return False

    misma_hora = uno['fecha'][11:16] == otro['fecha'][11:16]
    if misma_hora and largo.startswith(corto):
        return True
    parecido = difflib.SequenceMatcher(None, a, b).ratio()
    return parecido >= (MIN_PARECIDO_MISMA_FUNCION if misma_hora
                        else MIN_PARECIDO_SUELTO)


def _completar(base: dict, otro: dict) -> None:
    """Un duplicado puede traer datos que al primero le faltan."""
    for campo in ('imagen', 'url', 'direccion'):
        if not base.get(campo) and otro.get(campo):
            base[campo] = otro[campo]
    # Si el título que guardamos es el comienzo del otro, el otro lo dice
    # entero: "EL ESCRITOR DE TODAS LAS" contra "EL ESCRITOR DE TODAS LAS
    # COSAS". Gana el completo.
    kb, ko = _clave_titulo(base['titulo']), _clave_titulo(otro['titulo'])
    if kb != ko and ko.startswith(kb):
        base['titulo'] = otro['titulo']


def deduplicar(eventos: list) -> list:
    """Junta el mismo evento aunque cada fuente lo nombre distinto.

    Dos pasos. El primero es exacto (mismo título normalizado + mismo día) y
    es el que resuelve la mayoría. El segundo mira, dentro de cada día, los
    títulos que se parecen mucho: sin él la misma obra salía hasta tres veces
    en la revista, una por fuente.
    """
    vistos = {}
    resultado = []
    for ev in eventos:
        clave = hashlib.md5(
            (_clave_titulo(ev['titulo']) + ev['fecha'][:10]).encode()
        ).hexdigest()
        if clave not in vistos:
            vistos[clave] = ev
            resultado.append(ev)
        else:
            _completar(vistos[clave], ev)

    # Segundo paso, día por día. Se conserva el primero que entró: el orden
    # de las fuentes en main.py pone primero a las que mejor escriben.
    por_dia = {}
    for ev in resultado:
        por_dia.setdefault(ev['fecha'][:10], []).append(ev)

    absorbidos = set()
    for _dia, del_dia in por_dia.items():
        # Se arma por contagio: si A es el mismo que B y B el mismo que C,
        # los tres son el mismo show aunque A y C no se parezcan entre sí.
        # Pasa de verdad: "New sensation - Tributo INXS" y "NEW SENSATION
        # 2026" solo se tocan a través de "NEW SENSATION".
        grupo = list(range(len(del_dia)))

        def raiz(i, _g=grupo):
            while _g[i] != i:
                _g[i] = _g[_g[i]]
                i = _g[i]
            return i

        for i in range(len(del_dia)):
            for j in range(i + 1, len(del_dia)):
                if raiz(i) != raiz(j) and _mismo_evento(del_dia[i], del_dia[j]):
                    grupo[raiz(j)] = raiz(i)

        cabezas = {}
        for idx, ev in enumerate(del_dia):
            r = raiz(idx)
            if r not in cabezas:
                cabezas[r] = ev
            else:
                _completar(cabezas[r], ev)
                absorbidos.add(id(ev))

    return [ev for ev in resultado if id(ev) not in absorbidos]


def evento(titulo: str, fecha: str, lugar: str, categoria: str = '',
           direccion: str = '', url: str = '', fuente: str = '',
           imagen: str = '') -> dict:
    """Constructor estándar de evento."""
    titulo = limpiar_titulo(titulo)
    return {
        'titulo': titulo,
        'fecha': fecha,
        'lugar': lugar.strip()[:100],
        'direccion': direccion.strip()[:150],
        'categoria': categoria or detectar_categoria(titulo),
        'url': url,
        'fuente': fuente,
        'imagen': imagen.strip(),
    }
