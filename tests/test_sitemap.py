"""Pruebas del plan B por sitemap (core/sitemap.py).

Todo offline: se le pasan HTML y XML armados a mano, sin pedir nada a la red.
Los casos salen de lo que publican de verdad las fuentes.
"""
import unittest
from datetime import date

from core.sitemap import (_fechas_iso, _locs, _texto_lugar, evento_jsonld,
                          fechas_en_texto, meta_og, texto_visible)

HOY = date(2026, 9, 15)   # martes


def pagina(cuerpo: str) -> str:
    return f'<html><head></head><body>{cuerpo}</body></html>'


class FechasEnTextoTests(unittest.TestCase):
    """El Coliseo y el Teatro Metro escriben la función en prosa."""

    def test_coliseo_varias_funciones(self):
        texto = 'Sábado 19 de Septiembre | 20:00 Domingo 20 de Septiembre | 18:30'
        self.assertEqual(
            fechas_en_texto(texto, hoy=HOY),
            ['2026-09-19 20:00:00', '2026-09-20 18:30:00'])

    def test_metro_con_anio_explicito(self):
        self.assertEqual(
            fechas_en_texto('10 de Octubre de 2026 . 21:00 hs.', hoy=HOY),
            ['2026-10-10 21:00:00'])

    def test_sin_hora_no_es_funcion(self):
        # "venta en boletería a partir del 17 de febrero" no es una función:
        # por eso la hora es obligatoria.
        self.assertEqual(
            fechas_en_texto('VENTA EN BOLETERIA A PARTIR DEL 17 DE FEBRERO',
                            hoy=HOY), [])

    def test_horario_de_boleteria_no_entra(self):
        # El pie del Teatro Metro dice "calle 53 de lunes a sábados de 10.00".
        # "lunes" no es un mes, así que no matchea.
        self.assertEqual(
            fechas_en_texto('Boletería calle 53 de lunes a sábados de 10.00 a 20.00',
                            hoy=HOY), [])

    def test_deduce_el_anio_por_el_dia_de_la_semana(self):
        # El 3 de enero cae domingo en 2027, no en 2026.
        self.assertEqual(
            fechas_en_texto('Domingo 3 de Enero | 22:00', hoy=HOY),
            ['2027-01-03 22:00:00'])

    def test_dia_de_la_semana_mal_escrito_cae_en_la_proxima(self):
        # El 19/09/2026 es sábado; la fuente dice lunes. Gana la fecha futura.
        self.assertEqual(
            fechas_en_texto('Lunes 19 de Septiembre | 20:00', hoy=HOY),
            ['2026-09-19 20:00:00'])

    def test_fecha_que_no_existe(self):
        self.assertEqual(fechas_en_texto('Jueves 29 de Febrero | 20:00', hoy=HOY), [])

    def test_hora_invalida(self):
        self.assertEqual(fechas_en_texto('Viernes 25 de Septiembre | 99:99', hoy=HOY), [])

    def test_mes_inventado(self):
        self.assertEqual(fechas_en_texto('Viernes 25 de Marzoo | 21:00', hoy=HOY), [])

    def test_fecha_pasada_con_anio_se_descarta(self):
        self.assertEqual(fechas_en_texto('1 de Marzo de 2020 . 21:00 hs', hoy=HOY), [])

    def test_no_repite_la_misma_funcion(self):
        texto = 'Sábado 19 de Septiembre | 20:00 y tambien Sábado 19 de Septiembre | 20:00'
        self.assertEqual(fechas_en_texto(texto, hoy=HOY), ['2026-09-19 20:00:00'])


