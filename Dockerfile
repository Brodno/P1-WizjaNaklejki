# STAGE 1: Builder (Fabryka - tu budujemy ciężkie rzeczy)
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 
    PYTHONUNBUFFERED=1

WORKDIR /build

# Instalujemy narzędzia kompilacji
RUN apt-get update && apt-get install -y --no-install-recommends 
    build-essential 
    gcc 
    && rm -rf /var/lib/apt/lists/*

# Kopiujemy i instalujemy zależności do dedykowanego folderu
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# STAGE 2: Runner (Sklep - tu jest tylko gotowy, lekki produkt)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 
    PYTHONUNBUFFERED=1 
    PATH="/app/.local/bin:$PATH"

WORKDIR /app

# Instalujemy TYLKO niezbędne biblioteki systemowe dla OpenCV i EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends 
    libgl1-mesa-glx 
    libglib2.0-0 
    && rm -rf /var/lib/apt/lists/*

# Kopiujemy zainstalowane biblioteki z buildera
COPY --from=builder /install /usr/local

# Tworzymy bezpiecznego użytkownika (Non-Root)
RUN useradd -m -u 1000 appuser && 
    chown -R appuser:appuser /app

# Kopiujemy kod aplikacji jako appuser
COPY --chown=appuser:appuser . .

USER appuser

# Streamlit działa na tym porcie
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
