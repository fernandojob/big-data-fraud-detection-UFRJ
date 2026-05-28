import json
import subprocess
import sys
import time
from urllib.request import urlopen


ROOT_COMMAND = ["docker", "compose"]


def run(command: list[str]):
    print(f"$ {' '.join(command)}")
    subprocess.run(command, check=True)


def wait_json(url: str, timeout_seconds: int = 90):
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            time.sleep(2)

    raise RuntimeError(f"Timeout aguardando {url}: {last_error}")


def wait_http(url: str, timeout_seconds: int = 90):
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(2)

    raise RuntimeError(f"Timeout aguardando {url}: {last_error}")


def main():
    transaction_count = sys.argv[1] if len(sys.argv) > 1 else "2000"

    run([*ROOT_COMMAND, "up", "-d", "--build", "minio"])
    wait_http("http://localhost:9000/minio/health/live")

    run([*ROOT_COMMAND, "run", "--rm", "-e", f"TRANSACTION_COUNT={transaction_count}", "spark"])

    run([*ROOT_COMMAND, "up", "-d", "--build", "api"])
    health = wait_json("http://localhost:8000/health")
    print(f"health: {health}")

    alertas = wait_json("http://localhost:8000/fraudes/top?limit=5")
    if not alertas:
        raise RuntimeError("A API nao retornou alertas em /fraudes/top")

    required_fields = {"id_transacao", "id_usuario", "risk_score", "risk_level", "risk_reasons", "decision"}
    missing = required_fields - set(alertas[0].keys())
    if missing:
        raise RuntimeError(f"Campos ausentes no alerta retornado: {sorted(missing)}")

    print(f"alertas_validados: {len(alertas)}")
    print("validacao_end_to_end: OK")


if __name__ == "__main__":
    main()
