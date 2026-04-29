import os
import re
import json
import datetime

import google.generativeai as genai
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "log.json")


class AgenteMarcoV2:
    """Secretário Executivo Pessoal."""

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
        self._model = genai.GenerativeModel("gemini-2.5-flash-lite")
        self.creds = self._autenticar()

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
    # Estado dos projetos
    # ------------------------------------------------------------------

    def _montar_estado_projetos(self) -> str:
        """Lê a seção '# Estado Atual' de cada projeto diretamente do arquivo."""
        blocos = []
        for caminho in self.PROJETOS:
            if not os.path.exists(caminho):
                continue
            estado = _filtrar_concluidos(_ler_secao(caminho, "# Estado Atual"))
            if estado:
                blocos.append(f"[{_nome_curto(caminho)}]\n{estado}")
        return "\n\n".join(blocos) if blocos else "(nenhuma seção '# Estado Atual' encontrada nos projetos)"

    # ------------------------------------------------------------------
    # Briefing
    # ------------------------------------------------------------------

    def gerar_briefing(self) -> str:
        print("[1/3] Buscando agenda e tarefas...")
        agenda = self._get_agenda()
        tarefas = self._get_tarefas()

        print("[2/3] Lendo estado dos projetos...")
        estado_projetos = self._montar_estado_projetos()

        data_hoje = datetime.datetime.now().strftime("%d/%m/%Y")

        prompt = f"""
Você é o Secretário Executivo do Marco Antonio.
Hoje é {data_hoje}. Seja proativo, direto e com tom de parceria — sem ser servil.

FONTES DE DADOS:

[AGENDA GOOGLE — próximos compromissos]
{agenda}

[TAREFAS PESSOAIS (Google Tasks)]
{tarefas}

[ESTADO ATUAL DOS PROJETOS — declarado pelo usuário]
{estado_projetos}

INSTRUÇÕES:
- Concilie vida pessoal (tarefas, saúde, família) com os projetos profissionais.
- Cruze compromissos da agenda com o estado atual de cada projeto.
- Detecte prazos críticos, dependências e oportunidades de avanço.
- O estado dos projetos acima é a fonte de verdade — não infira pendências que não estejam explicitadas nele.
- Gere um briefing matinal estruturado em:
  [AGENDA] — compromissos do dia com contexto relevante
  [PROJETOS] — status rápido de cada frente ativa
  [TAREFAS] — o que precisa ser feito hoje (pessoal + profissional)
  [FOCO DO DIA] — prioridade número 1 com justificativa
  [PONTOS DE ATENÇÃO] — prazos críticos e riscos detectados
"""

        print("[3/3] Gerando briefing...")
        response = self._model.generate_content(prompt)
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
# Utilitários
# ---------------------------------------------------------------------------

def _filtrar_concluidos(texto: str) -> str:
    """Remove linhas de checklist marcadas como concluídas (- [x])."""
    linhas = [l for l in texto.split("\n") if not re.match(r"\s*-\s*\[x\]\s*", l, re.IGNORECASE)]
    return "\n".join(linhas).strip()


def _ler_secao(caminho: str, titulo: str) -> str:
    """Extrai o conteúdo de uma seção markdown pelo título (case-insensitive)."""
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            linhas = f.readlines()
    except Exception:
        return ""
    titulo_lower = titulo.strip().lower()
    dentro = False
    secao = []
    for linha in linhas:
        if linha.strip().lower().startswith(titulo_lower):
            dentro = True
            continue
        if dentro:
            if linha.startswith("#"):
                break
            secao.append(linha)
    return "".join(secao).strip()


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
    import pyperclip  # importado aqui pois só é usado na execução direta

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
