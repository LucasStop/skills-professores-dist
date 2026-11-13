---
name: plano-de-ensino
description: Monta o plano de ensino completo de uma disciplina universitária no template PUCPR "Percursos Formativos" (Ementa, Contexto da Disciplina, Competências/RA, Metodologia e Avaliação, Cronograma, Bibliografia, Orientações Gerais), calcula o cronograma automaticamente a partir de datas/RAs/dias de aula, e gera o .docx oficial pronto pra editar (e o .pdf quando o LibreOffice está instalado). Use quando o professor pedir "monta o plano de ensino de [disciplina]", "gera o cronograma da disciplina", "preciso montar/atualizar o plano de ensino", ou pedir pra recalcular o cronograma com novas datas. Não use pra criar uma skill nova do zero (isso é a `criar-skill-professor`).
metadata:
  repo: skills-professores
  template: percursos-formativos-pucpr-2026
---

# Plano de ensino

Gera o documento completo a partir de uma entrevista curta + um cálculo de cronograma, e gera o `.docx` oficial só com Python 3; o `.pdf` com a arte institucional exige LibreOffice (`soffice`) instalado. Leia `references/template-pucpr.md` (estrutura oficial de 7 seções + "Regras da Disciplina" opcional, confirmada contra o `.docx` editável oficial da PUCPR e planos reais de professores) e `references/entrevista.md` (roteiro completo de perguntas por bloco) antes de rodar o fluxo abaixo.

O template oficial já está no repo (`assets/template-oficial-tokenizado.docx`, com a arte institucional: faixa, selo, cores) — **não gere do zero**, use `scripts/preencher_template.py` pra preencher os campos direto nesse arquivo (ver nota no fim de `references/template-pucpr.md`). `gerar_docx.py`/`gerar_pdf.py` são o caminho de reserva se esse asset não estiver disponível.

## 0. Checagem de pré-requisito

Antes de qualquer coisa, confirme que há Python 3 disponível:
```
python3 --version
```
Se o comando falhar (não encontrado), **pare e pergunte ao professor se quer instalar** (não instale sozinho sem confirmação — no Mac seria `brew install python3` ou o instalador oficial em python.org). Sem Python 3 os scripts desta skill não rodam.

## 1. Entrevista

Siga `references/entrevista.md` — 5 blocos curtos (Identificação, Conteúdo pedagógico, Avaliação, Cronograma, Regras/Bibliografia/Orientações), 2-3 perguntas por rodada, assert-then-confirm quando o contexto já sugerir a resposta.

**Regra do NDE e consulta ao PPC**:
- Antes de pedir Ementa, Temas e Bibliografia ao professor, execute `python3 scripts/consulta_ppc.py "<disciplina>"`.
  - Se encontrar no PPC (curso BSI): apresente o texto do PPC e pergunte se o professor mantém (**recomendado, já pré-aprovado pelo NDE**) ou altera (vira pendência de revisão do NDE).
  - Se não encontrar ou for outro curso: peça ao professor como hoje.
- Para precedentes e posteriores da seção 2 (Contexto da Disciplina): sugira com `python3 scripts/consulta_ppc.py --precedencia "<disciplina>"` a partir da Matriz de Competências e peça confirmação do professor.
- **Nome oficial**: toda chamada ao `consulta_ppc.py` (consulta simples, `--precedencia`, `--confere`) usa o nome oficial do campo `disciplina` da primeira consulta, não o nome dito pelo professor.
  - Se vier `disciplina: null` com aviso "candidatos mais próximos", mas houver `sugestao`, confirme com o professor e rode de novo com esse nome exato.
  - Só diga que a disciplina "não consta no PPC/matriz" quando não houver candidato.
- Lembrete de governança do NDE: Contexto e Competências/RAs não possuem texto de referência descritivo por disciplina no PPC, sendo sempre objeto de validação e pendência de aprovação do NDE.

O Bloco 4 (Cronograma) é o que alimenta o cálculo — não pule nenhuma das 11 perguntas dele (inclui granularidade, formato de data, feriados como linha e 2ª chamada). O Bloco 3 (Avaliação) pergunta o tipo de disciplina (Certificadora/Internalizadora-Mobilizadora/Mista — decide a estrutura oficial da seção 3) e, se aplicável, o estilo visual — não assume nenhum dos dois. "Regras da Disciplina" **é opcional** — o template oficial da PUCPR não tem essa seção, o Bloco 1 pergunta se a Escola do professor exige (se sim, ela vira seção 6, deslocando Bibliografia/Orientações Gerais pra 7/8).

**Plano antigo (template 2025)**: se `extrai_plano_existente.py` devolver o aviso de template 2025 (seções numeradas "1. Ementa", "4. Resultados de Aprendizagem"), nada foi extraído de propósito. Leia `texto_original` do resultado, refaça a entrevista (`references/entrevista.md`) usando esse texto como sugestão em cada campo (Ementa, temas, RAs, metodologia, bibliografia) e confirme cada seção com o professor; gere no template 2026. Nunca descarte texto do plano antigo em silêncio.

