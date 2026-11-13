# Calendário institucional (PDF que o professor manda)

Quando o professor manda o PDF da resolução do calendário acadêmico (CONSUN
ou equivalente), use esse processo pra extrair as datas relevantes e cruzar
com o cronograma calculado — em vez de perguntar recesso por recesso no
Bloco 4, item 9, da entrevista.

## 1. Converter o PDF

```
markitdown "<caminho do PDF>" > calendario-institucional.md
```

O PDF costuma ter uma grade de calendário (tabela mês a mês) que sai
bagunçada na conversão — a coluna de notas se mistura com a grade de dias.
Precisa reconstruir os pares dia+evento cruzando o cabeçalho do mês com a
nota associada. Se o `.md` tiver mais de ~150 linhas, delegue a leitura pra
um subagente (regra de contexto do projeto) — ele devolve só a lista de
datas por categoria, não o `.md` inteiro.

## 2. Extrair por categoria

Peça pro subagente (ou extraia direto, se o arquivo for curto) as datas
nessas categorias — **não invente o que não estiver no documento**, e marque
"não encontrado" pra categoria ausente:

1. Início/fim de cada semestre letivo do ano corrente — separe a data
   "administrativa" (início do semestre letivo) da data real de início das
   aulas em sala, se o documento distinguir as duas (a PUCPR costuma ter ~1
   semana de defasagem entre elas, por causa da Semana de Integração e
   Formação Docente). Use sempre a segunda pro cronograma.
2. Pontos facultativos / recessos acadêmicos institucionais — só os que o
   texto rotula como "Recesso Acadêmico" (ou equivalente); feriado nacional
   não entra aqui (já vem da BrasilAPI dentro de `gerar_cronograma.py`).
   Corpus Christi e datas de padroeiro costumam aparecer como "Feriado" sem
   ser feriado federal — checar se não duplica com a BrasilAPI antes de
   incluir.
3. Feriados/recessos **locais por campus** — só valem se o professor
   leciona nesse campus específico; não aplicar globalmente.
4. Eventos institucionais que ocupam dias de aula sem necessariamente
   cancelá-la (Semana Acadêmica/Integração, SEMIC/SEMITI, Formação
   Docente) — viram candidatas a linha manual (`RA: "-"`) no cronograma.
5. Períodos de avaliação / recuperação — a resolução pode não usar
   literalmente "2ª chamada" (a PUCPR usa "Semana Estendida de
   Recuperação"); não assuma que é a mesma coisa que o professor quer dizer
   com `datas_2a_chamada` — confirme antes de mapear direto.
6. Datas que não bloqueiam aula mas valem avisar o professor (prazo de
   postagem do Plano de Ensino/TDE no AVA, fechamento de diário, entrega de
   notas) — não entram no cronograma, só no brief da entrevista.

## 3. Montar `calendario_institucional.json`

Formato aceito por `scripts/verifica_calendario_institucional.py` (ver
docstring do script pro contrato completo):

```json
[
  {"data": "2026-02-16", "data_fim": "2026-02-17", "tipo": "recesso", "descricao": "Carnaval"},
  {"data": "2026-02-23", "data_fim": "2026-02-28", "tipo": "evento", "descricao": "Semana de Integração Acadêmica"},
  {"data": "2026-03-02", "tipo": "limite_inicio", "descricao": "Início das aulas"},
  {"data": "2026-06-27", "tipo": "limite_fim", "descricao": "Encerramento das aulas"}
]
```

Recesso vira automaticamente candidato a `recessos_manuais` em
`dados_cronograma.json` — não precisa perguntar de novo ao professor se já
veio do PDF.

**Só inclua o `limite_inicio`/`limite_fim` do semestre que a disciplina
cobre.** O PDF costuma trazer o calendário do ano inteiro (1º e 2º
semestre); se os dois pares entrarem no JSON, o script compara o
cronograma contra os dois — e o par do semestre errado sempre dispara
aviso (ex: cronograma do 2º semestre "termina depois" do fim do 1º
semestre, o que é óbvio e não é um conflito real). `recesso` e `evento`
não têm esse problema — comparam data por data, então tanto faz incluir
os dois semestres.

## 4. Verificar contra o cronograma calculado

Depois de rodar `gerar_cronograma.py` (passo 2 do `SKILL.md`):

```
python3 scripts/verifica_calendario_institucional.py cronograma.json calendario_institucional.json
```

Os avisos apontam:
- recesso institucional que ainda aparece como aula no cronograma (faltou
  em `recessos_manuais`);
- evento institucional (Semana Acadêmica etc) coincidindo com aula normal
  marcada — decida com o professor se vira linha manual ou se mantém a aula;
- cronograma começando antes ou terminando depois do limite oficial do
  semestre.

Resolva os avisos com o professor (mesma regra do item "avisos" do passo 2
do `SKILL.md`) antes de seguir pra montagem do documento — não gere o plano
final com um aviso de calendário institucional pendente sem avisar
explicitamente que ficou uma lacuna.