class EventoJsonLdTests(unittest.TestCase):
    """Livepass, PlateaUno y el Coliseo publican schema.org/Event."""

    def test_event_completo(self):
        html = pagina('''<script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Event","name":"TIRRIA",
         "startDate":"2026-09-18T21:00:00-03:00",
         "location":{"@type":"Place","name":"LaPlata Metro",
                     "address":{"@type":"PostalAddress",
                                "streetAddress":"Calle 4 978","addressLocality":"La Plata"}},
         "image":["https://x/1.jpg"],"description":"obra de teatro"}
        </script>''')
        d = evento_jsonld(html)
        self.assertEqual(d['titulo'], 'TIRRIA')
        self.assertEqual(d['fechas'], ['2026-09-18 21:00:00'])
        self.assertEqual(d['lugar'], 'LaPlata Metro')
        self.assertEqual(d['direccion'], 'Calle 4 978, La Plata')
        self.assertEqual(d['imagen'], 'https://x/1.jpg')

    def test_event_adentro_de_un_graph(self):
        # Así lo publica el Coliseo: el Event cuelga de @graph.
        html = pagina('''<script type="application/ld+json">
        {"@graph":[{"@type":"WebSite","name":"Coliseo"},
                   {"@type":"Event","name":"LAS HIJAS",
                    "startDate":["2026-11-07T20:00","2026-11-07T22:00"]}]}
        </script>''')
        d = evento_jsonld(html)
        self.assertEqual(d['titulo'], 'LAS HIJAS')
        self.assertEqual(d['fechas'], ['2026-11-07 20:00:00', '2026-11-07 22:00:00'])

    def test_json_roto_no_explota(self):
        html = pagina('<script type="application/ld+json">{esto no es json</script>')
        self.assertEqual(evento_jsonld(html), {})

    def test_sin_event_devuelve_vacio(self):
        html = pagina('<script type="application/ld+json">{"@type":"Product"}</script>')
        self.assertEqual(evento_jsonld(html), {})

    def test_event_sin_fecha_no_sirve(self):
        html = pagina('<script type="application/ld+json">'
                      '{"@type":"Event","name":"Sin fecha"}</script>')
        self.assertEqual(evento_jsonld(html), {})

    def test_tipo_derivado_de_event(self):
        html = pagina('<script type="application/ld+json">'
                      '{"@type":"TheaterEvent","name":"Obra","startDate":"2026-10-01"}</script>')
        self.assertEqual(evento_jsonld(html)['titulo'], 'Obra')

    def test_fecha_sin_hora_asume_las_21(self):
        self.assertEqual(_fechas_iso('2026-10-01'), ['2026-10-01 21:00:00'])

    def test_fecha_basura_se_ignora(self):
        self.assertEqual(_fechas_iso(['', None, 'proximamente', 42]), [])

    def test_lugar_como_texto_suelto(self):
        self.assertEqual(_texto_lugar('Teatro Ópera'), ('Teatro Ópera', ''))

    def test_lugar_sin_direccion(self):
        self.assertEqual(_texto_lugar({'@type': 'Place', 'name': 'Guajira'}),
                         ('Guajira', ''))


class LecturaDePaginaTests(unittest.TestCase):
    def test_locs_del_sitemap(self):
        xml = ('<urlset><url><loc> https://a/1 </loc></url>'
               '<url><loc>https://a/2</loc></url></urlset>')
        self.assertEqual(_locs(xml), ['https://a/1', 'https://a/2'])

    def test_meta_og_desescapa_entidades(self):
        html = pagina('<meta property="og:title" content="El esp&iacute;ritu">'
                      '<meta property="og:image" content="https://x/a.jpg">')
        og = meta_og(html)
        self.assertEqual(og['title'], 'El espíritu')
        self.assertEqual(og['image'], 'https://x/a.jpg')

    def test_texto_visible_saca_scripts_y_menu(self):
        html = pagina('<nav>MENU</nav><script>var x=1</script><p>Hola   mundo</p>')
        self.assertEqual(texto_visible(html), 'Hola mundo')


if __name__ == '__main__':
    unittest.main()