**Global Classes (plano em inglês)**: o Bloco 1 pergunta se a disciplina é Global Classes. Se for, o plano sai com `assets/template-oficial-tokenizado-en.docx` (mesmos tokens do PT, textos fixos em inglês — gerado por `scripts/limpar_template_oficial.py --en`, nunca à mão) e a Ementa leva a nota do programa + o bloco "(Syllabus)" (Bloco 2). Os textos fixos EN vêm do dicionário `TRADUCAO_EN` em `scripts/extrai_plano_existente.py`; alguns não têm par no plano EN real do corpus e estão marcados como tradução a revisar. `gerar_cronograma.py` ainda emite `Feriado`, `TDE`, `Recesso Acadêmico` e `[2ª Chamada]` em português — num plano EN, revise essas linhas do cronograma com o professor. Ver `references/template-pucpr.md` (seção "Global Classes").

Monte um brief resumido (identificação, RAs e %, range de datas, nº de encontros) e **confirme com o professor antes de gerar qualquer arquivo**.

## 2. Cronograma

Depois de confirmado o brief, monte o JSON de entrada (formato documentado no topo de `scripts/gerar_cronograma.py`) com os dados do Bloco 4 — inclua `campus` (`"ctb"`/`"lon"`/`"tol"`: sem ele, feriado local e dia de TDE do calendário não entram e o script avisa), `granularidade` (`"dia"`/`"semana"`/`"quinzena"`/`"mes"`), `formato_data` (`"dd_mm"` ou `"dd_mm_aaaa"`, só relevante se granularidade `"dia"`), `feriados_como_linha` (`true`/`false`) e `datas_2a_chamada` (lista, opcional) conforme as respostas do professor — e rode:
```
python3 scripts/gerar_cronograma.py dados_cronograma.json > cronograma.json
```
Leia os `avisos` do resultado (feriados não encontrados, temas insuficientes, TDE estourando a carga do RA) e resolva com o professor antes de seguir — não gere o documento final com aviso pendente sem avisar explicitamente que ficou uma lacuna.

Se o professor mandou o PDF do calendário institucional (resolução CONSUN ou equivalente), siga `references/calendario-institucional.md` — extrai as datas relevantes (recessos, eventos, limites de semestre), monta `calendario_institucional.json` e roda `scripts/verifica_calendario_institucional.py cronograma.json calendario_institucional.json` pra cruzar com o cronograma calculado. Resolva os avisos com o professor antes de seguir, mesma regra do parágrafo acima.

## 3. Bibliografia

Regra do NDE, confirmada no template oficial (ver `references/template-pucpr.md` seção 6): Básica precisa de no mínimo 3 títulos + 1 periódico, Complementar de no mínimo 5 + 1 periódico. Valide as referências no catálogo Pergamum via `scripts/verifica_bibliografia.py`, seguindo `references/entrevista.md` Bloco 5 — professor já tem título/autor (busca por referência) ou só tem o tema (busca por assunto, ele escolhe entre os candidatos):
```
python3 scripts/verifica_bibliografia.py --busca "<título, autor ou tema>"
python3 scripts/verifica_bibliografia.py --checa biblio_basica.json biblio_complementar.json
```
Leia os `avisos` do `--checa` (mínimo não atingido, item da Complementar sem exemplar físico, nenhum item virtual na Básica, lembrete de periódico manual) e resolva com o professor antes de seguir, mesma regra do passo anterior. Periódico (1 por bloco): ofereça opções de acesso aberto com `python3 scripts/verifica_bibliografia.py --periodico "<tema>"` (DOAJ, sem chave); periódico com ISSN no DOAJ deixa de gerar o aviso de conferência manual no `--checa`. Periódico de base paga da PUC continua confirmado direto com o professor (exige login institucional).

## 4. Montar o documento

Monte `documento.json` (lista de blocos `titulo1`/`titulo2`/`paragrafo`/`tabela`, formato no topo de `scripts/gerar_docx.py`) seguindo a ordem de `assets/plano-template.md`, usando o `cronograma.json` gerado no passo anterior pra preencher a tabela da seção 5 — colunas **# | Data (ou Período, se granularidade ≠ "dia") | RA | Descrição das atividades pedagógicas | Carga horária** (`larguras: [5, 12, 8, 55, 20]`), usando os campos `indice`/`data`/`ra`/`descricao`/`carga_horaria_fmt` de cada linha do `cronograma.json` (não `carga_horaria` nem `data_iso`, que são só pro cálculo). Linha com `indice: null` entra com a célula `#` vazia. Se o professor pediu datas institucionais sem RA (Acolhida Cultural, Semana Acadêmica), insira essas linhas manualmente na posição cronológica certa, com `RA: "-"`.

A coluna `RA` do cronograma aceita múltiplos valores (`RA1, RA2`) ou o literal `Todos` pra linhas que não pertencem a um RA só (revisão, feedback) — ajuste manual, nenhum script gera isso sozinho.

