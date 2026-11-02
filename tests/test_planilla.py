import unittest
from datetime import date, timedelta

from scrapers.comunidad import _parsear


def _f(dias):
    return (date.today() + timedelta(days=dias)).strftime("%d/%m/%Y")


CABECERA = "Nombre del evento,Categoría,Fecha,Hora,Lugar,Dirección,Localidad,Fuente,Enlace\n"


class TestPlanilla(unittest.TestCase):
    def test_columnas_de_gpt_y_berisso_por_localidad(self):
        csv_txt = CABECERA + (
            f"Salí del Garaje,Música,{_f(5)},19:00,Raíces del Dawson,"
            f"Nueva York y Marsella,Berisso,El Mundo de Berisso,https://ejemplo.com/a\n"
        )
        ev = _parsear(csv_txt, fuente="planilla")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["fuente"], "planilla")
        self.assertEqual(ev[0]["url"], "https://ejemplo.com/a")

    def test_descarta_pasados_y_otras_ciudades(self):
        csv_txt = CABECERA + (
            f"Viejo,Música,{_f(-5)},20:00,Casa Suiza,Calle 2 Nº 621,La Plata,x,https://a.com\n"
            f"Lejos,Música,{_f(5)},20:00,Niceto,Niceto Vega,CABA,x,https://a.com\n"
        )
        self.assertEqual(_parsear(csv_txt, fuente="planilla"), [])


if __name__ == "__main__":
    unittest.main()
