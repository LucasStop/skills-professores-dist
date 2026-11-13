# Template PUCPR "Percursos Formativos" (vigente desde 2026/1)

Duas fontes: o **template oficial vazio** ("Plano de ensino PUCPR - novo template (2026)", conseguido pelo usuário — a estrutura de fundo, com texto entre colchetes indicando o que é preenchido pelo NDE vs. pelo professor) e **7 planos reais preenchidos** (do repositório de desenvolvimento, todos Escola Politécnica — usados pra ver como professores de fato preenchem/estilizam por cima da estrutura oficial). Rodapé constante em toda página: "Percursos Formativos - Centro de Ensino e Aprendizagem da PUCPR (2026)" + logo "creare".

**Identidade visual**: faixa decorativa no topo de cada página com círculos em tom de roxo/magenta sobre fundo bordô/pink, selo circular vermelho da PUCPR na capa, título "Pontifícia Universidade Católica do Paraná" e títulos de seção em roxo/magenta. `scripts/preencher_template.py` preenche esse `.docx` oficial preservando a arte; `scripts/gerar_docx.py`/`gerar_pdf.py` geram do zero (só texto/tabelas, sem a arte) quando não há o template oficial disponível.

## Capa
Nome da disciplina (grande), nome do professor, "AAAA – Nº Semestre" (ex: "2026 – 2º Semestre"). Logo abaixo, tabela: Escola/Câmpus, Curso, Período, Turma, Turno, Carga Horária, Créditos, Carga Horária de Extensão, Requisitos.

## 1. Ementa
Parágrafo descritivo do que a disciplina cobre. **Propriedade do NDE do curso** — o template oficial vazio traz literalmente: "[Texto construído pelo NDE do curso, caso haja sugestões de ajustes o professor deverá contatar o NDE ou a coordenação do curso. A ementa explicita as aprendizagens a serem desenvolvidas na disciplina, envolvendo saber, saber-fazer e saber-ser.]". O professor não escreve do zero — cola o texto já aprovado (normalmente vindo do PPC do curso).

No BSI, a Ementa, os Temas e a Bibliografia vêm de `scripts/consulta_ppc.py "<disciplina oficial>"`, e os precedentes e posteriores da seção 2 vêm de `--precedencia`. Ementa igual à do PPC fica pré-aprovada; Ementa alterada, Contexto e Competências entram na lista de pendências do NDE gerada por `consulta_ppc.py --confere`, entregue junto com o `.docx`.

## 2. Contexto da Disciplina
**Propriedade do NDE do curso**, mesma regra da Ementa — texto oficial vazio: "[Texto construído pelo NDE do curso, caso haja sugestões de ajustes o professor deverá contatar o NDE ou a coordenação do curso. O contexto apresenta a relação desta disciplina com aprendizagens de disciplinas precedentes e contribuições para disciplinas posteriores.]". Na prática, os planos reais formalizam isso em tabelas (Código | Disciplina): disciplinas precedentes recomendadas e disciplinas que a atual prepara/beneficia depois. Se não houver pré-requisito formal, vira um texto corrido ("Esta disciplina não possui pré-requisitos, porém é recomendado que o estudante tenha cursado..."). Variação vista em alguns planos: tabela de 3 colunas (Código | Período | Nome da disciplina) — ambas são válidas.

## 3. Competência(s), Temas de Estudo e Resultados de Aprendizagem
**Propriedade do NDE do curso** — o próprio título da seção no template oficial traz a instrução: "[Este item é construído pelo NDE do curso, caso haja sugestões de ajustes o professor deverá contatar o NDE ou a coordenação do curso.]". Ajuste passa por eles, não é o professor que inventa. O template oficial define **2 tabelas mutuamente exclusivas por tipo de disciplina** (apaga a que não usa; disciplina mista mantém as duas):

**Disciplinas Internalizadoras e Mobilizadoras** (não certificam competência) — tabela de 5 colunas: Competência | Elementos de Competência | I/M (Internaliza/Mobiliza) | Temas de Estudo | Resultados de Aprendizagem.

**Disciplinas Certificadoras** (o Resultado de Aprendizagem É a própria competência a certificar) — tabela de 2 colunas: Resultado de Aprendizagem (Competência) | Temas de Estudo.

