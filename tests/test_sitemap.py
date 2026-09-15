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
