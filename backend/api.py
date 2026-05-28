from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
import duckdb
import os
from pathlib import Path
import shutil
from typing import Optional
from fraud_queries import (
    montar_perfil_risco,
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
PARQUET_CACHE_DIR = Path(os.getenv("PARQUET_CACHE_DIR", "/tmp/fraud-serving-cache"))


def _sync_parquet_prefix(prefix: str) -> Optional[str]:
    objects = client.list_objects(BUCKET, prefix=prefix, recursive=True)
    prefix_dir = PARQUET_CACHE_DIR / prefix.strip("/")

    if prefix_dir.exists():
        shutil.rmtree(prefix_dir)
    prefix_dir.mkdir(parents=True, exist_ok=True)

    found = False
    for obj in objects:
        if not obj.object_name.endswith(".parquet"):
            continue

        local_path = PARQUET_CACHE_DIR / obj.object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client.fget_object(BUCKET, obj.object_name, str(local_path))
        found = True

    if not found:
        return None

    return (prefix_dir / "**" / "*.parquet").as_posix().replace("'", "''")


def _duckdb_rows(sql: str, params: list | None = None) -> list[dict]:
    with duckdb.connect(database=":memory:") as conn:
        result = conn.execute(sql, params or [])
        columns = [column[0] for column in result.description]
        return [dict(zip(columns, row)) for row in result.fetchall()]


def _query_parquet_prefix(
    prefix: str,
    where_clauses: list[str] | None = None,
    params: list | None = None,
    order_by: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    parquet_glob = _sync_parquet_prefix(prefix)
    if parquet_glob is None:
        return []

    sql = f"SELECT * FROM read_parquet('{parquet_glob}', hive_partitioning=true)"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit is not None:
        sql += " LIMIT ?"
        params = [*(params or []), limit]

    return _duckdb_rows(sql, params)


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
    where_clauses = []
    params = []

    if risk_level:
        where_clauses.append("risk_level = ?")
        params.append(risk_level)
    if id_usuario:
        where_clauses.append("id_usuario = ?")
        params.append(id_usuario)
    if pais:
        where_clauses.append("pais_transacao = ?")
        params.append(pais)
    if motivo:
        where_clauses.append("list_contains(risk_reasons, ?)")
        params.append(motivo)
    if valor_minimo is not None:
        where_clauses.append("valor >= ?")
        params.append(valor_minimo)
    if data_inicio:
        where_clauses.append("CAST(COALESCE(CAST(data_processamento AS VARCHAR), SUBSTR(CAST(data_hora AS VARCHAR), 1, 10)) AS VARCHAR) >= ?")
        params.append(data_inicio)
    if data_fim:
        where_clauses.append("CAST(COALESCE(CAST(data_processamento AS VARCHAR), SUBSTR(CAST(data_hora AS VARCHAR), 1, 10)) AS VARCHAR) <= ?")
        params.append(data_fim)
    if decision:
        where_clauses.append("decision = ?")
        params.append(decision)

    return _query_parquet_prefix(
        GOLD_ALERTS_PREFIX,
        where_clauses=where_clauses,
        params=params,
        order_by="risk_score DESC, valor DESC",
        limit=limit,
    )


def _buscar_historico_usuario(id_usuario: str, limit: int = 20) -> list[dict]:
    return _query_parquet_prefix(
        SILVER_TRANSACTIONS_PREFIX,
        where_clauses=["id_usuario = ?"],
        params=[id_usuario],
        order_by="data_hora DESC",
        limit=limit,
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "bucket": BUCKET, "serving": "duckdb"}


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
    transacoes = _query_parquet_prefix(
        SILVER_TRANSACTIONS_PREFIX,
        where_clauses=["id_transacao = ?"],
        params=[id_transacao],
        limit=1,
    )
    if transacoes:
        return transacoes[0]

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
