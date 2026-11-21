"""Pruebas del scraper de Teatro Cerca. Offline: HTML armado a mano."""
import unittest

from scrapers.teatrocerca import parsear_funcion, urls_de_funciones

FICHA = '''<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"WebPage"},
{"@type":"TheaterEvent","name":"Agonizantes","startDate":"2999-10-10T21:00:00-03:00",
"location":{"@type":"Place","name":"Espacio 44","address":"Av. 44 N° 496, La Plata"},
"image":"https://teatrocerca.com.ar/uploads/posters/a.webp"}]}
</script></head><body></body></html>'''

U = 'https://teatrocerca.com.ar/obra/agonizantes-obra/funcion/la-plata/espacio-44/10-octubre-2999'


class TeatroCercaTests(unittest.TestCase):
    def test_urls_solo_la_plata_sin_repetir(self):
        html = (f'<a href="{U}">x</a><a href="{U}">y</a>'
                '<a href="https://teatrocerca.com.ar/obra/otra/funcion/quilmes/sala/1-octubre-2999">z</a>')
        self.assertEqual(urls_de_funciones(html), [U])

    def test_funcion_futura(self):
        ev = parsear_funcion(FICHA, U, 'teatro')
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]['titulo'], 'Agonizantes')
        self.assertEqual(ev[0]['fecha'][:16], '2999-10-10 21:00')
        self.assertEqual(ev[0]['lugar'], 'Espacio 44')
        self.assertEqual(ev[0]['fuente'], 'teatrocerca')
        self.assertTrue(ev[0]['imagen'].endswith('a.webp'))

    def test_funcion_pasada_se_descarta(self):
        self.assertEqual(parsear_funcion(FICHA.replace('2999', '2001'), U), [])

    def test_pagina_sin_evento(self):
        self.assertEqual(parsear_funcion('<html></html>', U), [])


if __name__ == '__main__':
    unittest.main()


def test_listado_vacio_se_reintenta_una_vez(monkeypatch):
    """Si el listado viene sin funciones se prueba de nuevo antes del respaldo."""
    from scrapers import teatrocerca as tc
    llamadas = []
    respuestas = [{}, {'https://teatrocerca.com.ar/obra/x/funcion/la-plata/y/1': 'teatro'}]
    monkeypatch.setattr(tc, '_recolectar', lambda: llamadas.append(1) or respuestas[len(llamadas) - 1])
    monkeypatch.setattr(tc, '_pedir', lambda url, params=None: None)
    monkeypatch.setattr(tc.time, 'sleep', lambda s: None)
    tc.scrape(espera_reintento=0)
    assert len(llamadas) == 2
