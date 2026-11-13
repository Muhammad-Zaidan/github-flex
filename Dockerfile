FROM python:3.12-slim

# LibreOffice untuk PDF/ODT/RTF, Pandoc untuk HTML/Markdown/LaTeX/EPUB,
# dan font yang ukurannya setara Times New Roman, Arial, Calibri, Cambria.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libreoffice-writer-nogui pandoc \
    fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir python-docx lxml fastapi uvicorn python-multipart pymupdf
COPY cetakan ./cetakan

EXPOSE 8000
CMD ["python", "-m", "cetakan", "--host", "0.0.0.0", "--port", "8000"]
