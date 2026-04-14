import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memoria.db")


class MemoryInterface:
    """Gerencia a persistência de triplas (sujeito, relação, objeto) no SQLite."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._criar_banco()

    def _criar_banco(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS triplas (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    sujeito          TEXT NOT NULL,
                    relacao          TEXT NOT NULL,
                    objeto           TEXT NOT NULL,
                    data_referencia  TEXT,
                    fonte            TEXT,
                    UNIQUE(sujeito, relacao, objeto)
                )
            """)
            # Migração: adiciona coluna fonte se o banco já existia sem ela
            try:
                conn.execute("ALTER TABLE triplas ADD COLUMN fonte TEXT")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def inserir_tripla(self, sujeito, relacao, objeto, data_referencia=None, fonte=None):
        """Insere uma tripla ignorando duplicatas. Retorna 1 se inseriu, 0 se já existia."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO triplas (sujeito, relacao, objeto, data_referencia, fonte) VALUES (?, ?, ?, ?, ?)",
                (sujeito.strip(), relacao.strip(), objeto.strip(), data_referencia, fonte)
            )
            conn.commit()
            return cur.rowcount

    def inserir_lote(self, triplas: list, data_referencia=None, fonte=None) -> int:
        """Insere uma lista de dicts com chaves sujeito/relacao/objeto. Retorna o total inserido."""
        inseridas = 0
        for t in triplas:
            if all(k in t for k in ("sujeito", "relacao", "objeto")):
                inseridas += self.inserir_tripla(
                    t["sujeito"], t["relacao"], t["objeto"],
                    data_referencia=data_referencia, fonte=fonte
                )
        return inseridas

    def listar_top_por_projeto(self, n_por_projeto=10) -> dict:
        """
        Retorna as N triplas mais recentes de cada projeto (fonte).
        Retorna um dict: {fonte: [triplas]}.
        """
        query = """
            SELECT sujeito, relacao, objeto, data_referencia, fonte
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY fonte ORDER BY data_referencia DESC, id ASC) AS rn
                FROM triplas
                WHERE fonte IS NOT NULL
            )
            WHERE rn <= ?
            ORDER BY fonte, data_referencia DESC, id ASC
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, (n_por_projeto,)).fetchall()

        resultado = {}
        for r in rows:
            fonte = r[4]
            if fonte not in resultado:
                resultado[fonte] = []
            resultado[fonte].append({
                "sujeito": r[0], "relacao": r[1], "objeto": r[2], "data": r[3]
            })
        return resultado

    def buscar_fuzzy(self, termos: list, limite=40) -> list:
        """Busca por LIKE em sujeito, relação e objeto para uma lista de termos."""
        if not termos:
            return []
        condicoes = " OR ".join(
            ["(sujeito LIKE ? OR relacao LIKE ? OR objeto LIKE ?)"] * len(termos)
        )
        params = []
        for t in termos:
            p = f"%{t}%"
            params += [p, p, p]
        query = f"""
            SELECT DISTINCT sujeito, relacao, objeto, data_referencia, fonte
            FROM triplas
            WHERE {condicoes}
            ORDER BY data_referencia DESC
            LIMIT ?
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(query, params + [limite]).fetchall()
        return [{"sujeito": r[0], "relacao": r[1], "objeto": r[2], "data": r[3], "fonte": r[4]} for r in rows]

    def listar_recentes(self, limite=100) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT sujeito, relacao, objeto, data_referencia
                FROM triplas ORDER BY data_referencia DESC LIMIT ?
            """, (limite,)).fetchall()
        return [{"sujeito": r[0], "relacao": r[1], "objeto": r[2], "data": r[3]} for r in rows]

    def contar(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM triplas").fetchone()[0]
