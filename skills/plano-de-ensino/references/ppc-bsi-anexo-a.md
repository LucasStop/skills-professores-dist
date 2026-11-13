# PPC BSI — ANEXO A extraído

`ppc-bsi-anexo-a.json` = as 44 disciplinas do ANEXO A ("Planos de Ensino")
do PPC do curso BSI (`skills/plano-de-ensino/references/fontes/PPC_BSI_2023_02082024VR.docx`), extraídas via
`scripts/extrai_ppc.py`. Fonte de verdade institucional pra Ementa, Temas
de Estudo, Bibliografia Básica/Complementar e Justificativa por disciplina
— usar em vez de pedir pro professor redigitar.

## Como regenerar

```
markitdown "skills/plano-de-ensino/references/fontes/PPC_BSI_2023_02082024VR.docx" > ppc.md   # ~32MB, demora
python3 scripts/extrai_ppc.py ppc.md > references/ppc-bsi-anexo-a.json
```

## Gaps conhecidos (do próprio PPC, não é bug de parsing)

- 7 disciplinas sem Professor preenchido no ANEXO A (Mobile Development:
  IOS, Desenvolvimento Ágil de Software, Design Patterns, Mobile
  Development: Framework, Back-End: Cloud Computing, Gestão de Equipes de
  Alto Desempenho, DevOps).
- "Management Science" tem uma segunda lista de referências logo após a
  Bibliografia Básica sem nenhum rótulo (nem "Bibliografia Complementar:"
  nem variante sem negrito) — o parser não adivinha, ignora a linha.

## Como consultar

Use o script `consulta_ppc.py` para consultar os dados oficiais de uma disciplina:

```bash
python3 skills/plano-de-ensino/scripts/consulta_ppc.py "<disciplina>"
```

A saída é um JSON estruturado com:
- `disciplina`: nome oficial da disciplina;
- `periodo`: número do período letivo (1 a 8);
- `ementa`: texto oficial da ementa;
- `temas_estudo`: lista numerada dos temas de estudo institucionais;
- `bibliografia_basica`: referências básicas formatadas do PPC;
- `bibliografia_complementar`: referências complementares do PPC;
- `justificativa`: texto justificativo de vínculo entre temas e bibliografias;
- `avisos`: lista de eventuais alertas (disciplina não encontrada, termos ambíguos ou candidatos sugeridos).

Para obter precedências e posteriores derivadas da Matriz de Competências, use a flag `--precedencia`:

```bash
python3 skills/plano-de-ensino/scripts/consulta_ppc.py --precedencia "<disciplina>"
```

Para conferir o alinhamento das seções do plano (Ementa, Contexto, Competências) em relação ao PPC e listar pendências do NDE, use a flag `--confere`:

```bash
python3 skills/plano-de-ensino/scripts/consulta_ppc.py --confere dados.json
```

A saída JSON contém `disciplina`, `pre_aprovadas`, `pendencias_nde` e `avisos`:
- **Ementa**: se for idêntica à do PPC (após normalização de espaços e quebras de linha), vai para `pre_aprovadas`; se diferente, vai para `pendencias_nde` com o motivo `"Ementa difere do PPC"` e resumo da contagem de palavras a mais/a menos; se ausente, vai para `pendencias_nde`;
- **Contexto** e **Competências**: vão sempre para `pendencias_nde` com o motivo `"sem texto de referência no PPC"`;
- **Disciplina fora do dataset**: todas as seções viram `pendencias_nde` com alerta explicativo em `avisos`.

## Fora de escopo e encerramento da frente Contexto/RA por disciplina no PPC

Contexto da disciplina (precedentes/posteriores) e Resultados de
Aprendizagem por disciplina **não existem em prosa individualizada no
PPC** — a seção 1.4 do PPC possui exclusivamente texto conceitual genérico
sobre a metodologia pedagógica do curso como um todo, sem detalhamento por
disciplina.

A ideia original de extração assistida por IA para Contexto e Resultados de
Aprendizagem a partir de texto corrido do PPC foi **formalmente encerrada por
falta de fonte documental no PPC**. A solução definitiva adotada divide as
responsabilidades:
- **Precedentes e Posteriores (Contexto)**: derivados formalmente via
  `matriz-competencias-bsi.json` e `consulta_ppc.py --precedencia`;
- **Resultados de Aprendizagem (RAs)**: extraídos do plano de ensino existente
  do professor via `extrai_plano_existente.py` ou definidos pelo professor
  durante a entrevista de elaboração do plano.