class LivepassPrefiltroTests(unittest.TestCase):
    """El prefiltro por URL y la unificación de nombres de sala."""

    def setUp(self):
        from scrapers import livepass
        self.lp = livepass

    def test_entra_a_las_salas_platenses(self):
        for u in ('https://livepass.com.ar/events/rey-garufa-en-el-teatro-opera-lp',
                  'https://livepass.com.ar/events/diego-torres-en-el-hipodromo-de-la-plata',
                  'https://livepass.com.ar/events/sin-datos-en-guajira-lp'):
            with self.subTest(url=u):
                self.assertTrue(self.lp._tiene_pista(u))

    def test_estadio_de_estudiantes(self):
        # Se llama "Jorge Luis Hirschi" en la ficha pero en la URL es
        # 'estadio-uno'. Sin esta pista el prefiltro lo dejaba afuera.
        self.assertTrue(self.lp._tiene_pista(
            'https://livepass.com.ar/events/tan-bionica-en-estadio-uno'))

    def test_no_entra_a_las_portenas(self):
        for u in ('https://livepass.com.ar/events/dolar-blues-en-cafe-berlin',
                  'https://livepass.com.ar/events/gyomara-trio-en-ccnu-2026-09-17',
                  'https://livepass.com.ar/events/bhavi-en-san-miguel-18-09'):
            with self.subTest(url=u):
                self.assertFalse(self.lp._tiene_pista(u))

    def test_unifica_el_nombre_de_la_sala(self):
        # El JSON-LD escribe sin tildes y con nombres largos; la revista tiene
        # que mostrar siempre el mismo nombre para la misma sala.
        casos = {
            'Teatro Opera La Plata': 'Teatro Ópera La Plata',
            'Hipodromo de La Plata': 'Hipódromo de La Plata',
            'Teatro Argentino Centro Provincial de las Artes': 'Teatro Argentino La Plata',
            'Sala Ginastera - Teatro Argentino': 'Teatro Argentino La Plata',
        }
        for crudo, esperado in casos.items():
            with self.subTest(sala=crudo):
                self.assertEqual(self.lp._canonizar(crudo, '')[0], esperado)

    def test_sala_desconocida_queda_como_viene(self):
        # Guajira no está en VENUES: se respeta lo que diga la fuente.
        self.assertEqual(self.lp._canonizar('Guajira', 'Calle 1'),
                         ('Guajira', 'Calle 1'))

    def test_la_sala_conocida_trae_su_direccion(self):
        self.assertEqual(self.lp._canonizar('Teatro Opera La Plata', '')[1],
                         'Calle 58 entre 10 y 11, La Plata')


class LivepassFusionTests(unittest.TestCase):
    """Las tarjetas del HTML cortan los títulos; el JSON-LD los da enteros."""

    def setUp(self):
        from scrapers import livepass
        self.lp = livepass

    def _ev(self, titulo, fecha='2026-09-25 20:00:00', lugar='Teatro Ópera La Plata'):
        return {'titulo': titulo, 'fecha': fecha, 'lugar': lugar,
                'direccion': '', 'categoria': 'musica', 'url': '',
                'fuente': 'livepass', 'imagen': ''}

    def test_el_cortado_cede_ante_el_entero(self):
        venues = [self._ev('ROMPIENDO ESPEJOS - Tributo a Callej ...')]
        sitemap = [self._ev('ROMPIENDO ESPEJOS - Tributo a Callejeros')]
        r = self.lp._fusionar(venues, sitemap)
        self.assertEqual([e['titulo'] for e in r],
                         ['ROMPIENDO ESPEJOS - Tributo a Callejeros'])

    def test_otro_dia_no_se_fusiona(self):
        venues = [self._ev('ROMPIENDO ESPEJOS - Tributo a Callej ...',
                           fecha='2026-10-02 20:00:00')]
        sitemap = [self._ev('ROMPIENDO ESPEJOS - Tributo a Callejeros')]
        self.assertEqual(len(self.lp._fusionar(venues, sitemap)), 2)

    def test_otra_sala_no_se_fusiona(self):
        venues = [self._ev('HECATOMBE - MI PRIMERA GUERRA MUNDIA ...',
                           lugar='Teatro Argentino La Plata')]
        sitemap = [self._ev('HECATOMBE - MI PRIMERA GUERRA MUNDIAL')]
        self.assertEqual(len(self.lp._fusionar(venues, sitemap)), 2)

    def test_dos_shows_distintos_conviven(self):
        venues = [self._ev('EMANERO')]
        sitemap = [self._ev('DYANGO')]
        self.assertEqual(len(self.lp._fusionar(venues, sitemap)), 2)

    def test_titulo_muy_corto_no_arrastra(self):
        # "LA K" es prefijo de "LA KONGA" pero es demasiado corto para
        # afirmar que son el mismo show.
        venues = [self._ev('LA K')]
        sitemap = [self._ev('LA KONGA')]
        self.assertEqual(len(self.lp._fusionar(venues, sitemap)), 2)

    def test_sin_sitemap_no_toca_nada(self):
        venues = [self._ev('EMANERO'), self._ev('DYANGO')]
        self.assertEqual(len(self.lp._fusionar(venues, [])), 2)
