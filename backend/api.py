from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
import os
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Optional

app = FastAPI(title="API Antifraude")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=False, 
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "admin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "admin123"),
    secure=False
)

BUCKET = "fraudes"
if not client.bucket_exists(BUCKET):
    client.make_bucket(BUCKET)

GOLD_ALERTS_PREFIX = os.getenv("GOLD_ALERTS_PREFIX", "gold/alertas_fraude/")
SILVER_TRANSACTIONS_PREFIX = os.getenv("SILVER_TRANSACTIONS_PREFIX", "silver/transacoes_enriquecidas/")


def _partition_values(object_name: str) -> dict:
    values = {}
    for part in object_name.split("/"):
        if "=" in part:
            key, value = part.split("=", 1)
            values[key] = value
    return values


def _read_parquet_prefix(prefix: str) -> list[dict]:
    objects = client.list_objects(BUCKET, prefix=prefix, recursive=True)
    rows: list[dict] = []

    for obj in objects:
        if not obj.object_name.endswith(".parquet"):
            continue

        response = client.get_object(BUCKET, obj.object_name)
        try:
            data = response.read()
            table = pq.read_table(pa.BufferReader(data))
            partition_values = _partition_values(obj.object_name)
            for row in table.to_pylist():
                row.update({key: row.get(key, value) for key, value in partition_values.items()})
                rows.append(row)
        finally:
            response.close()
            response.release_conn()

    return rows


def _apply_alert_filters(
    rows: list[dict],
    risk_level: Optional[str],
    id_usuario: Optional[str],
    pais: Optional[str],
    motivo: Optional[str],
    valor_minimo: Optional[float],
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

    return filtered


@app.get("/health")
def health_check():
    return {"status": "ok", "bucket": BUCKET}


@app.get("/fraudes")
def listar_fraudes(
    risk_level: Optional[str] = Query(default=None),
    id_usuario: Optional[str] = Query(default=None),
    pais: Optional[str] = Query(default=None),
    motivo: Optional[str] = Query(default=None),
    valor_minimo: Optional[float] = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
):
    alertas = _read_parquet_prefix(GOLD_ALERTS_PREFIX)
    alertas = _apply_alert_filters(alertas, risk_level, id_usuario, pais, motivo, valor_minimo)
    alertas = sorted(alertas, key=lambda row: (row.get("risk_score") or 0, row.get("valor") or 0), reverse=True)
    return alertas[:limit]


@app.get("/fraudes/top")
def get_fraudes(limit: int = Query(default=50, ge=1, le=500)):
    return listar_fraudes(limit=limit)


@app.get("/transacoes/{id_transacao}")
def buscar_transacao(id_transacao: str):
    transacoes = _read_parquet_prefix(SILVER_TRANSACTIONS_PREFIX)
    for transacao in transacoes:
        if transacao.get("id_transacao") == id_transacao:
            return transacao

    raise HTTPException(status_code=404, detail="Transacao nao encontrada")


@app.get("/usuarios/{id_usuario}/historico")
def historico_usuario(id_usuario: str, limit: int = Query(default=20, ge=1, le=200)):
    transacoes = _read_parquet_prefix(SILVER_TRANSACTIONS_PREFIX)
    historico = [row for row in transacoes if row.get("id_usuario") == id_usuario]
    historico = sorted(historico, key=lambda row: row.get("data_hora"), reverse=True)
    return historico[:limit]


@app.get("/usuarios/{id_usuario}/perfil-risco")
def perfil_risco_usuario(id_usuario: str):
    historico = historico_usuario(id_usuario, limit=200)
    if not historico:
        raise HTTPException(status_code=404, detail="Usuario sem historico encontrado")

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