Os 7 planos reais mapeados são **todos do tipo Internalizadora/Mobilizadora** — nenhum exemplo real de Certificadora ainda (perguntar a um professor se ele tem algum, pra validar essa tabela). Dentro do tipo Internalizadora/Mobilizadora, o **estilo visual** varia por professor — mesma estrutura de dado, apresentação diferente:

| Disciplina | Estilo visual |
|---|---|
| Data Analytics, Inteligência Artificial, Raciocínio Algorítmico (Turma U) | 3 tabelas separadas (Variante A): **Temas de Estudo** (Nº \| Descrição), **Competências** (Nº C \| Competência \| Nº EC \| Elementos de Competência \| classificação I/M/Certifica), **Resultados de Aprendizagem** (EC \| Nº RA \| descrição \| Tema de estudo) |
| AI-Assisted Python, Engenharia de Software, Especificação de Software, Gestão de Projetos, Métodos e Ferramentas | 3 tabelas separadas (Variante B): mesma estrutura de 3 tabelas, mas a tabela de Competências tem 4 colunas (sem a coluna de classificação I/M, exigindo preenchimento manual) |
| Desenvolvimento de Carreira, Desenvolvimento de Jogos com Unreal, Raciocínio Algorítmico (Turma A), Resolução de Problemas Estruturados | Tabela única de 5 colunas (Competência \| Elementos de Competência \| I/M \| Temas de Estudo \| RA), igual à estrutura oficial |
| Experiência Criativa - Projetando Sistemas de Informação, Template Oficial Tokenizado | Tabela única de 4 colunas (Competência agregando EC \| I/M \| Temas \| RA; em Experiência Criativa a primeira coluna traz o RA e a quarta a competência) |

- **Imagem/diagrama de fechamento** (opcional, template oficial diz literalmente "se não utilizar, retirar este item"): nos 7 planos mapeados, todos têm alguma imagem no fim da seção 3, mas só 2 (Data Analytics, Inteligência Artificial) rotulam como "Mapa Mental". Os outros 5 colocam a imagem direto, sem título, e o conteúdo varia — mapa mental, diagrama de processo (ex: pipeline ETL), até screenshot de aplicativo (Unreal). Não é convenção fixa da PUCPR, é escolha por professor — a entrevista pergunta se quer incluir, com que título (ou nenhum). A skill não gera a imagem em si, só reserva o espaço no documento.

## 4. Alinhamento Construtivo: Metodologia e Avaliação
**Diferente das 3 seções acima: aqui não há regra de NDE.** O template oficial diz explicitamente que "o formato desta descrição é de escolha do professor" — é ele quem decide como descrever avaliação e composição de notas, sem precisar de aprovação do NDE.

Uma tabela por RA: Resultado(s) de aprendizagem | Indicadores de desempenho (IDx.y) | Metodologias/recursos/estratégias de ensino-aprendizagem | Processos de avaliação e recuperação de aprendizagem — este último detalha por tipo: `[Diagnóstica]`, `[Formativa]`, `[Somativa]`, `[Recuperação]` (ao longo do semestre e/ou estendida), cada um com o feedback e formato descritos.

Variação vista em alguns planos: tabela de 3 colunas de Indicadores de Desempenho (`Resultado(s) de aprendizagem | Nº/ID | Indicador de desempenho`), associada ou separada das metodologias e avaliações.

**% de cada RA na nota final** aparece de formas diferentes conforme o professor — a entrevista (Bloco 3) pergunta qual usar, sem assumir uma única:
- % simples por RA, ou % por instrumento dentro do RA com fórmula ponderada final (`Nota = (35×RA1 + 65×RA2)/100`).
- Pontos absolutos somando 10 (ex: RA1 = 3 pontos, RA2 = 7 pontos).
- % embutido entre parênteses no próprio rótulo do RA dentro desta tabela (ex: `RA1. ... (30%)`), sem tabela/fórmula separada.
- Tabela dedicada **"Avaliações Somativas"** logo antes do cronograma: `RA | Somativa | Nota das atividades no RA | Nota do RA na nota semestral (%)`.
- Sem fórmula nenhuma — só prosa vaga ("Nota da Disciplina calculada a partir das atividades propostas").

