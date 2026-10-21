FROM mcr.microsoft.com/playwright/python:v1.56.0-noble
WORKDIR /app
RUN pip install --no-cache-dir playwright==1.56.0
COPY screenshot_service/server.py /app/server.py
USER pwuser
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "/app/server.py"]
