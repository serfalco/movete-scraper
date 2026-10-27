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


def reparar_espacios(titulo: str) -> str:
    """Livepass publica el nombre del Event con los espacios duros (U+00A0)
    convertidos en '?': "MAS ALLA?TOUR?en Guajira LP". Un '?' pegado a la
    palabra siguiente no es una pregunta —en castellano llevaría '¿'—, es un
    espacio roto. Los '?' de fin de frase ("¿Quién?") se dejan."""
    t = titulo.replace('\u00a0', ' ')
    if '¿' not in t:
        t = re.sub(r'(?<=\S)\?+(?=[^\s?!.,;:)\]"\'»”’])', ' ', t)
    return t


def limpiar_titulo(titulo: str) -> str:
    # Algunas fuentes entregan el título con entidades HTML sin convertir
    # ("Camerata Rosario presenta &apos;Las 8 Estaciones&apos;"). Se hace dos
    # veces porque hay fuentes que escapan dos veces (&amp;apos;).
    t = reparar_espacios(_html.unescape(_html.unescape(titulo)))
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
# Si el título corto es el comienzo del largo y además coinciden sala y hora,
# alcanza con un largo menor: "Escalandrum" contra "Escalandrum - Jazz, tango
# y folclore" son el mismo show aunque el corto tenga solo 11 letras.
MIN_LARGO_PREFIJO_MISMA_FUNCION = 8
# Más corto todavía si el corto es el comienzo del largo en PALABRAS enteras:
# "Play" (alternativa) contra "Play, de Samuel Beckett" (genda), misma sala y
# hora, edición del 29/10/2026. "Play" contra "Playlist" no entra.
MIN_LARGO_PALABRAS_MISMA_FUNCION = 4
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


# Palabras que no distinguen una sala de otra ("Teatro", "Centro Cultural"...).
_PALABRAS_SALA_COMUNES = {
    'teatro', 'de', 'del', 'la', 'el', 'los', 'las', 'y', 'en', 'centro',
    'cultural', 'museo', 'plata', 'sala', 'club', 'calle', 'av', 'avenida',
}


def _palabras_sala(lugar: str) -> set:
    """Palabras que sí distinguen a la sala: 'Teatro y Museo Coliseo Podestá'
    queda en {coliseo, podesta}."""
    palabras = re.findall(r'[a-z0-9]+', _sin_acentos(lugar.lower()))
    return {p for p in palabras
            if p not in _PALABRAS_SALA_COMUNES and len(p) >= 3}


def _misma_sala(a: str, b: str) -> bool:
    """Cada fuente escribe la sala a su manera: 'Teatro Metro', 'Teatro Metro
    La Plata', 'Metro'. Alcanza con que una esté contenida en la otra.

    Si no alcanza por texto, se comparan las palabras que distinguen a la
    sala: 'Teatro Coliseo Podestá' y 'Teatro y Museo Coliseo Podestá', o
    'Teatro de la UNLP' y 'Asociación Amigos del Taller de Teatro de la
    Universidad Nacional de La Plata - Teatro UNLP', son la misma sala.
    """
    ka, kb = _clave_lugar(a), _clave_lugar(b)
    if len(ka) < 4 or len(kb) < 4:
        return False
    if ka in kb or kb in ka:
        return True
    pa, pb = _palabras_sala(a), _palabras_sala(b)
    if not pa or not pb:
        return False
    chico, grande = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return chico <= grande


_PALABRAS_TITULO_VACIAS = {'y', 'e', 'and', 'en', 'de', 'la', 'el', 'los', 'las', 'con', 'vivo'}


def _palabras_contenidas(t1: str, t2: str) -> bool:
    """True si todas las palabras del título con menos palabras aparecen
    dentro del otro, que puede tenerlas pegadas o con prefijos: "Leti y Bic"
    (genda) contra "143LETI + BIC" (livepass). Se pide un mínimo de letras
    para no juntar títulos de una sola palabra corta."""
    def palabras(t):
        return [p for p in re.findall(r'[a-z0-9]+', _sin_acentos(t.lower()))
                if p not in _PALABRAS_TITULO_VACIAS]
    pa, pb = palabras(t1), palabras(t2)
    if not pa or not pb:
        return False
    chico, grande = (pa, pb) if len(''.join(pa)) <= len(''.join(pb)) else (pb, pa)
    if len(chico) < 2 or len(''.join(chico)) < 6:
        return False
    junto = ''.join(grande)
    return all(p in junto for p in chico)


def _empieza_con_palabras(t1: str, t2: str) -> bool:
    """True si las palabras del título más corto son el comienzo exacto de
    las del otro: "Play" y "Play, de Samuel Beckett"."""
    def palabras(t):
        return re.findall(r'[a-z0-9]+', _sin_acentos(t.lower()))
    pa, pb = palabras(t1), palabras(t2)
    if not pa or not pb or len(pa) == len(pb):
        return False
    chico, grande = (pa, pb) if len(pa) < len(pb) else (pb, pa)
    return grande[:len(chico)] == chico


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
    misma_hora = uno['fecha'][11:16] == otro['fecha'][11:16]
    secuela = largo.startswith(corto) and _es_secuela(largo[len(corto):])
    if misma_hora and not secuela and _palabras_contenidas(uno['titulo'], otro['titulo']):
        return _misma_sala(uno['lugar'], otro['lugar'])
    if len(corto) < MIN_LARGO_PARECIDO:
        # Solo se perdona un título corto si es el comienzo del otro y la
        # función (sala + hora) coincide.
        prefijo_ok = misma_hora and largo.startswith(corto) and (
            len(corto) >= MIN_LARGO_PREFIJO_MISMA_FUNCION
            or (len(corto) >= MIN_LARGO_PALABRAS_MISMA_FUNCION
                and _empieza_con_palabras(uno['titulo'], otro['titulo'])))
        if not prefijo_ok:
            return False
    if not _misma_sala(uno['lugar'], otro['lugar']):
        return False
    if largo.startswith(corto) and _es_secuela(largo[len(corto):]):
        return False

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


# Salas cerradas: las fuentes (la propia web de la sala, Teatro Cerca, Genda)
# siguen listando funciones que ya se suspendieron. Mientras dure el cierre,
# esas funciones no salen. (palabras de la sala, cerrada hasta esta fecha
# exclusive, motivo).
SALAS_CERRADAS = [
    # laplataya.com.ar 08/10/2026: suspende todo hasta fines de noviembre
    # por obras demoradas; ~20 shows reprogramados para diciembre.
    ({'coliseo', 'podesta'}, '2026-12-01', 'obras en la sala'),
]


def en_sala_cerrada(ev: dict) -> bool:
    palabras = _palabras_sala(ev.get('lugar', ''))
    fecha = (ev.get('fecha') or '')[:10]
    return any(clave <= palabras and fecha < hasta
               for clave, hasta, _motivo in SALAS_CERRADAS)
