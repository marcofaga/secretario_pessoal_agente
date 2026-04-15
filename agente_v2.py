import os
import json
import datetime

import pyperclip
import google.generativeai as genai
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from graph_miner import GraphMiner
from memory_interface import MemoryInterface

# ---------------------------------------------------------------------------
# Configuração — chave lida do arquivo .env (nunca versionar o .env)
# ---------------------------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LOG_FILE = os.path.join(BASE_DIR, "log.json")


class AgenteMarcoV2:
    """Secretário Executivo com Memória de Grafo (v2.0)."""

    PROJETOS = [
        "G:/Meu Drive/MAFData/projetosAtivos/20251009 - CADE PNUD/03_produtos/administrativo/agenda.md",
        "G:/Meu Drive/RadioOne/Agenda.md",
        "G:/Meu Drive/MAFData/projetosAtivos/2303_posdoc_fgv/jobs/a38 - Distancia e Abstencao Eleitoral Luna/admin/Agenda.md",
        "G:/Meu Drive/MAFData/projetosAtivos/2303_posdoc_fgv/jobs/a31 - Rede Neural e Despesa de Campanha/artigo/Agenda.md",
        "G:/Meu Drive/MAFData/projetosAtivos/2303_posdoc_fgv/jobs/a011 - IC Mudancas nas Regras/reunioes/Agenda.md",
        "G:/Meu Drive/MAFData/projetosAtivos/2303_posdoc_fgv/jobs/a34 - Funcionarios Publicos/Agenda.md",
        "G:/Meu Drive/MAFData/projetosAtivos/2303_posdoc_fgv/jobs/a39 - Experimento Eleições/agenda.md",
        "G:/Meu Drive/MAFData/projetosAtivos/imoveis_bucci/agenda.md",
    ]

    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)

        self._model_miner = genai.GenerativeModel("gemini-2.5-flash-lite")
        self._model_briefing = genai.GenerativeModel("gemini-2.5-flash-lite")

        self.memory = MemoryInterface()
        self.miner = GraphMiner(self._model_miner)
        self.creds = self._autenticar()
        self.state = self._carregar_state()

    # ------------------------------------------------------------------
    # Autenticação Google
    # ------------------------------------------------------------------

    def _autenticar(self):
        creds = None
        token_path = os.path.join(BASE_DIR, "token.json")
        creds_path = os.path.join(BASE_DIR, "credentials.json")

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return creds

    # ------------------------------------------------------------------
    # Estado persistente (state.json)
    # ------------------------------------------------------------------

    def _carregar_state(self) -> dict:
        if os.path.exists(STATE_FILE):
            for enc in ("utf-8", "utf-8-sig", "utf-16"):
                try:
                    with open(STATE_FILE, "r", encoding=enc) as f:
                        return json.load(f)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            print("  [Aviso] state.json corrompido — reiniciando estado.")
        return {"arquivos": {}}

    def _salvar_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Processamento incremental dos projetos
    # ------------------------------------------------------------------

    def processar_projetos(self):
        """Verifica mudanças nos arquivos .md e minera novas triplas."""
        hoje = datetime.date.today().isoformat()
        total_novas = 0

        for caminho in self.PROJETOS:
            if not os.path.exists(caminho):
                continue

            mtime_atual = os.path.getmtime(caminho)
            info = self.state["arquivos"].get(caminho, {
                "mtime": 0,
                "escopo_processado": False,
                "agenda_start_line": 0,
            })

            if mtime_atual <= info["mtime"]:
                continue  # arquivo não mudou

            print(f"  [Miner] Processando: {_nome_curto(caminho)}")

            # Determina a partir de qual linha processar
            if not info["escopo_processado"]:
                # Primeira execução: processa tudo e localiza onde começa a seção # Agenda
                start_line = 0
                agenda_start = _encontrar_secao_agenda(caminho)
            else:
                # Execuções seguintes: reprocessa só a seção # Agenda (dedup garante idempotência)
                start_line = info["agenda_start_line"]
                agenda_start = info["agenda_start_line"]

            triplas, _, sucesso = self.miner.processar_arquivo(caminho, start_line)

            if sucesso:
                if triplas:
                    inseridas = self.memory.inserir_lote(triplas, data_referencia=hoje, fonte=caminho)
                    total_novas += inseridas
                    print(f"    -> {len(triplas)} triplas extraídas, {inseridas} novas no grafo.")
                self.state["arquivos"][caminho] = {
                    "mtime": mtime_atual,
                    "escopo_processado": True,
                    "agenda_start_line": agenda_start,
                }
            else:
                print(f"    -> Erro na extração. Estado não salvo — será reprocessado na próxima execução.")

        self._salvar_state()
        print(f"  [Grafo] Total no banco: {self.memory.contar()} triplas (+{total_novas} hoje).")

    # ------------------------------------------------------------------
    # Fontes de dados Google
    # ------------------------------------------------------------------

    def _get_agenda(self) -> list:
        service = build("calendar", "v3", credentials=self.creds)
        now = datetime.datetime.now().isoformat() + "Z"
        result = service.events().list(
            calendarId="primary", timeMin=now,
            maxResults=5, singleEvents=True, orderBy="startTime"
        ).execute()
        eventos = []
        for ev in result.get("items", []):
            inicio = ev["start"].get("dateTime", ev["start"].get("date"))
            eventos.append(f"{inicio} - {ev['summary']}")
        return eventos

    def _get_tarefas(self) -> list:
        service = build("tasks", "v1", credentials=self.creds)
        listas = service.tasklists().list().execute()
        lista_id = next(
            (tl["id"] for tl in listas.get("items", []) if tl["title"] == "Pessoal"),
            None
        )
        if not lista_id:
            return ["Lista 'Pessoal' não encontrada no Google Tasks."]

        items = service.tasks().list(tasklist=lista_id).execute().get("items", [])
        tarefas = []
        for item in items:
            texto = item["title"]
            if "notes" in item:
                texto += f" — {item['notes']}"
            tarefas.append(texto)
        return tarefas

    # ------------------------------------------------------------------
    # Contexto do grafo
    # ------------------------------------------------------------------

    def _extrair_entidades_da_agenda(self, agenda: list) -> list:
        """Pede ao Gemini uma lista de entidades-chave mencionadas na agenda."""
        if not agenda:
            return []
        texto_agenda = "\n".join(agenda)
        prompt = f"""
Da lista de compromissos abaixo, extraia os nomes de pessoas, projetos e instituições mencionados.
Retorne APENAS um JSON com uma lista de strings, sem texto adicional.
Exemplo: ["Gabriel Cepaluni", "CADE", "FGV"]

COMPROMISSOS:
{texto_agenda}
"""
        try:
            raw = self._model_miner.generate_content(prompt).text.strip()
            if raw.startswith("```"):
                partes = raw.split("```")
                raw = partes[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            entidades = json.loads(raw.strip())
            return entidades if isinstance(entidades, list) else []
        except Exception:
            return []

    def _montar_contexto_grafo(self, agenda: list) -> str:
        """
        Monta o bloco de contexto do grafo com duas seções:
        1. Estado atual de cada projeto (top N triplas por projeto)
        2. Triplas fuzzy relacionadas aos compromissos de hoje
        """
        linhas = []

        # --- Seção 1: Estado dos projetos ---
        linhas.append("--- ESTADO DOS PROJETOS ---")
        por_projeto = self.memory.listar_top_por_projeto(n_por_projeto=10)
        if por_projeto:
            for fonte, triplas in por_projeto.items():
                nome = _nome_curto(fonte)
                linhas.append(f"\n[{nome}]")
                for t in triplas:
                    linhas.append(f"  {t['sujeito']} --[{t['relacao']}]--> {t['objeto']} ({t['data']})")
        else:
            linhas.append("  (grafo ainda vazio)")

        # --- Seção 2: Contexto da agenda de hoje ---
        entidades = self._extrair_entidades_da_agenda(agenda)
        if entidades:
            linhas.append("\n--- CONTEXTO DA AGENDA DE HOJE ---")
            fuzzy = self.memory.buscar_fuzzy(entidades)
            if fuzzy:
                for t in fuzzy:
                    linhas.append(f"  {t['sujeito']} --[{t['relacao']}]--> {t['objeto']} ({t['data']})")
            else:
                linhas.append("  (nenhuma relação encontrada para os compromissos de hoje)")

        return "\n".join(linhas)

    # ------------------------------------------------------------------
    # Briefing
    # ------------------------------------------------------------------

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

        print("[4/4] Gerando briefing...")
        response = self._model_briefing.generate_content(prompt)
        return response.text

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------

    def log(self, output: str):
        historico = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                historico = json.load(f)
        historico.append({
            "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "output_ai": output,
        })
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Utilitário
# ---------------------------------------------------------------------------

def _encontrar_secao_agenda(caminho: str) -> int:
    """Retorna o índice da linha onde começa a seção '# Agenda'.
    Se não encontrar, retorna 0 (processa o arquivo inteiro)."""
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for i, linha in enumerate(f):
                if linha.strip().lower().startswith("# agenda"):
                    return i
    except Exception:
        pass
    return 0


def _nome_curto(caminho: str) -> str:
    """Extrai um nome legível do caminho do arquivo de agenda."""
    ignorar = {
        "agenda.md", "Agenda.md", "administrativo", "admin",
        "artigo", "reunioes", "03_produtos", "jobs", "projetosAtivos"
    }
    partes = caminho.replace("\\", "/").split("/")
    for parte in reversed(partes[:-1]):
        if parte and parte not in ignorar:
            return parte
    return partes[-2]


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pyperclip

    os.system("cls")
    agente = AgenteMarcoV2()
    briefing = agente.gerar_briefing()
    print("\n" + "=" * 60)
    print(briefing)
    agente.log(briefing)

    try:
        pyperclip.copy(briefing)
        print("\n[Briefing copiado para a área de transferência.]")
    except Exception as e:
        print(f"\n[Não foi possível copiar: {e}]")
