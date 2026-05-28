from typing import Optional


def aplicar_filtros_alertas(
    rows: list[dict],
    risk_level: Optional[str] = None,
    id_usuario: Optional[str] = None,
    pais: Optional[str] = None,
    motivo: Optional[str] = None,
    valor_minimo: Optional[float] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    decision: Optional[str] = None,
) -> list[dict]:
    filtered = rows

    if risk_level:
        filtered = [row for row in filtered if row.get("risk_level") == risk_level]
    if id_usuario:
        filtered = [row for row in filtered if row.get("id_usuario") == id_usuario]
    if pais:
        filtered = [row for row in filtered if row.get("pais_transacao") == pais]
    if motivo:
        filtered = [row for row in filtered if motivo in (row.get("risk_reasons") or [])]
    if valor_minimo is not None:
        filtered = [row for row in filtered if (row.get("valor") or 0) >= valor_minimo]
    if data_inicio:
        filtered = [
            row
            for row in filtered
            if str(row.get("data_processamento") or row.get("data_hora") or "")[:10] >= data_inicio
        ]
    if data_fim:
        filtered = [
            row
            for row in filtered
            if str(row.get("data_processamento") or row.get("data_hora") or "")[:10] <= data_fim
        ]
    if decision:
        filtered = [row for row in filtered if row.get("decision") == decision]

    return filtered


def ordenar_alertas_por_risco(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row.get("risk_score") or 0, row.get("valor") or 0), reverse=True)


def limitar_resultado(rows: list[dict], limit: int) -> list[dict]:
    return rows[:limit]


def montar_perfil_risco(id_usuario: str, historico: list[dict]) -> dict:
    alertas = [row for row in historico if row.get("risk_level") in ["MEDIUM", "HIGH", "CRITICAL"]]
    maior_score = max((row.get("risk_score") or 0 for row in historico), default=0)
    valor_total = sum(row.get("valor") or 0 for row in historico)

    return {
        "id_usuario": id_usuario,
        "total_transacoes": len(historico),
        "total_alertas": len(alertas),
        "maior_risk_score": maior_score,
        "valor_total": round(valor_total, 2),
        "principais_motivos": sorted(
            {motivo for row in alertas for motivo in (row.get("risk_reasons") or [])}
        ),
    }
