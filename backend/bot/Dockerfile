# backend/bot/Dockerfile

FROM python:3.11-slim

# Устанавливаем переменные окружения для корректной работы с UTF-8 и для автоматических установок
ENV PYTHONIOENCODING=UTF-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Устанавливаем системные зависимости, обновляем pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    fonts-dejavu-core \
    dvipng \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    git \
    # Очистка кэша apt
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # Обновляем сам pip до последней версии
    && pip install --upgrade pip

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код нашего приложения в рабочую директорию /app
COPY bot.py .
COPY animate_code.py .
COPY youtube_client.py .

# Создаем директорию для видео
RUN mkdir -p static/videos

# Запуск бота
CMD ["python", "bot.py"]