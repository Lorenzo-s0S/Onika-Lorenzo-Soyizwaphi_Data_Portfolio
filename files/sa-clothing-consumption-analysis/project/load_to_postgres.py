"""Optional: load the processed panel into PostgreSQL and run queries.sql.
Setup:  set DATABASE_URL, e.g. postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME  (free Supabase/Neon instance works)
Run:    python analysis.py && python load_to_postgres.py
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent ## import only works like this for some reason

engine = create_engine(os.environ["DATABASE_URL"])
df = pd.read_csv(BASE / "data" / "processed" / "panel.csv", parse_dates=["date"]) ## __path__ might be the problem
df.to_sql("clothing_consumption", engine, if_exists="replace", index=False)   # reproducible: table rebuilt each run
print(f"Loaded {len(df)} rows into clothing_consumption")

for query in open(BASE /"queries.sql", encoding="utf-8").read().split(";"):
    if query.strip():
        print(pd.read_sql(text(query), engine).to_string(index=False), "\n")