## 5. Cronograma de Atividades Pedagógicas
No template oficial a coluna se chama **"Período (dia, semana, quinzena ou mês)"** — não "Data", e sem coluna "#". Os 7 planos reais, na prática, sempre usam dia específico com "Data" (`DD/MM`) + "#" numerado — por isso é o padrão sugerido da skill, mas a entrevista pergunta a granularidade (Bloco 4, item 3) porque o template oficial permite as outras.

Tabela com 5 colunas: **# | Data/Período | RA | Descrição das atividades pedagógicas | Carga horária**.
- `#`: número sequencial da sessão — **em branco** para linhas administrativas sem data de aula fixa (ex: "Semana de Recuperação Estendida").
- `Data` (granularidade "dia", padrão): formato brasileiro `DD/MM` (padrão sugerido, sem ano) ou `DD/MM/AAAA` (com ano) — confirmado na entrevista, vira `formato_data` em `dados.json`. Intervalo de datas (`DD/MM–DD/MM`, visto em 1 caso) não é gerado automaticamente — ajuste manual se o professor pedir.
- `Período` (granularidade "semana"/"quinzena"/"mês"): rótulo do bucket (ex: "Semana de 04/08 a 08/08") — a carga horária e a descrição da linha somam/agrupam os encontros daquele período; a matemática de % por RA não muda, só a apresentação.
- `RA`: `-` para atividades institucionais não ligadas a um RA específico (Acolhida Cultural, Semana Acadêmica, Feedback de notas) e para linhas de feriado. Também aceita múltiplos valores (`RA1, RA2`, aula que revisa mais de um RA) ou o literal `Todos` — ajuste manual, o calculador não gera isso sozinho.
- `Carga horária`: formato `HH:MM` (ex: `04:00`).
- **Feriados nacionais**: por padrão somem do cronograma (excluídos via BrasilAPI). Se o professor pedir (`feriados_como_linha: true` em `dados.json`), aparecem como linha normal numerada, `RA: -`, descrição `Feriado`, com a carga horária do dia — sem consumir a meta de nenhum RA.
- **2ª chamada** (exigência do template oficial, Art. 29 da Resolução 414/2024 CONSUN): as datas previstas devem estar sinalizadas no cronograma. Se caem num encontro já calculado, anota na descrição (`+ " [2ª Chamada]"`); se não, entram como linha própria. Vira `datas_2a_chamada` em `dados.json`.
- **TDE**: numeração sequencial no plano inteiro na ordem de aparição: `TDE 01 – <descricao>` (dois dígitos, travessão `–`), ou `TDE` caso não tenha descrição. Com integração entre disciplinas, acrescenta ` (integrado com <disciplina>)` (ex: `TDE 01 – Atividade (integrado com Matemática)`). TDE com data entra na posição cronológica dentro do bloco do RA, com data formatada pelo mesmo `formato_data` das aulas e `#` numerado sequencialmente. Se a data cair em feriado/recesso com `feriados_como_linha: true`, a linha vira combinada `<descrição do feriado> (TDE NN – <descricao>)` com a carga horária do TDE e RA correspondente; se não gera linha de feriado, entra como linha própria na data. TDE sem data entra no fechamento do bloco com `[professor define a data]` e `#` em branco (`indice: null`). Carga horária na coluna própria em formato `HH:MM`.
- **Estilo padrão da tabela** (`assets/template-oficial-tokenizado.docx`): texto preto, Período/RA/Carga horária centralizados, Descrição alinhada à esquerda. Linhas de avaliação somativa (fechamento de RA) costumam vir destacadas com uma cor de fundo diferente nos planos reais — replicado via flag `"_destaque": true` na linha, em `linhas_repetir` de `preencher_template.py` (pinta a linha de vermelho mais fraco, `F2DCDB`; ajuste manual de quem monta `documento.json`, nenhum script decide isso sozinho).
- Nota de rodapé da tabela: `*O cronograma está sujeito a alterações conforme necessidade.`
- Variação vista em `Experiência Criativa - Projetando Sistemas de Informação`: tabela de 3 colunas (`Ano/Mês | Dia | Atividades desenvolvidas`), sem RA nem carga horária explícita na linha. O extrator mapeia o dia/mês para `DD/MM` em `CRONO_PERIODO` e gera aviso de que RA e carga horária precisam ser conferidos/preenchidos manualmente.
- Ver `../scripts/gerar_cronograma.py` — essa seção é calculada, não preenchida à mão.

