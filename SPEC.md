# SPEC: Agente Secretário Executivo — v2.0

## 1. Visão Geral

Agente de IA que atua como Secretário Executivo pessoal de Marco Antonio Faganello. O sistema integra dados de múltiplas fontes (Google Calendar, Google Tasks, arquivos Markdown de projetos) e mantém uma **Memória de Grafo de Conhecimento** em SQLite para gerar um briefing matinal contextualizado, cruzando vida pessoal e profissional.

---

## 2. Arquitetura

```
                        ┌─────────────────────────────┐
                        │        agente_v2.py          │
                        │      AgenteMarcoV2           │
                        └──────────┬──────────────────┘
                                   │
          ┌────────────────────────┼──────────────────────┐
          ▼                        ▼                       ▼
 ┌────────────────┐    ┌──────────────────────┐   ┌──────────────────┐
 │  Google APIs   │    │    graph_miner.py     │   │memory_interface.py│
 │  Calendar      │    │    GraphMiner         │   │ MemoryInterface  │
 │  Tasks         │    │ (Gemini extrai triplas│   │ (SQLite — grafo) │
 └────────────────┘    │  dos arquivos .md)   │   └──────────────────┘
                        └──────────────────────┘
                                   │
                        ┌──────────────────────┐
                        │  Arquivos .md locais  │
                        │  (8 projetos/agendas) │
                        └──────────────────────┘
```

---

## 3. Componentes

### 3.1 `AgenteMarcoV2` (`agente_v2.py`)
Classe principal. Orquestra o fluxo completo de execução.

**Responsabilidades:**
- Autenticação OAuth 2.0 com Google (Calendar + Tasks)
- Gerenciamento de estado incremental via `state.json`
- Coordenação entre GraphMiner e MemoryInterface
- Montagem do contexto do grafo em duas seções (estado dos projetos + contexto da agenda)
- Geração do briefing via Gemini
- Persistência do histórico em `log.json`

**Fluxo de execução:**
1. `processar_projetos()` — verifica `mtime` de cada `.md`; se mudou, minera delta via GraphMiner
2. `_get_agenda()` / `_get_tarefas()` — busca dados da Google API
3. `_montar_contexto_grafo()` — combina estado dos projetos + busca fuzzy da agenda
4. `gerar_briefing()` — envia prompt ao Gemini e retorna texto estruturado

### 3.2 `GraphMiner` (`graph_miner.py`)
Transforma trechos de Markdown em triplas via Gemini.

**Responsabilidades:**
- Dividir o conteúdo em chunks de 80 linhas (evita estouro de tokens de saída)
- Enviar cada chunk ao Gemini com prompt especializado para secretário executivo
- Retornar flag `sucesso` — se algum chunk falhar, o estado do arquivo não é salvo
- Limitar a saída a 2048 tokens e 15 triplas por chunk via `generation_config`

**Prompt de extração:** focado em Marco Antonio como sujeito central, priorizando:
- Status de entregas (concluído, pendente, em andamento)
- Prazos concretos
- Responsabilidades e próximos passos
- Pessoas colaboradoras
- Riscos e bloqueios

### 3.3 `MemoryInterface` (`memory_interface.py`)
Gerencia a persistência do grafo de conhecimento em SQLite.

**Schema (`memoria.db`):**
```sql
CREATE TABLE triplas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sujeito          TEXT NOT NULL,
    relacao          TEXT NOT NULL,
    objeto           TEXT NOT NULL,
    data_referencia  TEXT,           -- data de processamento (ISO)
    fonte            TEXT,           -- caminho do arquivo de origem
    UNIQUE(sujeito, relacao, objeto) -- deduplicação automática
)
```

**Métodos principais:**
- `inserir_lote(triplas, data_referencia, fonte)` — insere com deduplicação
- `listar_top_por_projeto(n=10)` — top N triplas por projeto, ordenadas por `data_referencia DESC, id ASC` (preserva ordem do topo do arquivo = conteúdo mais recente)
- `buscar_fuzzy(termos)` — LIKE em sujeito/relação/objeto para múltiplos termos

