import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

def audit_database():
    db_url = os.getenv("DATABASE_URL")
    # SQLAlchemy usa un formato ligeramente distinto, cambiamos postgresql:// por postgresql+psycopg2://
    engine = create_engine(db_url.replace("postgresql://", "postgresql+psycopg2://"))
    
    print("🔍 Consultando el Tanque de Datos...")
    
    # 1. Contar total de registros
    count_df = pd.read_sql("SELECT COUNT(*) FROM xauusd_m1", engine)
    total_rows = count_df.iloc[0, 0]
    
    # 2. Ver las últimas 5 velas ingresadas
    data_df = pd.read_sql("SELECT * FROM xauusd_m1 ORDER BY time DESC LIMIT 5", engine)
    
    print("-" * 30)
    print(f"📊 ESTADO DEL TANQUE: {total_rows} velas encontradas.")
    print("-" * 30)
    print("ÚLTIMOS DATOS REGISTRADOS (XAUUSD):")
    print(data_df)
    print("-" * 30)

if __name__ == "__main__":
    audit_database()