## Regras da Disciplina (seção opcional, fora do template oficial)
**Achado importante**: o template oficial vazio da PUCPR **não tem essa seção** — vai direto de Cronograma (5) pra Bibliografia (6) e Orientações Gerais (7). Mas os 7 planos reais mapeados (todos Escola Politécnica) **sempre a têm**, como seção 6 (deslocando Bibliografia pra 7, Orientações Gerais pra 8) — parece ser convenção adicionada pela Escola, não parte do template central. A entrevista (Bloco 1) pergunta se a Escola do professor exige.

Quando presente, estrutura fixa observada, com pequenas variações de escola/curso:
- Texto introdutório remetendo aos RAs/IDs/metodologia da seção 4.
- Lista com marcadores, negrito no rótulo: **Diagnóstica**, **Formativa**, **Somativa** (o que cada uma é e se compõe a nota), **Recuperação ao longo do semestre** (cita a Instrução Normativa vigente — conferir o número correto com o professor, ex: "01/2026" em Data Analytics), **Recuperação Estendida** (regras de nota mínima/máxima), **Nota da Disciplina** (fórmula, ex: `Nota = RA1 + RA2 + RA3` ou com pesos).
- **Segunda chamada**: cita a Resolução institucional vigente (ex: "414/2024") e o contato da secretaria da escola/câmpus responsável — **pedir ao professor o contato correto da sua escola**, não é o mesmo em todo curso.
- Regras de entrega: meio de entrega (AVA), autoria em atividades em grupo, honestidade intelectual.

## 6. Bibliografia (nº 7 se a disciplina tiver seção "Regras da Disciplina")
**Básica** e **Complementar** — no template oficial não há subseções numeradas (6.1/6.2), embora os planos reais costumem numerar (7.1/7.2). Referência completa (autor, título, edição, cidade, editora, ano, ISBN quando houver), em um de 3 formatos, confirmado na entrevista: tabela `Nº | Referência` (padrão sugerido), lista numerada, ou bullets — os últimos dois vistos com mais frequência nos planos reais mapeados. Igual à Ementa/Contexto/Competências, normalmente vem pronta do PPC/NDE do curso — o professor cola o texto existente. Texto oficial do template (citação literal):

**Básica**: "[As Referências Bibliográficas das disciplinas constam nos PPC de cada curso. Assim, essa informação também é fornecida pelos NDE. **No mínimo 3 títulos por disciplina**, dando preferência para aqueles encontrados na biblioteca virtual e para os títulos com maior número de exemplares por estudante disponíveis na biblioteca, e 1 título de periódico considerando que esteja disponível em texto completo e acessível dentre as bases adquiridas pela PUC, há mais orientações no manual de apoio.]"

**Complementar**: "[**No mínimo 5 títulos por disciplina**, desde que haja pelo menos 1 exemplar físico na biblioteca, e mais 1 título de periódico.]"

### Validação via Pergamum e DOAJ

`scripts/verifica_bibliografia.py` busca/valida as referências no catálogo Pergamum da PUCPR direto por API (pública, sem login):

```
GET https://pergamum-biblioteca.pucpr.br/api/consulta
    ?termo_pesquisa={termo}&coluna_um=LIVRE&search_tab=pesquisa_geral&search_id={id}&page=1&perPage=20&orderBy=ano_publicacao&direction=D
```

Cada resultado traz `cod_acervo` (id do item), `referencia_sem_tag` (referência já formatada em ABNT), `desc_tipo_obra`/`classificacao` (indica e-book/Biblioteca Virtual) e `tot_exemplares` (nº de exemplares físicos). O script normaliza isso em `classifica_registro()` (campos: `cod_acervo`, `referencia`, `obra`, `link`, `e_virtual`, `tot_exemplares`, `autor`, `ano`) e confere os mínimos acima em `checa_minimos()` — nunca decide sozinho qual referência entra, só gera avisos pro professor resolver (mesmo padrão de `verifica_calendario_institucional.py`).

Convenção de link (já usada em 2 dos 7 planos reais mapeados, mas não documentada até agora): cada referência achada no Pergamum entra no texto final com `(Link acervo Pergamum: https://pergamum-biblioteca.pucpr.br/acervo/{cod_acervo})` ao final.

