"""Pruebas del deduplicador.

Cada fuente escribe el mismo show a su manera, así que la misma obra llegaba
a salir tres veces en la revista. Los casos de acá salieron de la cartelera
real del 15/09/2026.

La regla: misma sala siempre; si además coincide la hora alcanza con que los
títulos se parezcan, porque una sala no puede tener dos cosas a la vez. Si la
hora no coincide se exige mucho más, porque ahí sí conviven cosas distintas.
"""
import unittest

from core.normalizar import deduplicar, limpiar_titulo


def ev(titulo, hora='21:00', fecha='2026-10-10', lugar='Teatro Metro',
       fuente='genda', imagen='', url='', direccion=''):
    return {'titulo': titulo, 'fecha': f'{fecha} {hora}:00', 'lugar': lugar,
            'direccion': direccion, 'categoria': 'musica', 'url': url,
            'fuente': fuente, 'imagen': imagen}


class LimpiarTituloTests(unittest.TestCase):
    def test_convierte_entidades_html(self):
        self.assertEqual(
            limpiar_titulo('Camerata presenta &apos;Las 8 Estaciones&apos;'),
            "Camerata presenta 'Las 8 Estaciones'")

    def test_convierte_entidades_dobles(self):
        self.assertEqual(limpiar_titulo('Tango &amp;amp; Jazz'), 'Tango & Jazz')

    def test_saca_los_puntos_suspensivos(self):
        self.assertEqual(limpiar_titulo('EL ESCRITOR DE TODAS LAS ...'),
                         'EL ESCRITOR DE TODAS LAS')
        self.assertEqual(limpiar_titulo('ROMPIENDO ESPEJOS…'),
                         'ROMPIENDO ESPEJOS')

    def test_las_comillas_se_sacan_de_a_pares(self):
        self.assertEqual(limpiar_titulo('"La Casa de Bernarda Alba"'),
                         'La Casa de Bernarda Alba')
        # La de cierre no se come sola.
        self.assertEqual(limpiar_titulo("Camerata presenta 'Las 8 Estaciones'"),
                         "Camerata presenta 'Las 8 Estaciones'")


class SeJuntanTests(unittest.TestCase):
    """Misma sala y misma hora: es el mismo show."""

    def test_tres_fuentes_un_solo_show(self):
        evs = [ev('New sensation - Tributo INXS', fuente='genda'),
               ev('NEW SENSATION', lugar='Teatro Metro La Plata',
                  fuente='teatro-metro'),
               ev('NEW SENSATION 2026', lugar='Metro', fuente='plateauno')]
        r = deduplicar(evs)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['titulo'], 'New sensation - Tributo INXS')

    def test_se_junta_por_contagio(self):
        # El primero y el tercero no se parecen entre sí; los une el segundo.
        evs = [ev('Historias innecesarias - Damián Kuc'),
               ev('HISTORIAS INNECESARIAS', lugar='Metro'),
               ev('Historias Innecesarias En Vivo.',
                  lugar='Teatro Metro La Plata')]
        self.assertEqual(len(deduplicar(evs)), 1)

    def test_diferencias_de_tilde_y_mayuscula(self):
        evs = [ev('Homenaje sinfónico a Los Redondos'),
               ev('HOMENAJE SINFONICO A REDONDOS', lugar='Metro')]
        self.assertEqual(len(deduplicar(evs)), 1)

    def test_una_fuente_agrega_el_subtitulo(self):
        evs = [ev('Cuadrilateros 6', lugar='Teatro Estudio'),
               ev('Cuadriláteros 6, teatro breve reunido',
                  lugar='TEATRO ESTUDIO DE LAS ARTES')]
        self.assertEqual(len(deduplicar(evs)), 1)

    def test_titulos_que_se_parecen_poco_pero_comparten_funcion(self):
        evs = [ev('Sofia Viola - 20 Años DELUXE', lugar='Guajira Bar'),
               ev('Sofia Viola - 20 años Edición Deluxe - La Plata',
                  lugar='GUAJIRA BAR')]
        self.assertEqual(len(deduplicar(evs)), 1)

    def test_un_anio_es_la_edicion_no_la_parte(self):
        evs = [ev('Festival de jazz de La Plata'),
               ev('Festival de jazz de La Plata 2026')]
        self.assertEqual(len(deduplicar(evs)), 1)


class NoSeJuntanTests(unittest.TestCase):
    """Lo que hay que dejar en paz, aunque los títulos se parezcan."""

    def test_distinta_hora_y_parecido_flojo(self):
        # Dos talleres del mismo día en la misma sala. Dan 0.83 de parecido y
        # son dos cosas distintas.
        evs = [ev('Taller de teatro para adultos', hora='15:00'),
               ev('Taller de teatro para niños', hora='17:00')]
        self.assertEqual(len(deduplicar(evs)), 2)

    def test_distinta_hora_aunque_uno_sea_el_comienzo_del_otro(self):
        evs = [ev('Observación astronómica', hora='19:00'),
               ev('Observación astronómica guiada', hora='21:00')]
        self.assertEqual(len(deduplicar(evs)), 2)

    def test_distinta_sala(self):
        evs = [ev('Historias innecesarias - Damián Kuc', lugar='Teatro Metro'),
               ev('HISTORIAS INNECESARIAS', lugar='Coliseo Podestá')]
        self.assertEqual(len(deduplicar(evs)), 2)

    def test_una_secuela_no_es_el_mismo_show(self):
        evs = [ev('Los juegos del hambre'), ev('Los juegos del hambre 2')]
        self.assertEqual(len(deduplicar(evs)), 2)

    def test_una_secuela_en_romanos_tampoco(self):
        evs = [ev('Los juegos del hambre'), ev('Los juegos del hambre II')]
        self.assertEqual(len(deduplicar(evs)), 2)

    def test_titulos_cortos_no_se_arrastran(self):
        self.assertEqual(len(deduplicar([ev('LA K'), ev('LA KONGA')])), 2)

    def test_dos_shows_distintos(self):
        self.assertEqual(len(deduplicar([ev('EMANERO'), ev('DYANGO')])), 2)

    def test_mismo_titulo_otro_dia(self):
        evs = [ev('Historias innecesarias - Damián Kuc', fecha='2026-10-10'),
               ev('Historias innecesarias - Damián Kuc', fecha='2026-10-17')]
        self.assertEqual(len(deduplicar(evs)), 2)


class QueSeConservaTests(unittest.TestCase):
    def test_el_repetido_completa_imagen_link_y_direccion(self):
        evs = [ev('NEW SENSATION', fuente='genda'),
               ev('NEW SENSATION', fuente='plateauno', imagen='https://x/a.jpg',
                  url='https://x/e', direccion='Calle 4, La Plata')]
        r = deduplicar(evs)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['imagen'], 'https://x/a.jpg')
        self.assertEqual(r[0]['url'], 'https://x/e')
        self.assertEqual(r[0]['direccion'], 'Calle 4, La Plata')

    def test_gana_el_titulo_completo_sobre_el_cortado(self):
        evs = [ev('EL ESCRITOR DE TODAS LAS', lugar='Metro', fuente='plateauno'),
               ev('EL ESCRITOR DE TODAS LAS COSAS', lugar='Teatro Metro La Plata',
                  fuente='teatro-metro')]
        r = deduplicar(evs)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['titulo'], 'EL ESCRITOR DE TODAS LAS COSAS')


if __name__ == '__main__':
    unittest.main()
