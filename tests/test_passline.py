"""Filtro de La Plata de Passline: el lugar viene sin ciudad ("Casa Suiza")."""
import unittest

from scrapers.passline import es_local


class EsLocalTests(unittest.TestCase):
    def test_sala_propia_entra_aunque_no_diga_la_plata(self):
        self.assertTrue(es_local("Kiss Me, en Espacio Live!", "Espacio Live", None))
        self.assertTrue(es_local("Los Bidú", "Casa Suiza", None))

    def test_sala_propia_afuera_si_nombra_otra_ciudad(self):
        self.assertFalse(es_local("Gira en Rosario", "Espacio Live", None))

    def test_productora_mixta_solo_salas_platenses(self):
        lug = ("vonharv",)
        self.assertTrue(es_local("LA TM - VONHARV VOLUMEN 2", "Vonharv", lug))
        self.assertFalse(es_local("LA TM - PINAMAR", "Kota Beach", lug))
        self.assertFalse(es_local("LA TM - Corrientes Volumen 2", "Zavod", lug))

    def test_mixta_entra_si_dice_la_plata(self):
        self.assertTrue(es_local("Oliver Kozlov en vivo en La Plata", "Pampa Cultural",
                                 ("pampa cultural",)))
        self.assertFalse(es_local("Oliver Kozlov en vivo en Buenos Aires",
                                  "UN LUGAR AParte - ULAP", ("pampa cultural",)))

    def test_mixta_acentos(self):
        self.assertTrue(es_local("La Mancha de Rolando", "Teatro René Favaloro",
                                 ("rene favaloro",)))
        self.assertFalse(es_local("Intimo Lomas de Zamora", "Espacio Dali", ("la nonna",)))


if __name__ == "__main__":
    unittest.main()
