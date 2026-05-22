# Sistema de Detecção de Fraudes com Big Data

Projeto acadêmico desenvolvido no contexto da pós-graduação em Engenharia de Software da Universidade Federal do Rio de Janeiro (UFRJ). A aplicação simula um pipeline de Big Data para geração, processamento, armazenamento e visualização de transações financeiras suspeitas.

O sistema combina Apache Spark, MinIO compatível com S3, FastAPI e Angular para demonstrar uma arquitetura desacoplada entre processamento, armazenamento, exposição de dados e interface analítica.

## Arquitetura

```text
Apache Spark (ETL)
        |
        v
MinIO Object Storage (S3A)
        |
        v
FastAPI
        |
        v
Angular + Chart.js
```

### Componentes

- `spark/`: aplicação PySpark responsável por ler uma seed sintética de usuários, gerar 1.000.000 de transações simuladas, calcular features comportamentais, aplicar score de risco e gravar os resultados no MinIO via protocolo `s3a://`.
- `spark/seeds/usuarios.csv`: base cadastral sintética com 10.000 usuários, usada apenas para fins educacionais. Em um ambiente real, essa origem viria de CRM, core banking, e-commerce, sistema de contas ou data warehouse.
- `backend/`: API FastAPI que lê arquivos Parquet da camada Gold no bucket `fraudes` do MinIO e expõe alertas, filtros, detalhe de transação e histórico por usuário.
- `frontend/`: dashboard Angular que consome a API, exibe indicadores, gráfico por score de risco e tabela paginada.
- `docker-compose.yml`: orquestra MinIO, API e job Spark em containers.

## Pipeline de Dados

1. O Spark lê uma seed sintética de usuários em CSV.
2. O Spark gera transações sintéticas associadas a esses usuários.
3. O pipeline calcula features comportamentais por usuário, como país anterior, dispositivo novo, tempo desde a última transação, distância percorrida e velocidade estimada.
4. As transações recebem `risk_score`, `risk_level` e `risk_reasons`.
5. Os dados são gravados no MinIO em Parquet nas camadas Bronze, Silver e Gold.
6. A API lê a camada Gold e expõe os alertas para o frontend.
7. O frontend renderiza indicadores, gráfico por score e tabela com motivos explicáveis.

## Regras de Fraude

O projeto agora usa score explicável em vez de uma classificação fixa por transação isolada.

- `risk_score`: pontuação de 0 a 100.
- `risk_level`: `LOW`, `MEDIUM`, `HIGH` ou `CRITICAL`.
- `risk_reasons`: lista de motivos que explicam o alerta.

Motivos atualmente simulados:

- `IMPOSSIBLE_TRAVEL`: deslocamento fisicamente improvável entre duas transações do mesmo usuário.
- `VALUE_ABOVE_USER_PROFILE`: valor acima do perfil histórico do usuário.
- `NEW_DEVICE`: dispositivo diferente do principal.
- `NEW_COUNTRY_FOR_USER`: país diferente do perfil usual.
- `HIGH_ATTEMPT_COUNT`: quantidade elevada de tentativas.
- `UNUSUAL_TRANSACTION_HOUR`: transação em horário incomum.
- `ABNORMAL_FREQUENCY`: transações em intervalo muito curto.

## Camadas do Data Lake

Os dados são persistidos em Parquet no MinIO:

```text
s3a://fraudes/bronze/usuarios/
s3a://fraudes/bronze/transacoes/
s3a://fraudes/silver/transacoes_enriquecidas/
s3a://fraudes/gold/alertas_fraude/
```

A camada Gold é particionada por `data_processamento` e `risk_level`.

## Tecnologias

- Apache Spark 3.5.0
- PySpark
- MinIO
- FastAPI
- Uvicorn
- Angular 21
- Chart.js
- Docker e Docker Compose

## Estrutura do Projeto

```text
.
├── backend/
│   ├── api.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   ├── angular.json
│   ├── package.json
│   └── package-lock.json
├── spark/
│   ├── app_spark.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## Como Executar

### 1. Subir infraestrutura, API e processamento

Na raiz do projeto:

```bash
docker compose up --build
```

Esse comando inicia:

- MinIO em `http://localhost:9001`
- API FastAPI em `http://localhost:8000`
- Job Spark que gera e grava os dados no bucket `fraudes`

Credenciais padrão do MinIO:

```text
Usuário: admin
Senha: admin123
```

### 2. Validar a API

Depois que o processamento Spark finalizar, acesse:

```text
http://localhost:8000/fraudes/top
```

O endpoint retorna os 50 alertas com maior score de risco.

Endpoints disponíveis:

```text
GET /health
GET /fraudes
GET /fraudes/top
GET /transacoes/{id_transacao}
GET /usuarios/{id_usuario}/historico
GET /usuarios/{id_usuario}/perfil-risco
```

Filtros suportados em `/fraudes`:

```text
risk_level
id_usuario
pais
motivo
valor_minimo
data_inicio
data_fim
limit
```

### 3. Executar o frontend

Em outro terminal:

```bash
cd frontend
npm install
npm start
```

Acesse:

```text
http://localhost:4200
```

## Execução Manual do Spark

Também é possível executar o processamento Spark diretamente, desde que o MinIO esteja disponível:

```bash
cd spark
pip install -r requirements.txt
python app_spark.py
```

Em execução local fora do Docker, ajuste o endpoint S3A em `spark/app_spark.py` caso necessário, pois o código usa `http://minio:9000`, nome resolvido pela rede do Docker Compose.

## Execução Manual da API

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

Variáveis de ambiente suportadas:

```text
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin123
```

## Evidências Visuais

![Dashboard com gráfico](./frontend/public/grafico-frontend.png)

![Dashboard com tabela](./frontend/public/tabela-frontend.png)

![Bucket no MinIO](./frontend/public/minio-bucket.png)

## Observações

- O projeto usa MinIO para simular um Data Lake compatível com S3.
- A arquitetura separa processamento e armazenamento, permitindo evolução para serviços como AWS S3, EMR ou Databricks.
- O frontend espera que a API esteja disponível em `http://localhost:8000`.
- A seed de usuários em CSV é pequena e versionada para facilitar a demonstração.
- As transações e alertas são dados analíticos de maior volume e são gravados em Parquet no MinIO.
- Os dados gerados pelo Spark são descartáveis e não devem ser versionados no Git.
