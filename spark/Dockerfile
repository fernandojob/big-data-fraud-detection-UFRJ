FROM apache/spark:3.5.0

USER root

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python3", "app_spark.py"]