Linhas de avaliação somativa (fechamento de RA) levam destaque visual (vermelho mais fraco) no cronograma — marque com `"_destaque": true` na linha correspondente ao montar `dados_preenchimento.json` (ver contrato de `linhas_repetir` na docstring de `scripts/preencher_template.py`). Nenhum script decide isso sozinho.

Se o Bloco 1 confirmou que a Escola exige "Regras da Disciplina", inclua essa seção (usar o boilerplate documentado em `references/template-pucpr.md`) antes da Bibliografia, e ajuste a numeração dos títulos (Bibliografia vira 7, Orientações Gerais vira 8); senão, segue a numeração oficial (Bibliografia 6, Orientações Gerais 7).

Bibliografia: referências validadas no passo 3 (via Pergamum) levam `(Link acervo Pergamum: <link>)` no fim do texto; se o professor pediu lista numerada ou bullets (em vez de tabela), monte como sequência de blocos `"paragrafo"` com o número/bullet já no texto (`"1. Autor..."` ou `"• Autor..."`) em vez de um bloco `"tabela"`.

Orientações Gerais: use o texto literal de `references/template-pucpr.md`, não parafraseie.

Se estiver preenchendo o `.docx` oficial via `scripts/preencher_template.py` em vez de gerar do zero, o formato de entrada é diferente (`{"valores": {...}, "linhas_repetir": {...}}`, ver docstring do script) — os mesmos dados acima, só reorganizados pro formato de placeholder.

Antes de exportar (inclusive quando o plano foi extraído de um `.docx` existente com `scripts/extrai_plano_existente.py`), confira o Alinhamento Construtivo — todo RA da seção 3 avaliado na seção 4 e trabalhado no cronograma, e nenhum RA citado fora da seção 3:
```
python3 scripts/verifica_ras.py dados_preenchimento.json
```
Aceita o formato de `linhas_repetir` acima ou a saída inteira do extrator. **Mostre os `avisos` ao professor** (RA órfão, seção sem RA extraído, texto sem RA reconhecível) e resolva com ele antes de exportar; o script só aponta, nunca corrige.

## 5. Exportar

Antes de gerar os arquivos finais, **pergunte onde salvar** — padrão `~/Desktop` se o professor não especificar outra pasta.

Caminho principal (template oficial, via `scripts/preencher_template.py`):
```
python3 scripts/preencher_template.py assets/template-oficial-tokenizado.docx dados_preenchimento.json "<pasta escolhida>/Plano de Ensino - <Disciplina>.docx"
```
Se sobrar algum `{{TOKEN}}` o script para com erro, lista os campos faltantes e não grava o arquivo: volte à entrevista e complete (só use `--permite-pendente` se o professor pediu um rascunho). Gera o `.docx` (com a arte institucional). **PDF:** se o professor quiser `.pdf`, rode `which soffice`: se existir, `soffice --headless --convert-to pdf --outdir "<pasta escolhida>" "<arquivo>.docx"` (mantém a arte). Se não existir, **avise antes de gerar**: o `.pdf` de `gerar_pdf.py` (a partir do mesmo `documento.json`) sai só com texto e tabelas, sem a arte oficial, e não deve ser apresentado como versão oficial; ofereça só o `.docx` e a instalação do LibreOffice.

Global Classes (plano em inglês): mesmo comando, trocando o template por `assets/template-oficial-tokenizado-en.docx`.

Caminho de reserva (sem o template oficial, gera do zero):
```
python3 scripts/gerar_docx.py documento.json "<pasta escolhida>/Plano de Ensino - <Disciplina>.docx"
python3 scripts/gerar_pdf.py documento.json "<pasta escolhida>/Plano de Ensino - <Disciplina>.pdf"
```
Esse caminho gera os dois formatos juntos a partir do mesmo `documento.json`, sem a arte institucional: o `.docx` é a fonte editável, o `.pdf` é só pra leitura.

## 6. Lista de pendências do NDE

Junto com a entrega do `.docx`, gere e apresente a lista de pendências de revisão e pré-aprovações do NDE através do script `consulta_ppc.py --confere`:
```bash
python3 scripts/consulta_ppc.py --confere dados_preenchimento.json
```
A saída JSON identifica claramente a governança de cada seção do plano:
- `disciplina`: nome oficial da disciplina;
- `pre_aprovadas`: seções que mantêm o texto do PPC sem alterações (`["Ementa"]` se idêntica após normalização de espaços e quebras);
- `pendencias_nde`: seções pendentes de revisão/aprovação do NDE (`Contexto` e `Competências` constam sempre por não terem texto descritivo por disciplina no PPC; `Ementa` consta com o resumo da divergência caso tenha sido alterada ou não preenchida);
- `avisos`: eventuais alertas caso a disciplina não conste na matriz/catálogo do PPC.

Apresente esse resumo ao professor ao entregar o plano gerado para dar visibilidade do que já está pré-aprovado e do que demanda apreciação formal do NDE.

Não commita/dá push no repo `skills-professores` sozinho — só se o professor pedir.