### 3.4 `ver_grafo.py`
Ferramenta de inspeção do banco. Uso: `python ver_grafo.py [termo]`

### 3.5 `agente_v2_test.py`
Dry run: executa todo o pipeline exceto a chamada final ao Gemini para o briefing. Imprime o prompt completo para validação.

---

## 4. Fontes de Dados

### Google APIs
| Fonte | Escopo | Dados coletados |
|---|---|---|
| Google Calendar | `calendar.readonly` | Próximos 5 eventos |
| Google Tasks | `tasks.readonly` | Lista "Pessoal" completa |

### Arquivos Markdown Locais (8 projetos)
| Projeto | Caminho |
|---|---|
| CADE PNUD | `G:/Meu Drive/MAFData/projetosAtivos/20251009 - CADE PNUD/03_produtos/administrativo/agenda.md` |
| RadioOne | `G:/Meu Drive/RadioOne/Agenda.md` |
| a38 - Abstenção Eleitoral | `.../a38 - Distancia e Abstencao Eleitoral Luna/admin/Agenda.md` |
| a31 - Rede Neural | `.../a31 - Rede Neural e Despesa de Campanha/artigo/Agenda.md` |
| a011 - IC Mudanças | `.../a011 - IC Mudancas nas Regras/reunioes/Agenda.md` |
| a34 - Funcionários Públicos | `.../a34 - Funcionarios Publicos/Agenda.md` |
| a39 - Experimento Eleições | `.../a39 - Experimento Eleições/agenda.md` |
| Imóveis Bucci | `G:/Meu Drive/MAFData/projetosAtivos/imoveis_bucci/agenda.md` |

---

## 5. Processamento Incremental

**Estado persistido em `state.json`:**
```json
{
  "arquivos": {
    "G:/caminho/Agenda.md": {
      "mtime": 1776144342.613,
      "ultima_linha": 458
    }
  }
}
```

**Lógica:**
1. Compara `os.path.getmtime()` com `mtime` salvo
2. Se igual → pula (sem custo de API)
3. Se diferente → lê apenas linhas a partir de `ultima_linha`
4. Processa em chunks de 80 linhas
5. **Salva estado SOMENTE se todos os chunks tiverem sucesso**

---

## 6. Modelos Gemini

| Uso | Modelo |
|---|---|
| Extração de triplas (GraphMiner) | `gemini-2.5-flash-lite` |
| Extração de entidades da agenda | `gemini-2.5-flash-lite` |
| Geração do briefing | `gemini-2.5-flash-lite` |

---

## 7. Output do Briefing

Estrutura gerada pelo Gemini:

```
[AGENDA]        — compromissos do dia com contexto dos projetos
[PROJETOS]      — status rápido de cada frente ativa
[TAREFAS]       — pessoal + profissional para o dia
[FOCO DO DIA]   — prioridade número 1 com justificativa
[PONTOS DE ATENÇÃO] — prazos críticos e riscos detectados
```

---

## 8. Limitações Conhecidas

- **Datas relativas nas triplas** — expressões como "amanhã" ou "em breve" perdem significado com o tempo
- **Ordenação por projeto** — arquivos com conteúdo mais recente no topo são tratados corretamente (`id ASC`), mas arquivos com ordem cronológica invertida exigirão ajuste manual
- **Deduplicação sem atualização** — se um status muda (ex: "pendente" → "concluído"), ambas as triplas coexistem no banco. Não há mecanismo de invalidação de triplas antigas
- **Token de saída** — o limite de 2048 tokens por chunk pode truncar arquivos com sessões muito densas; reduzir `CHUNK_LINHAS` de 80 para 50 nesses casos

---

## 9. Roadmap

- [ ] Invalidação de triplas obsoletas (ex: status desatualizado)
- [ ] Normalização de datas relativas para absolutas no momento da extração
- [ ] Agendamento automático diário (Task Scheduler / cron)
- [ ] Envio do briefing por canal de notificação (e-mail, Telegram)
