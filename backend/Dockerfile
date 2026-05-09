FROM python:3.10-slim

# Diretório da aplicação
WORKDIR /app

# Copia dependências
COPY requirements.txt .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Expõe a porta da API
EXPOSE 8000

# Comando para iniciar a API
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]