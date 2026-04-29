# Agente Secretário Executivo Pessoal

Agente de IA que atua como secretário executivo pessoal, integrando Google Calendar, Google Tasks e arquivos de projeto em Markdown para gerar um briefing matinal estruturado.

---

## Como funciona

A cada execução o agente:

1. **Lê a seção `# Estado Atual`** de cada arquivo `.md` de projeto — fonte de verdade sobre o que está em aberto
2. **Filtra itens concluídos** — linhas `- [x]` são ignoradas; só chegam ao briefing os `- [ ]`
3. **Busca agenda e tarefas** via Google Calendar e Google Tasks
4. **Gera o briefing** cruzando tudo com o estado declarado de cada projeto

```
[AGENDA]             compromissos do dia com contexto dos projetos
[PROJETOS]           status rápido de cada frente ativa
[TAREFAS]            pessoal + profissional para hoje
[FOCO DO DIA]        prioridade número 1 com justificativa
[PONTOS DE ATENÇÃO]  prazos críticos e riscos detectados
```

O agente também mantém um grafo de conhecimento secundário (SQLite) para contextualizar compromissos da agenda com informações históricas dos projetos.

---

## Estrutura do projeto

```
agente/
├── agente_v2.py          # Classe principal AgenteMarcoV2
├── graph_miner.py        # Extração de triplas via Gemini (contexto de agenda)
├── memory_interface.py   # Grafo de conhecimento (SQLite)
├── ver_grafo.py          # Ferramenta de inspeção do banco de triplas
├── agente_v2_test.py     # Dry run — imprime o prompt sem chamar a API
├── agenda_template.md    # Template para novos arquivos de projeto
├── memoria.db            # Banco SQLite (gerado automaticamente)
├── state.json            # Estado incremental de processamento (gerado automaticamente)
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
pip install google-generativeai google-api-python-client google-auth-oauthlib python-dotenv pyperclip
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

**3. Caminhos dos projetos**

Em `agente_v2.py`, ajuste a lista `PROJETOS` com os caminhos dos seus arquivos `.md`.

---

## Uso

```bash
# Briefing completo (resultado copiado para a área de transferência)
python agente_v2.py

# Dry run — ver o prompt montado sem chamar a API de briefing
python agente_v2_test.py

# Inspecionar o grafo de conhecimento secundário
python ver_grafo.py                  # visão geral por projeto
python ver_grafo.py "Marco Antonio"  # filtrar por termo
```

Na **primeira execução**, o browser abrirá para autenticação OAuth com o Google. O token é salvo em `token.json` para execuções futuras.

---

## Formato dos arquivos `.md` de projeto

Cada arquivo deve ter obrigatoriamente a seção `# Estado Atual`. A seção `# Agenda` é opcional e serve apenas como diário histórico — o agente não a lê para o briefing.

```markdown
# Estado Atual

- [x] Planilha entregue ao CADE
- [x] Produto 2 finalizado com Luciano e Andréia
- [ ] Aguardar resposta do CADE para iniciar Produto 3
- [ ] Entregar Produto 3 - Prazo: 29/04

---

# Agenda

<!-- Diário histórico — não é lido pelo agente para o briefing -->

## 28 de abril de 2026

Terminei a planilha e enviei para o CADE...
```

### Regras da seção `# Estado Atual`

| Elemento | Comportamento |
|---|---|
| `- [ ] tarefa` | Aparece no briefing como pendência |
| `- [ ] tarefa - Prazo: DD/MM` | Aparece no briefing com o prazo destacado |
| `- [x] tarefa` | **Ignorado** pelo agente — não aparece no briefing |
| Texto livre | Incluído no briefing normalmente |

### Boas práticas

- Mantenha a seção curta — 5 a 15 linhas é o ideal
- Ao concluir uma tarefa, troque `[ ]` por `[x]` (não delete)
- Inclua prazos próximos em texto livre: `**Próximos prazos:** DD/MM — descrição`
- Use a seção `# Agenda` livremente como diário — ela não afeta o briefing

Use `agenda_template.md` como ponto de partida para novos projetos.

---

## .gitignore recomendado

```
.env
credentials.json
token.json
memoria.db
state.json
log.json
__pycache__/
*.pyc
```

---

## Tecnologias

- **LLM:** Google Gemini 2.5 Flash Lite
- **APIs:** Google Calendar, Google Tasks (OAuth 2.0)
- **Grafo secundário:** SQLite com triplas (sujeito → relação → objeto)
- **Linguagem:** Python 3.10+
