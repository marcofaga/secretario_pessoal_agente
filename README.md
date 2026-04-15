# Agente Secretário Executivo Pessoal

Agente de IA que atua como secretário executivo pessoal, integrando Google Calendar, Google Tasks e arquivos de agenda em Markdown para gerar um briefing matinal estruturado. Mantém uma **memória de grafo de conhecimento** em SQLite para conectar pessoas, projetos e prazos ao longo do tempo.

---

## Como funciona

A cada execução o agente:

1. **Detecta mudanças** nos arquivos `.md` de projetos (via `mtime`) e minera apenas o conteúdo novo
2. **Extrai triplas** do tipo `Marco Antonio --[tem_prazo_em]--> 22/04/2026` usando o Gemini
3. **Busca agenda e tarefas** via Google Calendar e Google Tasks
4. **Monta contexto** cruzando o estado de cada projeto com os compromissos do dia
5. **Gera o briefing** com seções de Agenda, Projetos, Tarefas, Foco do Dia e Pontos de Atenção

```
[AGENDA]             compromissos do dia com contexto dos projetos
[PROJETOS]           status rápido de cada frente ativa
[TAREFAS]            pessoal + profissional para hoje
[FOCO DO DIA]        prioridade número 1 com justificativa
[PONTOS DE ATENÇÃO]  prazos críticos e riscos detectados
```

---

## Estrutura do projeto

```
agente/
├── agente_v2.py          # Classe principal AgenteMarcoV2
├── graph_miner.py        # Extração de triplas via Gemini
├── memory_interface.py   # Grafo de conhecimento (SQLite)
├── ver_grafo.py          # Ferramenta de inspeção do banco
├── agente_v2_test.py     # Dry run — imprime prompt sem chamar a API
├── SPEC.md               # Especificação técnica detalhada
├── memoria.db            # Banco SQLite (gerado automaticamente)
├── state.json            # Estado incremental de processamento
├── log.json              # Histórico de briefings gerados
├── credentials.json      # Credenciais Google OAuth (não versionar)
└── token.json            # Token de acesso Google (não versionar)
```

---

## Requisitos

- Python 3.10+
- Conta Google com acesso ao Calendar e Tasks
- Chave de API do Google Gemini

```bash
pip install google-generativeai google-api-python-client google-auth-oauthlib python-dotenv
```

---

## Configuração

**1. Credenciais Google**

Acesse o [Google Cloud Console](https://console.cloud.google.com), crie um projeto, ative as APIs **Google Calendar** e **Google Tasks**, e baixe o arquivo `credentials.json` (OAuth 2.0 para aplicativo desktop). Coloque-o na raiz do projeto.

**2. Chave Gemini**

Copie o arquivo de exemplo e preencha com sua chave:
```bash
cp .env.example .env
```
Edite o `.env`:
```
GEMINI_API_KEY=sua_chave_aqui
```
O `.env` está no `.gitignore` e nunca será enviado ao repositório.

**3. Caminhos dos projetos**

Em `agente_v2.py`, ajuste a lista `PROJETOS` com os caminhos dos seus arquivos `.md` de agenda.

---

## Uso

```bash
# Briefing completo
python agente_v2.py

# Dry run — ver o prompt sem chamar a API de briefing
python agente_v2_test.py

# Inspecionar o grafo de conhecimento
python ver_grafo.py                  # visão geral por projeto
python ver_grafo.py "Marco Antonio"  # filtrar por termo
python ver_grafo.py CADE             # filtrar por projeto
```

Na **primeira execução**, o browser abrirá para autenticação OAuth com o Google. O token é salvo em `token.json` para execuções futuras.

---

## Formato dos arquivos .md de agenda

Cada arquivo deve seguir obrigatoriamente a estrutura de duas seções:

```markdown
# Escopo

Contexto permanente do projeto: objetivo, participantes fixos, tecnologias,
regras de negócio. Esta seção é processada uma única vez pelo agente.

---

# Agenda

## 14 de abril de 2026

Conteúdo mais recente sempre no topo desta seção.
Decisões tomadas, prazos, responsabilidades, próximos passos.

## 10 de abril de 2026

...
```

### Regras importantes

| Regra | Motivo |
|---|---|
| `# Escopo` sempre antes de `# Agenda` | O agente detecta a seção pelo cabeçalho |
| Novas entradas sempre no **topo** da seção `# Agenda` | O agente reprocessa a seção inteira quando o arquivo muda |
| Datas no cabeçalho das entradas (`## DD de mês de AAAA`) | Facilita a extração de contexto temporal |
| Prazos e nomes escritos por extenso | O Gemini extrai melhor entidades explícitas do que abreviações |

### O que escrever para maximizar a qualidade do grafo

O agente extrai mais valor de texto que mencione explicitamente:

- **Status** — "Produto 2 finalizado.", "Em andamento.", "Atrasado."
- **Prazos** — "Entrega prevista para 30/04/2026.", "Reunião às 14h."
- **Pessoas** — nomes completos na primeira menção ("Keila Ferreira"), apelidos depois
- **Responsabilidades** — "Marco Antonio ficou de enviar até sexta."
- **Riscos** — "Dados desatualizados.", "Dependência do Luciano para acesso ao sistema."
- **Próximos passos** — "Próximo passo: redigir relatório final."

Use `agenda_template.md` como ponto de partida para novos projetos.

---

## .gitignore recomendado

```
credentials.json
token.json
memoria.db
log.json
__pycache__/
*.pyc
```

---

## Tecnologias

- **LLM:** Google Gemini 2.5 Flash Lite
- **Memória:** SQLite com grafo de triplas (sujeito → relação → objeto)
- **APIs:** Google Calendar, Google Tasks (OAuth 2.0)
- **Linguagem:** Python 3.10+
