from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    avg,
    col,
    collect_set,
    concat,
    count,
    current_date,
    expr,
    hour,
    lag,
    least,
    lit,
    rand,
    round as spark_round,
    size,
    stddev,
    to_date,
    when,
)
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)
import os

os.environ["HADOOP_CONF_DIR"] = ""
os.environ["YARN_CONF_DIR"] = ""

BUCKET = os.getenv("FRAUD_BUCKET", "fraudes")
S3_BASE_PATH = f"s3a://{BUCKET}"
USER_SEED_PATH = os.getenv("USER_SEED_PATH", "/app/seeds/usuarios.csv")
TRANSACTION_COUNT = int(os.getenv("TRANSACTION_COUNT", "1000000"))

spark = (
    SparkSession.builder
    .appName("FraudDetectionMBA")
    .config("spark.hadoop.fs.s3a.connection.timeout", "60000")
    .config("spark.hadoop.fs.s3a.connection.establish.timeout", "5000")
    .config("spark.hadoop.fs.s3a.connection.request.timeout", "60000")
    .config("spark.hadoop.fs.s3a.socket.timeout", "60000")
    .config(
        "spark.jars.packages",
        "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262",
    )
    .config("spark.hadoop.fs.s3a.endpoint", os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000"))
    .config("spark.hadoop.fs.s3a.access.key", os.getenv("MINIO_ACCESS_KEY", "admin"))
    .config("spark.hadoop.fs.s3a.secret.key", os.getenv("MINIO_SECRET_KEY", "admin123"))
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.configuration", "")
    .getOrCreate()
)


def carregar_usuarios():
    schema = StructType(
        [
            StructField("user_seq", IntegerType(), False),
            StructField("id_usuario", StringType(), False),
            StructField("pais_residencia", StringType(), False),
            StructField("cidade_residencia", StringType(), False),
            StructField("latitude_base", DoubleType(), False),
            StructField("longitude_base", DoubleType(), False),
            StructField("perfil", StringType(), False),
            StructField("device_principal", StringType(), False),
            StructField("ticket_medio", DoubleType(), False),
            StructField("renda_faixa", StringType(), False),
            StructField("criado_em", StringType(), False),
        ]
    )

    return (
        spark.read.option("header", True)
        .schema(schema)
        .csv(USER_SEED_PATH)
        .withColumn("criado_em", to_date(col("criado_em")))
    )


def gerar_transacoes(usuarios):
    paises = spark.createDataFrame(
        [
            ("BR", "Sao Paulo", -23.5505, -46.6333),
            ("US", "New York", 40.7128, -74.0060),
            ("GB", "London", 51.5074, -0.1278),
            ("FR", "Paris", 48.8566, 2.3522),
            ("DE", "Berlin", 52.5200, 13.4050),
            ("IN", "Mumbai", 19.0760, 72.8777),
            ("CN", "Shanghai", 31.2304, 121.4737),
            ("JP", "Tokyo", 35.6762, 139.6503),
            ("CA", "Toronto", 43.6532, -79.3832),
            ("AU", "Sydney", -33.8688, 151.2093),
        ],
        ["pais_transacao", "cidade_transacao", "latitude", "longitude"],
    )

    base = (
        spark.range(0, TRANSACTION_COUNT)
        .withColumn("id_transacao", concat(lit("tx_"), col("id").cast("string")))
        .withColumn("user_seq", ((col("id") % lit(10000)) + lit(1)).cast("int"))
        .join(usuarios, "user_seq", "inner")
    )

    pais_transacao = (
        when(rand(11) < when(col("perfil") == "VIAJANTE", 0.55).otherwise(0.86), col("pais_residencia"))
        .when(rand(12) < 0.10, "US")
        .when(rand(13) < 0.20, "GB")
        .when(rand(14) < 0.30, "FR")
        .when(rand(15) < 0.40, "DE")
        .when(rand(16) < 0.50, "IN")
        .when(rand(17) < 0.60, "CN")
        .when(rand(18) < 0.72, "JP")
        .when(rand(19) < 0.84, "CA")
        .otherwise("AU")
    )

    return (
        base.withColumn("pais_transacao", pais_transacao)
        .join(paises, "pais_transacao", "left")
        .withColumn(
            "valor",
            spark_round(
                when(rand(21) < 0.92, rand(22) * col("ticket_medio") * 2)
                .when(rand(23) < 0.985, rand(24) * col("ticket_medio") * 5)
                .otherwise(rand(25) * col("ticket_medio") * 14),
                2,
            ),
        )
        .withColumn("device", when(rand(31) < 0.87, col("device_principal")).otherwise(when(col("device_principal") == "mobile", "web").otherwise("mobile")))
        .withColumn("tentativas", when(rand(41) < 0.91, 1).when(rand(42) < 0.98, 2).otherwise((rand(43) * 5).cast("int") + 3))
        .withColumn(
            "data_hora",
            expr(
                """
                current_timestamp()
                - (rand(51) * 30) * interval 1 day
                - (rand(52) * 24) * interval 1 hour
                - (rand(53) * 60) * interval 1 minute
                - (rand(54) * 60) * interval 1 second
                """
            ),
        )
        .withColumn("data_processamento", current_date())
        .withColumn("hora", hour(col("data_hora")))
        .select(
            "id_transacao",
            "id_usuario",
            "perfil",
            "pais_residencia",
            "cidade_residencia",
            "pais_transacao",
            "cidade_transacao",
            "latitude",
            "longitude",
            "valor",
            "ticket_medio",
            "device",
            "device_principal",
            "tentativas",
            "data_hora",
            "data_processamento",
            "hora",
        )
    )


def calcular_features_comportamentais(transacoes):
    janela_usuario = Window.partitionBy("id_usuario").orderBy("data_hora")
    janela_historica = janela_usuario.rowsBetween(Window.unboundedPreceding, -1)
    janela_1h = Window.partitionBy("id_usuario").orderBy("data_hora_ts").rangeBetween(-3600, 0)
    janela_24h = Window.partitionBy("id_usuario").orderBy("data_hora_ts").rangeBetween(-86400, 0)

    enriquecidas = (
        transacoes.withColumn("data_hora_ts", col("data_hora").cast("long"))
        .withColumn("pais_anterior", lag("pais_transacao").over(janela_usuario))
        .withColumn("cidade_anterior", lag("cidade_transacao").over(janela_usuario))
        .withColumn("latitude_anterior", lag("latitude").over(janela_usuario))
        .withColumn("longitude_anterior", lag("longitude").over(janela_usuario))
        .withColumn("data_hora_anterior", lag("data_hora").over(janela_usuario))
        .withColumn("device_anterior", lag("device").over(janela_usuario))
        .withColumn("media_valor_usuario", avg("valor").over(janela_historica))
        .withColumn("desvio_valor_usuario", stddev("valor").over(janela_historica))
        .withColumn("qtd_transacoes_1h", count("id_transacao").over(janela_1h))
        .withColumn("qtd_paises_24h", size(collect_set("pais_transacao").over(janela_24h)))
        .withColumn(
            "minutos_desde_ultima_transacao",
            spark_round((col("data_hora").cast("long") - col("data_hora_anterior").cast("long")) / 60, 2),
        )
    )

    distancia = (
        lit(6371)
        * lit(2)
        * expr(
            """
            asin(sqrt(
                pow(sin((radians(latitude - latitude_anterior)) / 2), 2) +
                cos(radians(latitude_anterior)) * cos(radians(latitude)) *
                pow(sin((radians(longitude - longitude_anterior)) / 2), 2)
            ))
            """
        )
    )

    return (
        enriquecidas.withColumn(
            "distancia_km_desde_ultima_transacao",
            when(col("latitude_anterior").isNull(), None).otherwise(spark_round(distancia, 2)),
        )
        .withColumn(
            "velocidade_kmh_entre_transacoes",
            when(
                col("minutos_desde_ultima_transacao") > 0,
                spark_round(col("distancia_km_desde_ultima_transacao") / (col("minutos_desde_ultima_transacao") / 60), 2),
            ),
        )
        .withColumn("valor_acima_do_perfil", col("valor") > (col("ticket_medio") * 4))
        .withColumn("device_novo", col("device") != col("device_principal"))
        .withColumn("pais_novo_para_usuario", (col("pais_transacao") != col("pais_residencia")) & (col("pais_anterior").isNotNull()))
        .withColumn("frequencia_anormal", (col("minutos_desde_ultima_transacao").between(0, 5)) | (col("qtd_transacoes_1h") >= 5))
        .drop("data_hora_ts")
    )


def calcular_risco(transacoes):
    impossible_travel = col("velocidade_kmh_entre_transacoes") > 900
    valor_acima = col("valor_acima_do_perfil")
    device_novo = col("device_novo")
    pais_novo = col("pais_novo_para_usuario")
    tentativas_altas = col("tentativas") >= 3
    horario_incomum = col("hora") < 6
    frequencia_anormal = col("frequencia_anormal")

    score = least(
        lit(100),
        when(impossible_travel, 45).otherwise(0)
        + when(valor_acima, 25).otherwise(0)
        + when(device_novo, 10).otherwise(0)
        + when(pais_novo, 10).otherwise(0)
        + when(tentativas_altas, 20).otherwise(0)
        + when(horario_incomum, 8).otherwise(0)
        + when(frequencia_anormal, 12).otherwise(0),
    )

    return (
        transacoes.withColumn("risk_score", score)
        .withColumn("reason_impossible_travel", when(impossible_travel, lit("IMPOSSIBLE_TRAVEL")))
        .withColumn("reason_value_above_profile", when(valor_acima, lit("VALUE_ABOVE_USER_PROFILE")))
        .withColumn("reason_new_device", when(device_novo, lit("NEW_DEVICE")))
        .withColumn("reason_new_country", when(pais_novo, lit("NEW_COUNTRY_FOR_USER")))
        .withColumn("reason_high_attempt_count", when(tentativas_altas, lit("HIGH_ATTEMPT_COUNT")))
        .withColumn("reason_unusual_hour", when(horario_incomum, lit("UNUSUAL_TRANSACTION_HOUR")))
        .withColumn("reason_abnormal_frequency", when(frequencia_anormal, lit("ABNORMAL_FREQUENCY")))
        .withColumn(
            "risk_reasons",
            expr(
                """
                filter(array(
                    reason_impossible_travel,
                    reason_value_above_profile,
                    reason_new_device,
                    reason_new_country,
                    reason_high_attempt_count,
                    reason_unusual_hour,
                    reason_abnormal_frequency
                ), reason -> reason is not null)
                """
            ),
        )
        .drop(
            "reason_impossible_travel",
            "reason_value_above_profile",
            "reason_new_device",
            "reason_new_country",
            "reason_high_attempt_count",
            "reason_unusual_hour",
            "reason_abnormal_frequency",
        )
        .withColumn(
            "risk_level",
            when(col("risk_score") >= 85, "CRITICAL")
            .when(col("risk_score") >= 60, "HIGH")
            .when(col("risk_score") >= 35, "MEDIUM")
            .otherwise("LOW"),
        )
        .withColumn("risk_reasons", risk_reasons)
    )


def salvar_resultados(usuarios, transacoes_brutas, transacoes_enriquecidas):
    alertas = transacoes_enriquecidas.filter(col("risk_level").isin("MEDIUM", "HIGH", "CRITICAL"))

    usuarios.write.mode("overwrite").parquet(f"{S3_BASE_PATH}/bronze/usuarios")
    transacoes_brutas.write.mode("overwrite").partitionBy("data_processamento").parquet(f"{S3_BASE_PATH}/bronze/transacoes")
    transacoes_enriquecidas.write.mode("overwrite").partitionBy("data_processamento").parquet(
        f"{S3_BASE_PATH}/silver/transacoes_enriquecidas"
    )
    alertas.write.mode("overwrite").partitionBy("data_processamento", "risk_level").parquet(
        f"{S3_BASE_PATH}/gold/alertas_fraude"
    )


print("Carregando usuarios sinteticos...")
usuarios_df = carregar_usuarios()

print("Gerando transacoes...")
transacoes_df = gerar_transacoes(usuarios_df)

print("Calculando features comportamentais...")
transacoes_enriquecidas_df = calcular_features_comportamentais(transacoes_df)

print("Calculando score de risco...")
transacoes_com_risco_df = calcular_risco(transacoes_enriquecidas_df)

print("Salvando camadas bronze, silver e gold em Parquet...")
salvar_resultados(usuarios_df, transacoes_df, transacoes_com_risco_df)

print("Pipeline finalizado com sucesso!")