**Periódico obrigatório (1 por bloco)**: o fluxo padrão busca periódicos científicos de acesso aberto no DOAJ (`GET https://doaj.org/api/search/journals/{tema}?pageSize=10`) via `--periodico "<tema>"`. O professor escolhe na lista de candidatos e o link público (`https://doaj.org/toc/{issn}`) é adicionado; `checa_minimos()` não emite aviso de confirmação manual para periódicos DOAJ. Se o professor preferir indicar um periódico de base paga (Portal CAPES, Oxford, ProQuest etc.), informa manualmente e `checa_minimos()` emite aviso para confirmar a disponibilidade em texto completo nas bases com login institucional. Se o bloco estiver sem periódico, `checa_minimos()` avisa que falta o periódico obrigatório citando o bloco.

## 7. Orientações Gerais (nº 8 se a disciplina tiver seção "Regras da Disciplina")
**Orientações para uso de Inteligência Artificial Generativa (IAGen)** — texto oficial, usar literal (só ajustar o número da resolução se a instituição atualizar):

> De acordo com a Resolução nº 274/2024 CONSUN, a utilização de ferramentas de Inteligência Artificial Generativa (IAGen) no ensino, aprendizagem e pesquisa da PUCPR deverá ocorrer de acordo com orientações explícitas do docente, que indicará quando, se e de que forma o uso pode acontecer. Ao utilizar qualquer ferramenta de IA, o estudante deve declarar explicitamente o uso, incluindo a seguinte declaração padrão nos materiais produzidos:
>
> "Durante a preparação deste [TIPO DE CONTEÚDO], o(s) autor(es) usaram [FERRAMENTA, VERSÃO] para [EXPLICITAR MOTIVOS]. Após usar essa ferramenta, o(s) autor(es) revisaram e editaram o conteúdo conforme necessário e assumem total responsabilidade pelo conteúdo."
>
> Clique aqui para acessar as Diretrizes para uso de IA (Inteligência Artificial) na PUCPR

**Link para documentos institucionais** sobre avaliações, faltas, tratamento especial, Prêmio Marcelino Champagnat e outros — texto padrão + link.

## Global Classes (plano em inglês)

Algumas disciplinas são do programa **Global Classes** e têm o plano escrito em inglês. O repositório de desenvolvimento tem um par real (PT e EN) desse tipo de plano, usado para derivar o template EN.

**Dicionário PT -> EN** (`TRADUCAO_EN` em `scripts/extrai_plano_existente.py`, junto dos headings PT; `limpar_template_oficial.py` importa de lá): headings, rótulos da capa, cabeçalhos de tabela, Orientações Gerais e rodapé. Os headings (mesmas chaves do extrator nos dois idiomas):

| Chave | PT | EN |
|---|---|---|
| `ementa` | EMENTA: | COURSE DESCRIPTION: |
| `contexto` | CONTEXTO DA DISCIPLINA | COURSE CONTEXT |
| `competencias` | COMPETÊNCIA(S), TEMAS DE ESTUDO E RESULTADOS DE APRENDIZAGEM | COMPETENCIES, STUDY TOPICS, AND LEARNING OUTCOMES |
| `alinhamento` | ALINHAMENTO CONSTRUTIVO: METODOLOGIA E AVALIAÇÃO | CONSTRUCTIVE ALIGNMENT: METHODOLOGY AND ASSESSMENT |
| `cronograma` | CRONOGRAMA DE ATIVIDADES PEDAGÓGICAS | COURSE SCHEDULE |
| `regras_disciplina` | REGRAS DA DISCIPLINA | COURSE RULES (*sem par real*) |
| `bibliografia` | BIBLIOGRAFIA | REFERENCES |
| `orientacoes` | ORIENTAÇÕES GERAIS | GENERAL GUIDELINES |

Os textos EN vêm do `.docx` EN real sempre que ele tem o par. O template PT tem alguns textos que o plano EN real não tem (ex: "Regras da Disciplina", "Disciplinas Certificadoras", "Mapa Mental", cabeçalhos da seção 3/4/cronograma do template): esses são tradução montada com o vocabulário do EN real e ficam num bloco separado do dicionário, marcado "sem par real" — revisar com o NDE/Global Classes antes de tratar como texto oficial. O `.docx` EN real também tem diferenças de layout em relação ao template PT (ex: cronograma com colunas `#`/`Study Topic`); o template EN só troca os textos, mantém o layout do PT.

