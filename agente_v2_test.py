import os
import datetime

from agente_v2 import AgenteMarcoV2, _nome_curto

os.system("cls")


class AgenteMarcoV2Test(AgenteMarcoV2):
    """Versão de teste: imprime o prompt final sem chamar a API de briefing."""

    def gerar_briefing(self) -> str:
        print("[1/4] Processando projetos e atualizando grafo...")
        self.processar_projetos()

        print("[2/4] Buscando agenda e tarefas...")
        agenda = self._get_agenda()
        tarefas = self._get_tarefas()

        print("[3/4] Montando contexto do grafo...")
        contexto_grafo = self._montar_contexto_grafo(agenda)

        data_hoje = datetime.datetime.now().strftime("%d/%m/%Y")

        prompt = f"""
Você é o Secretário Executivo do Marco Antonio.
Hoje é {data_hoje}. Seja proativo, direto e com tom de parceria — sem ser servil.

FONTES DE DADOS:

[AGENDA GOOGLE — próximos compromissos]
{agenda}

[TAREFAS PESSOAIS (Google Tasks)]
{tarefas}

[MEMÓRIA DOS PROJETOS]
{contexto_grafo}

INSTRUÇÕES:
- Concilie vida pessoal (tarefas, saúde, família) com os projetos profissionais.
- Cruze compromissos da agenda com o estado atual de cada projeto.
- Detecte prazos críticos, dependências e oportunidades de avanço.
- Gere um briefing matinal estruturado em:
  [AGENDA] — compromissos do dia com contexto relevante
  [PROJETOS] — status rápido de cada frente ativa
  [TAREFAS] — o que precisa ser feito hoje (pessoal + profissional)
  [FOCO DO DIA] — prioridade número 1 com justificativa
  [PONTOS DE ATENÇÃO] — prazos críticos e riscos detectados
"""

        sep = "=" * 60
        print(f"\n{sep}")
        print("PROMPT ENVIADO À API (DRY RUN — sem chamada ao Gemini)")
        print(sep)
        print(prompt)
        print(sep)

        por_projeto = self.memory.listar_top_por_projeto()
        print(f"Projetos no grafo: {len(por_projeto)}")
        for fonte, triplas in por_projeto.items():
            print(f"  {_nome_curto(fonte)}: {len(triplas)} triplas recentes")
        print(f"Total de triplas no banco: {self.memory.contar()}")
        print(sep)

        return "[DRY RUN] Prompt impresso. Nenhuma chamada à API foi feita."


if __name__ == "__main__":
    agente = AgenteMarcoV2Test()
    resultado = agente.gerar_briefing()
    print(f"\n{resultado}")
