"""Recorridos cargados sede por sede: una tarjeta, no once.

Caso real: la Noche de los Templos del 21/11/2026 llegó de Genda como un
evento por templo, todos a las 20:00, cargados en 20 minutos el 19/11. A la
misma hora había shows de verdad (La Vela Puerca en el Hipódromo) que no
tienen que tocarse.
"""
import unittest

from core.normalizar import agrupar_recorridos


def ev(titulo, lugar, carga, fecha='2026-11-21 20:00:00', fuente='genda', cat='otros'):
    return {'titulo': titulo, 'fecha': fecha, 'lugar': lugar, 'direccion': '',
            'categoria': cat, 'fuente': fuente, 'imagen': '',
            'url': f'https://agendalaplata.ar/evento/x-{carga}' if carga else ''}


TEMPLOS = [
    ev('Catedral de La Plata', 'Catedral de La Plata - Museo Eclesiástico Catedral', '20261119131652'),
    ev('Sikh, Fe Baháí, Asrau y AMIA', 'Plaza Moreno', '20261119132700'),
    ev('Santuario Nuestra Señora de Schoenstatt', 'Santuario Nuestra Señora de Schoenstatt', '20261119132744'),
    ev('Masoneria', 'Plaza Moreno', '20261119132823'),
    ev('Iglesia Pentecostal Puerta del Cielo', 'Iglesia Pentecostal Puerta del Cielo', '20261119132859'),
    ev('Iglesia Evangélica Luterana', 'Iglesia Luterana en La Plata - Congregación San Timoteo', '20261119133032'),
    ev('Iglesia San Francisco', 'Iglesia San Francisco de Asís', '20261119133107'),
    ev('Iglesia Evangélica Metodista', 'Iglesia Evangelica Metodista', '20261119133424'),
]
SHOWS = [
    ev('La vela puerca + Las pelotas', 'Hipódromo de La Plata', '20260814134809', cat='musica'),
    ev('Roberto Antier', 'Desafinado Club', '20261023125450', cat='musica'),
]


class RecorridosTests(unittest.TestCase):
    def test_junta_los_templos_y_deja_los_shows(self):
        r = agrupar_recorridos(SHOWS + TEMPLOS, nombrar=lambda g: 'Noche de los Templos')
        self.assertEqual(len(r), 3)
        rec = [e for e in r if e['titulo'] == 'Noche de los Templos'][0]
        self.assertEqual(rec['lugar'], 'Varias sedes')
        self.assertEqual(len(rec['sedes']), 7)          # Plaza Moreno una vez
        self.assertIn('Iglesia San Francisco de Asís', rec['sinopsis'])
        self.assertTrue(rec['url'])
        self.assertIn('Roberto Antier', [e['titulo'] for e in r])

    def test_sin_nombre_queda_recorrido_por_n_sedes(self):
        r = agrupar_recorridos(TEMPLOS)
        self.assertEqual([e['titulo'] for e in r], ['Recorrido por 7 sedes'])

    def test_si_nombrar_falla_no_se_cae(self):
        def roto(_g):
            raise RuntimeError('sin red')
        self.assertEqual(len(agrupar_recorridos(TEMPLOS, nombrar=roto)), 1)

    def test_festival_con_shows_a_la_misma_hora_no_se_junta(self):
        festival = [ev(f'Banda {n}', f'Sala {n}', f'2026111913{n:02d}00') for n in range(6)]
        self.assertEqual(len(agrupar_recorridos(festival)), 6)

    def test_pocas_sedes_no_alcanza(self):
        self.assertEqual(len(agrupar_recorridos(TEMPLOS[:4])), 4)

    def test_cargas_separadas_no_se_mezclan(self):
        # Mismo día y hora pero cargados con días de diferencia: cada uno por su lado.
        sueltos = [ev(t['titulo'], t['lugar'], f'202611{10 + i:02d}120000')
                   for i, t in enumerate(TEMPLOS)]
        self.assertEqual(len(agrupar_recorridos(sueltos)), len(TEMPLOS))

    def test_fuente_sin_marca_de_carga(self):
        sin = [dict(e, url='', fuente='planilla') for e in TEMPLOS]
        self.assertEqual(len(agrupar_recorridos(sin)), 1)


if __name__ == '__main__':
    unittest.main()
