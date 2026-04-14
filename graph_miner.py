import json
import datetime


class GraphMiner:
    """Transforma trechos de Markdown em triplas (sujeito, relação, objeto) via Gemini."""

    PROMPT_EXTRACAO = """
Você está lendo o diário de trabalho e agenda pessoal de MARCO ANTONIO, um pesquisador e consultor.
Extraia triplas que sejam ÚTEIS para um secretário executivo pessoal acompanhar o que está acontecendo.

Retorne APENAS um JSON válido — uma lista de objetos, sem texto adicional:
[
  {{"sujeito": "Sujeito curto", "relacao": "verbo_snake_case", "objeto": "Objeto curto"}},
  ...
]

Extraia no máximo 15 triplas — as MAIS RELEVANTES e acionáveis para um secretário executivo.
Prefira qualidade a quantidade: 5 triplas precisas valem mais que 15 vagas.

FOCO — priorize relações sobre:
1. STATUS de entregas e projetos (concluído, em andamento, atrasado, pendente)
2. PRAZOS concretos (datas de entrega, reuniões, deadlines)
3. RESPONSABILIDADES de Marco Antonio (o que ele tem que fazer)
4. PESSOAS com quem ele colabora ou se relaciona no projeto
5. DECISÕES tomadas e próximos passos definidos
6. RISCOS ou bloqueios identificados

REGRAS obrigatórias:
- sujeito: sempre uma entidade curta — "Marco Antonio", "Produto 2 CADE", "Reunião CADE", "Keila Ferreira"
- objeto: sempre um substantivo ou data curta — NUNCA uma frase longa
  BOM: "Finalizado", "27/03/2026", "Keila Ferreira", "Produto 3 CADE"
  RUIM: "4 processos administrativos que geram multa ou contribuição pecuniária"
- relacao: verbo no infinitivo em snake_case
  Exemplos: "entregou", "tem_prazo_em", "colabora_com", "é_responsável_por", "agendou_reunião_com", "tem_status", "depende_de"
- Priorize Marco Antonio como sujeito sempre que possível
- Ignore fatos genéricos sobre instituições que não afetam o trabalho de Marco Antonio
- Se não houver relações acionáveis, retorne: []

TEXTO:
{texto}
"""

    CHUNK_LINHAS = 80  # linhas por chamada à API

    def __init__(self, model):
        self.model = model

    def extrair_triplas(self, texto: str, data_referencia: str = None) -> list:
        """Chama o Gemini para extrair triplas de um bloco de texto."""
        if not texto.strip():
            return []
        if data_referencia is None:
            data_referencia = datetime.date.today().isoformat()

        prompt = self.PROMPT_EXTRACAO.format(texto=texto)
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"max_output_tokens": 2048}
            )
            raw = response.text.strip()

            # Remove blocos de código markdown se o modelo os incluir
            if raw.startswith("```"):
                partes = raw.split("```")
                raw = partes[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            triplas = json.loads(raw.strip())
            if isinstance(triplas, list):
                return triplas
            return []
        except Exception as e:
            print(f"  [GraphMiner] Erro ao extrair triplas: {e}")
            return []

    def processar_arquivo(self, caminho: str, ultima_linha: int = 0) -> tuple:
        """
        Lê o arquivo a partir de `ultima_linha`, divide em chunks e extrai triplas.
        Retorna (triplas: list, nova_ultima_linha: int, sucesso: bool).
        sucesso=False indica erro em algum chunk — estado não deve ser salvo.
        """
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                linhas = f.readlines()

            novas_linhas = linhas[ultima_linha:]
            if not novas_linhas:
                return [], len(linhas), True

            # Divide em chunks para não estourar o limite de tokens de saída
            chunks = [
                novas_linhas[i : i + self.CHUNK_LINHAS]
                for i in range(0, len(novas_linhas), self.CHUNK_LINHAS)
            ]

            todas_triplas = []
            sucesso = True
            for idx, chunk in enumerate(chunks, 1):
                texto_chunk = "".join(chunk)
                if not texto_chunk.strip():
                    continue
                print(f"    chunk {idx}/{len(chunks)}...", end=" ", flush=True)
                try:
                    triplas = self.extrair_triplas(texto_chunk)
                    print(f"{len(triplas)} triplas")
                    todas_triplas.extend(triplas)
                except Exception as e:
                    print(f"ERRO: {e}")
                    sucesso = False

            return todas_triplas, len(linhas), sucesso

        except FileNotFoundError:
            print(f"  [GraphMiner] Arquivo não encontrado: {caminho}")
            return [], ultima_linha, False
        except Exception as e:
            print(f"  [GraphMiner] Erro ao processar {caminho}: {e}")
            return [], ultima_linha, False
