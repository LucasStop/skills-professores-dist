# Matriz de Competências BSI (Figura 9 do PPC)

`matriz-competencias-bsi.json` = as 44 disciplinas do curso × 11 Elementos
de Competência (EC A1-A4, EC B1-B4, EC C1-C3), com o tipo de contribuição
de cada disciplina a cada EC — Internaliza (amarelo), Mobiliza (laranja)
ou Certifica (vermelho), ausente = sem relação. Fonte de verdade pra
derivar "disciplina precedente/posterior" de forma automática: uma
disciplina que Internaliza um EC num período cedo é precedente de uma que
Mobiliza/Certifica o mesmo EC num período posterior (task original do
backlog).

## Como foi extraído

A figura é uma imagem (`word/media/image16.png` dentro do `.docx` do PPC,
achada via bookmark `_Toc173482417` → `rId54`), não texto — não dá pra
extrair com `markitdown`/regex como o ANEXO A. Processo:

```
unzip -j "skills/plano-de-ensino/references/fontes/PPC_BSI_2023_02082024VR.docx" "word/media/image16.png"
```

A imagem tem grade regular (linhas/colunas pretas puras) e as 3 cores de
contribuição são sólidas e distintas (`(255,255,0)` amarelo,
`(237,125,49)` laranja, `(255,0,64)` vermelho, `(255,255,255)` vazio) —
em vez de transcrever visualmente célula por célula (44×11 = 484, alto
risco de erro), detectei a grade programaticamente (`PIL`, scan de linha
de pixel preto) e classifiquei cada célula pela cor mais próxima das 4
referências. Nomes de disciplina e período foram lidos visualmente da
imagem (crops com zoom), cruzados manualmente com a ordem período→CH que
já bate com o ANEXO A.

## Cruzamento com `ppc-bsi-anexo-a.json` e juntador de nomes

O PPC usa grafias diferentes para a mesma disciplina entre a Figura 9 e o
ANEXO A (acentuação, abreviação, ordem trocada e erros de digitação).
O script `skills/plano-de-ensino/scripts/consulta_ppc.py` implementa a junção
automática e tolerante sem similaridade difusa em três etapas:

1. **Igualdade normalizada**: remoção de acentos (`NFKD`), pontuação (`[^\w\s]`),
   minúsculas e colapso de espaços em branco (resolve caixa alta/baixa, acentos
   e o asterisco `*` de disciplina extensionista presente apenas no ANEXO A).
2. **Igualdade de conjunto de palavras**: resolve ordem trocada de palavras:
   - `Inovação e Empreendedorismo em Sistemas de Informação` (Matriz) vs
     `Empreendedorismo e Inovação em Sistemas de Informação` (ANEXO A).
3. **Dicionário explícito `APELIDOS`**: para os casos que a normalização pura
   não cobre:
   - `Clínica de TIC` (Matriz) vs `Clínica de Tecnologia da Informação e Comunicação` (ANEXO A) — sigla institucional;
   - `Fundamentos de Sistemas Ciber-Físicos` (Matriz) vs `Fundamentos de Sistemas Ciberfisicos` (ANEXO A) — hifenização;
   - `Conectividade de Sistemas Ciber-Físicos` (Matriz) vs `Conectividade de Sistemas Ciberfisicos` (ANEXO A) — hifenização;
   - `Performance em Sistemas Ciber-Físicos` (Matriz) vs `Perfomance em Sistemas Ciberfisicos` (ANEXO A) — hifenização e erro de digitação institucional ("Perfomance" sem 'r' no ANEXO A);
   - `Experiência Criativa: Implementação de Sistemas de Informação` (Matriz) vs `Experiência Criativa: Implementando Sistemas de Informação` (ANEXO A) — substantivo vs gerúndio;
   - `Database Performance Tunning` (Matriz) vs `Database Performance Tuning*` (ANEXO A) — erro de digitação institucional ("Tunning" com dois 'n' na Matriz);
   - `Resolução de Problemas Estruturados` (Matriz) vs `Resolução de Problemas Estruturados em Computação` (ANEXO A) — sufixo omitido na Matriz;
   - `Inovação nos Processos de Negócio` (Matriz) vs `Inovação nos Processos de Negócios` (ANEXO A) — singular vs plural.

Com essas regras, **todos os 44 pares casam legitimamente** entre os dois datasets
(`SEM_PAR = []`). Termos ambíguos ou inexistentes não são adivinhados: o script
devolve campos nulos e avisa os candidatos mais próximos por palavras em comum.

## Regra de derivação de precedência

Implementada em `consulta_ppc.py --precedencia "<disciplina>"`.
Para a disciplina X no período P, considerando cada elemento de competência (EC)
em que X possui contribuição na Matriz (Internaliza, Mobiliza ou Certifica):
- **Precedente**: disciplina Y de período anterior (`período < P`) que **Internaliza (I)** o mesmo EC;
- **Posterior**: disciplina Z de período posterior (`período > P`) que **Mobiliza (M)** ou **Certifica (C)** o mesmo EC.

As disciplinas são agregadas sem duplicatas (reunindo a lista de elementos que
justificam o vínculo) e ordenadas por período e nome. Disciplinas de 1º período
não possuem precedentes (`precedentes == []`); de 8º período não possuem
posteriores (`posteriores == []`).

> **Aviso institucional fixo**: Toda precedência gerada pela Matriz é uma
> sugestão automática baseada no PPC que deve ser confirmada pelo professor
> responsável no plano de ensino.

## Fora de escopo desta extração

Coluna "HR Ext" (horas de extensão por disciplina, populada só nas
disciplinas de Experiência Criativa/Web Development/Análise e Design/
Inovação e Empreendedorismo) não foi capturada — não é relevante pra
derivar precedência, é dado do ANEXO B (curricularização da extensão).
