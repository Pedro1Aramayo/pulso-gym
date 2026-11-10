import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

def conectar_bd():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
        port=os.getenv('POSTGRES_PORT', '5433'),
        dbname=os.getenv('POSTGRES_DB', 'asistencia_gimnasio'),
        user=os.getenv('POSTGRES_USER', 'gimnasio'),
        password=os.getenv('POSTGRES_PASSWORD'), connect_timeout=5,
        options="-c timezone=America/Argentina/Buenos_Aires -c statement_timeout=8000 -c lock_timeout=5000")