**Ementa bilíngue** (modelo Big Data): texto da ementa + nota do programa ("Importante: esta disciplina é ofertada no nível I do programa Global Classes.") e, em outro parágrafo, o bloco "(Syllabus) ..." em inglês. O extrator separa em `valores["EMENTA"]` (parte PT) e `valores["EMENTA_EN"]` (bloco inglês, com o rótulo, sem perder texto); "(Syllabus)" no meio de um parágrafo não é separado e vira aviso. Pra gerar, os dois blocos entram juntos em `EMENTA`.

**Template EN**: `assets/template-oficial-tokenizado-en.docx`, gerado por `python3 scripts/limpar_template_oficial.py --en` a partir do tokenizado PT (troca só os textos fixos, inclusive o rodapé "Learning Pathways – PUCPR Center for Teaching and Learning (2026)"; tokens `{{...}}` idênticos aos do PT). Texto fixo sem entrada no dicionário fica em português e sai como `aviso:` — roda de novo quando o tokenizado PT ou o dicionário mudarem.

**Limites atuais**: o extrator reconhece os headings e os rótulos da capa em inglês, mas ainda não os cabeçalhos de tabela da seção 3 nem os marcadores "Core/Supplementary References:" — num plano EN, `IM_RA` e a bibliografia saem vazios, com aviso.

## Nota sobre a geração anterior do template ("CrEAre", até 2025)

Planos de ensino de 2024/2025 seguem um template mais antigo (rodapé "CrEAre – Centro de Ensino e Aprendizagem da PUCPR"), com seções e nomes diferentes (ex: "Acessibilidade" e "Adaptações para práticas profissionais" como itens separados, sem "Orientações Gerais"/IAGen). A skill gera sempre no formato atual (Percursos Formativos); a geração antiga só é relevante se o professor pedir explicitamente pra consultar/migrar um plano legado.

## Sobre o `.docx` editável oficial

Conseguido — "Plano de ensino PUCPR - novo template (2026)". Sem content controls nem comentários, só texto entre colchetes indicando o que o NDE/professor preenche. Fonte de verdade pra estrutura oficial (seções, nomes de coluna, tabelas de seção 3) documentada acima. Arquivos em `assets/` (o quarto, o template EN, está na seção "Global Classes" abaixo):
- `assets/template-oficial-pucpr.docx` — o arquivo original, intocado (referência, e fonte se a PUCPR atualizar o template).
- `assets/template-oficial-tokenizado.docx` — o mesmo arquivo com os colchetes de instrução trocados por `{{PLACEHOLDER}}` (ver `scripts/limpar_template_oficial.py`), pronto pra `scripts/preencher_template.py` consumir. Roda a limpeza de novo só se o template oficial mudar.
- `scripts/preencher_template.py` preenche o tokenizado com os dados da entrevista, preservando a arte institucional (faixa, selo, cores, logo "creare") — via substituição de string no XML bruto, nunca reserializando a árvore inteira (ver docstring do script pro porquê).

`scripts/gerar_docx.py`/`gerar_pdf.py` continuam existindo como alternativa sem a arte institucional (só texto, tabelas e rodapé), útil se algum dia o `.docx` oficial não estiver disponível.

## Layout fixo por página (`assets/template-oficial-tokenizado.docx`)

`scripts/limpar_template_oficial.py` marca `w:pageBreakBefore` nos headings de 5 seções, fixando o agrupamento por página independente de quanto texto vem antes:
- Capa + tabela de identificação sozinhas na 1ª página (quebra antes de "1. Ementa").
- Ementa (1) + Contexto da Disciplina (2) juntos.
- Competências (3) sozinha (quebra antes dela).
- Alinhamento Construtivo (4) sozinha (quebra antes dela).
- Cronograma (5) sozinha — pode espalhar por várias páginas conforme o nº de linhas, mas sempre começa numa nova (quebra antes dela).
- Bibliografia (6) + Orientações Gerais (7) juntas (quebra antes de Bibliografia, nenhuma antes de Orientações Gerais).

Se o template oficial da PUCPR mudar de estrutura, reconferir esses 5 textos de heading em `main()` do script — o casamento é por texto exato do parágrafo.
