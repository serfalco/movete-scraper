"""Alarma por fuentes chicas que se caen.

Las troncales (genda, livepass, alternativa) ya avisan siempre. Las otras
caían a 0 en silencio. Ahora avisan, pero una sola vez: cuando pasan de
scrapear en vivo a no hacerlo.
"""
import unittest

from main import fuentes_que_se_cayeron


class FuentesQueSeCayeronTests(unittest.TestCase):
    def test_avisa_la_que_paso_de_ok_a_caida(self):
        previa = {"estado": {"passline": "ok", "coliseo": "ok"}}
        hoy = {"passline": "cache", "coliseo": "ok"}
        self.assertEqual(fuentes_que_se_cayeron(previa, hoy), ["passline"])

    def test_no_repite_si_ya_venia_caida(self):
        previa = {"estado": {"teatrobar": "vencida", "passline": "cache"}}
        hoy = {"teatrobar": "vencida", "passline": "vencida"}
        self.assertEqual(fuentes_que_se_cayeron(previa, hoy), [])

    def test_ignora_troncales_y_comunidad(self):
        previa = {"estado": {"genda": "ok", "comunidad": "ok"}}
        hoy = {"genda": "cache", "comunidad": "vencida"}
        self.assertEqual(fuentes_que_se_cayeron(previa, hoy), [])

    def test_salud_vieja_sin_estado_usa_cantidades(self):
        # Formato del _salud.json anterior a este cambio.
        previa = {"por_fuente": {"passline": 6, "teatrobar": 0, "eventbrite": 0}}
        hoy = {"passline": "vencida", "teatrobar": "vencida", "eventbrite": "vencida"}
        self.assertEqual(fuentes_que_se_cayeron(previa, hoy), ["passline"])

    def test_fuente_que_no_corrio_antes_no_avisa(self):
        # eldia y 0221 solo corren los viernes.
        previa = {"estado": {"passline": "ok"}}
        hoy = {"passline": "ok", "eldia": "vencida"}
        self.assertEqual(fuentes_que_se_cayeron(previa, hoy), [])

    def test_sin_salud_previa_no_avisa(self):
        self.assertEqual(fuentes_que_se_cayeron({}, {"passline": "vencida"}), [])


if __name__ == "__main__":
    unittest.main()
