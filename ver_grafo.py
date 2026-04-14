"""
Ferramenta de inspeção do grafo de conhecimento (memoria.db).

Uso:
  python ver_grafo.py                  # resumo geral
  python ver_grafo.py projeto          # filtra por nome de projeto
  python ver_grafo.py "Marco Antonio"  # filtra por qualquer termo
"""

import sys
import os
from memory_interface import MemoryInterface, DB_PATH

SEP = "=" * 60
SEP2 = "-" * 60

def _nome_curto(caminho: str) -> str:
    ignorar = {
        "agenda.md", "Agenda.md", "administrativo", "admin",
        "artigo", "reunioes", "03_produtos", "jobs", "projetosAtivos"
    }
    partes = caminho.replace("\\", "/").split("/")
    for parte in reversed(partes[:-1]):
        if parte and parte not in ignorar:
            return parte
    return partes[-2]


def exibir_por_projeto(mem: MemoryInterface):
    print(f"\n{SEP}")
    print(f"  GRAFO DE CONHECIMENTO — por projeto")
    print(f"  Banco: {DB_PATH}")
    print(f"  Total de triplas: {mem.contar()}")
    print(SEP)

    por_projeto = mem.listar_top_por_projeto(n_por_projeto=20)
    if not por_projeto:
        print("  (banco vazio)")
        return

    for fonte, triplas in por_projeto.items():
        print(f"\n[{_nome_curto(fonte)}]")
        print(SEP2)
        for t in triplas:
            print(f"  {t['sujeito']:<30} --[{t['relacao']}]--> {t['objeto']}  ({t['data']})")


def exibir_busca(mem: MemoryInterface, termo: str):
    print(f"\n{SEP}")
    print(f"  BUSCA: \"{termo}\"")
    print(SEP)

    resultados = mem.buscar_fuzzy([termo], limite=50)
    if not resultados:
        print(f"  Nenhuma tripla encontrada para \"{termo}\".")
        return

    fonte_atual = None
    for t in resultados:
        fonte = t.get("fonte", "")
        nome = _nome_curto(fonte) if fonte else "?"
        if nome != fonte_atual:
            print(f"\n[{nome}]")
            fonte_atual = nome
        print(f"  {t['sujeito']:<30} --[{t['relacao']}]--> {t['objeto']}  ({t['data']})")

    print(f"\n  Total: {len(resultados)} triplas encontradas.")


if __name__ == "__main__":
    os.system("cls")

    if not os.path.exists(DB_PATH):
        print("Banco memoria.db não encontrado. Execute agente_v2.py primeiro.")
        sys.exit(1)

    mem = MemoryInterface()

    if len(sys.argv) > 1:
        termo = " ".join(sys.argv[1:])
        exibir_busca(mem, termo)
    else:
        exibir_por_projeto(mem)
