import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fraud_queries import (
    aplicar_filtros_alertas,
    limitar_resultado,
    montar_perfil_risco,
    ordenar_alertas_por_risco,
)


class FraudQueriesTest(unittest.TestCase):
    def setUp(self):
        self.alertas = [
            {
                "id_transacao": "tx_1",
                "id_usuario": "user_1",
                "risk_level": "CRITICAL",
                "risk_score": 95,
                "valor": 5000,
                "pais_transacao": "JP",
                "data_processamento": "2026-05-22",
                "risk_reasons": ["IMPOSSIBLE_TRAVEL", "NEW_COUNTRY_FOR_USER"],
            },
            {
                "id_transacao": "tx_2",
                "id_usuario": "user_2",
                "risk_level": "HIGH",
                "risk_score": 70,
                "valor": 8000,
                "pais_transacao": "BR",
                "data_processamento": "2026-05-21",
                "risk_reasons": ["VALUE_ABOVE_USER_PROFILE"],
            },
            {
                "id_transacao": "tx_3",
                "id_usuario": "user_1",
                "risk_level": "MEDIUM",
                "risk_score": 45,
                "valor": 900,
                "pais_transacao": "US",
                "data_processamento": "2026-05-20",
                "risk_reasons": ["NEW_DEVICE"],
            },
        ]

    def test_filtra_alertas_por_motivo_e_periodo(self):
        filtrados = aplicar_filtros_alertas(
            self.alertas,
            motivo="IMPOSSIBLE_TRAVEL",
            data_inicio="2026-05-22",
            data_fim="2026-05-22",
        )

        self.assertEqual(["tx_1"], [row["id_transacao"] for row in filtrados])

    def test_ordena_por_score_e_usa_valor_como_desempate(self):
        alertas = [
            {"id_transacao": "baixo", "risk_score": 60, "valor": 10000},
            {"id_transacao": "alto", "risk_score": 90, "valor": 100},
            {"id_transacao": "desempate", "risk_score": 90, "valor": 500},
        ]

        ordenados = ordenar_alertas_por_risco(alertas)

        self.assertEqual(["desempate", "alto", "baixo"], [row["id_transacao"] for row in ordenados])

    def test_limita_resultado(self):
        self.assertEqual(2, len(limitar_resultado(self.alertas, 2)))

    def test_monta_perfil_risco(self):
        perfil = montar_perfil_risco("user_1", self.alertas)

        self.assertEqual("user_1", perfil["id_usuario"])
        self.assertEqual(3, perfil["total_transacoes"])
        self.assertEqual(3, perfil["total_alertas"])
        self.assertEqual(95, perfil["maior_risk_score"])
        self.assertEqual(13900, perfil["valor_total"])
        self.assertEqual(
            ["IMPOSSIBLE_TRAVEL", "NEW_COUNTRY_FOR_USER", "NEW_DEVICE", "VALUE_ABOVE_USER_PROFILE"],
            perfil["principais_motivos"],
        )


if __name__ == "__main__":
    unittest.main()
