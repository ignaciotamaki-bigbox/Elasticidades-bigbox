"""
Script de prueba Día 1.

Objetivo: verificar que el Service Account puede descargar uno de los Excels
desde Google Drive y leerlo con pandas.

Uso:
    1. Poner credentials.json en la misma carpeta que este script.
    2. Crear un archivo .env al lado con:
         FILE_ID_AR=<id_del_excel_AR_en_drive>
    3. Correr:  python test_download.py

Si imprime las primeras filas del Excel, el setup de credenciales funciona
y podemos pasar al Día 2.
"""

import io
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- Config ----------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
CREDENTIALS_PATH = SCRIPT_DIR / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

load_dotenv(SCRIPT_DIR / ".env")
FILE_ID_AR = os.getenv("FILE_ID_AR")


# --- Checks de setup -------------------------------------------------------

def preflight():
    problems = []

    if not CREDENTIALS_PATH.exists():
        problems.append(
            f"No encuentro credentials.json en {CREDENTIALS_PATH}.\n"
            f"     Descargalo del Service Account y ponelo ahí."
        )

    if not FILE_ID_AR:
        problems.append(
            "Falta FILE_ID_AR. Creá un archivo .env al lado del script con:\n"
            "         FILE_ID_AR=<el_id_del_excel_AR>\n"
            "     El ID lo sacás de la URL del archivo en Drive:\n"
            "     https://drive.google.com/file/d/<ESTO_ES_EL_ID>/view"
        )

    if problems:
        print("ERRORES DE SETUP:\n")
        for p in problems:
            print(f"  - {p}\n")
        sys.exit(1)


# --- Descarga --------------------------------------------------------------

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def download_file(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"  descargando... {int(status.progress() * 100)}%")
    return buffer.getvalue()


# --- Main ------------------------------------------------------------------

def main():
    preflight()

    print(f"Autenticando con {CREDENTIALS_PATH.name}...")
    service = get_drive_service()

    print(f"Bajando archivo {FILE_ID_AR}...")
    content = download_file(service, FILE_ID_AR)
    print(f"OK: {len(content):,} bytes descargados\n")

    # Leer todas las hojas para entender la estructura
    print("Hojas del Excel:")
    xls = pd.ExcelFile(io.BytesIO(content))
    for name in xls.sheet_names:
        print(f"  - {name}")

    # Mostrar preview de la primera hoja
    first_sheet = xls.sheet_names[0]
    print(f"\nPreview de '{first_sheet}':")
    df = pd.read_excel(io.BytesIO(content), sheet_name=first_sheet)
    print(f"  Columnas: {list(df.columns)}")
    print(f"  Filas: {len(df)}")
    print(f"\nPrimeras 5 filas:")
    print(df.head().to_string())

    print("\n[OK] Todo funciona. Listos para el Dia 2.")


if __name__ == "__main__":
    main()
