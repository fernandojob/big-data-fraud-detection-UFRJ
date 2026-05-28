from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
import os
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Optional
from fraud_queries import (
    aplicar_filtros_alertas,
    limitar_resultado,
    montar_perfil_risco,
    ordenar_alertas_por_risco,
)

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


def _listar_fraudes_filtradas(
    risk_level: Optional[str] = None,
    id_usuario: Optional[str] = None,
    pais: Optional[str] = None,
    motivo: Optional[str] = None,
    valor_minimo: Optional[float] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    alertas = _read_parquet_prefix(GOLD_ALERTS_PREFIX)
    alertas = aplicar_filtros_alertas(
        alertas,
        risk_level,
        id_usuario,
        pais,
        motivo,
        valor_minimo,
        data_inicio,
        data_fim,
        decision,
    )
    alertas = ordenar_alertas_por_risco(alertas)
    return limitar_resultado(alertas, limit)


def _buscar_historico_usuario(id_usuario: str, limit: int = 20) -> list[dict]:
    transacoes = _read_parquet_prefix(SILVER_TRANSACTIONS_PREFIX)
    historico = [row for row in transacoes if row.get("id_usuario") == id_usuario]
    historico = sorted(historico, key=lambda row: row.get("data_hora"), reverse=True)
    return historico[:limit]


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
    data_inicio: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    data_fim: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    decision: Optional[str] = Query(default=None, pattern=r"^(APPROVE|REVIEW|BLOCK)$"),
    limit: int = Query(default=50, ge=1, le=500),
):
    return _listar_fraudes_filtradas(
        risk_level=risk_level,
        id_usuario=id_usuario,
        pais=pais,
        motivo=motivo,
        valor_minimo=valor_minimo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        decision=decision,
        limit=limit,
    )


@app.get("/fraudes/top")
def get_fraudes(limit: int = Query(default=50, ge=1, le=500)):
    return _listar_fraudes_filtradas(limit=limit)


@app.get("/transacoes/{id_transacao}")
def buscar_transacao(id_transacao: str):
    transacoes = _read_parquet_prefix(SILVER_TRANSACTIONS_PREFIX)
    for transacao in transacoes:
        if transacao.get("id_transacao") == id_transacao:
            return transacao

    raise HTTPException(status_code=404, detail="Transacao nao encontrada")


@app.get("/usuarios/{id_usuario}/historico")
def historico_usuario(id_usuario: str, limit: int = Query(default=20, ge=1, le=200)):
    return _buscar_historico_usuario(id_usuario, limit)


@app.get("/usuarios/{id_usuario}/perfil-risco")
def perfil_risco_usuario(id_usuario: str):
    historico = _buscar_historico_usuario(id_usuario, limit=200)
    if not historico:
        raise HTTPException(status_code=404, detail="Usuario sem historico encontrado")

    return montar_perfil_risco(id_usuario, historico)
