from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
import json
import os

app = FastAPI()

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

@app.get("/fraudes/top")
def get_fraudes():
    objects = client.list_objects(BUCKET, prefix="output/", recursive=True)
    resultado = []
    for obj in objects:
        if not obj.object_name.endswith(".json"):
            continue
        response = client.get_object(BUCKET, obj.object_name)
        try:
            for linha in response:
                linha_str = linha.decode("utf-8").strip()
                if linha_str:
                    resultado.append(json.loads(linha_str))
        finally:
            response.close()
            response.release_conn()

    resultado = sorted(resultado, key=lambda x: x.get("valor", 0), reverse=True)
    return resultado[:50]