# Relatório: o Pergamum acha as referências do PPC? (issue #14)

- **Data da medição:** 2026-11-13
- **Comando:** `python3 skills/plano-de-ensino/scripts/verifica_bibliografia.py --relatorio-ppc skills/plano-de-ensino/references/ppc-bsi-anexo-a.json`
- **Amostra:** todas as referências das 44 disciplinas (370 referências: 145 Básica + 225 Complementar), sem limite por disciplina.
- **Parâmetros:** timeout de 6 s por requisição, sem retry, intervalo de 0,5 s entre requisições, orçamento de 8 min (o que passasse disso contaria como erro; não foi atingido). Duração: 6 min 52 s.
- **Critério:** termo = primeiro sobrenome + 3 primeiras palavras do título; achada se algum resultado traz o sobrenome (normalizado, sem acento) e ao menos 2 das 4 primeiras palavras significativas do título.

## Totais

| Bloco | Total | Achadas | Não achadas | Erros |
|---|---|---|---|---|
| Básica | 145 | 121 | 6 | 18 |
| Complementar | 225 | 204 | 9 | 12 |
| Geral | 370 | 325 | 15 | 30 |

- **Taxa de acerto (achadas ÷ consultadas com sucesso): 95,59 %** (325 de 340).
- Se os 30 erros contassem como não achadas, a taxa seria 87,84 % (325 de 370).
- **Erros de rede: 30 de 370 consultas** (18 na Básica, 12 na Complementar), falha ou timeout de 6 s. Não foram repetidas, então a taxa vale para as 340 consultas que responderam.
- O critério de sobrenome aceita o sobrenome em qualquer parte do autor ou da referência do resultado, então pode superestimar um pouco os acertos.

## Referências não achadas (15)

| # | Bloco | Disciplina | Termo | Referência do PPC |
|---|---|---|---|---|
| 0 | Complementar | Raciocínio Algorítmico | `PIVA Algoritmos e programação` | 5. PIVA JUNIOR, Dilermando *et al.* **Algoritmos e programação de computadores.** 2. Rio de Janeiro: GEN LTC, 2019. (Link acervo Pergamum: https://pergamum-bib |
| 1 | Básica | Matemática Discreta e suas Aplicações | `SCHEINERMAN Matemática discreta –` | 2. SCHEINERMAN, Edward R. **Matemática discreta – Uma introdução**. Ed. Cengage Learning. São Paulo, 2016 |
| 2 | Complementar | Web Development: Front-End* | `TERUEL HTML 5 -` | 1. TERUEL, Evandro C. **HTML 5 - Guia Prático**. São Paulo: Editora Saraiva, 2013. E-book. ISBN 9788536519296. Disponível em: https://integrada.minhabiblioteca |
| 3 | Complementar | Web Development: Front-End* | `SOARES PHP 5 -` | 3. SOARES, Walace. **PHP 5 - Conceitos, Programação e Integração com Banco de Dados**. São Paulo: Editora Saraiva, 2013. E-book. ISBN 9788536505633. Disponível  |
| 4 | Básica | Experiência Criativa: Implementando Sistemas de Informação | `SOARES Php 5 Conceitos,` | 3. SOARES, Walace. Php 5 Conceitos, programação e integração com Banco de Dados. São Paulo, Erica, 2013. (e-book) |
| 5 | Básica | Mobile Development: Android* | `DEITEL Android como programar` | 3. DEITEL, Harvey M. **Android como programar**. |
| 6 | Complementar | Mobile Development: IOS* | `SOBRAL Design de interfaces` | 4. SOBRAL, Wilma Sirlange. **Design de interfaces:** introdução. São Paulo: Erica, 2019. 1 recurso online. (Eixos). ISBN 9788536532073. |
| 7 | Complementar | Análise e Design de Sistemas de Informação | `SOBRAL Design de interfaces` | 3. SOBRAL, Wilma Sirlange. **Design de interfaces: introdução**. São Paulo: Erica, 2019. (Eixos). ISBN 9788536532073. |
| 8 | Complementar | Data Analytics | `MATTOS – 1` | 3. MATTOS, Viviane Leite Dias de, Andréa Cristina Konrath, Ana Maria Volkmer de Azambuja ; Introdução à estatística: aplicações em ciências exatas / . – 1. ed.  |
| 9 | Complementar | Back-End: Cloud Computing | `TANENBAUM DE CAMARGO` | 4. TANENBAUM, ANDREW STUART ; DANIEL VIEIRA; JORGE RITTER; HERBERT BOS; RAPHAEL Y. DE CAMARGO. Sistemas operacionais modernos. Editora Pearson, 2016. 778 p. ISB |
| 10 | Complementar | Gestão de Equipes de Alto Desempenho | `CAPRONI J` | 1. CAPRONI, P. J. profissional, Treinamento Gerencial: como dar um salto significativo em sua carreira. 1°. ed. [S.l.]: Editora Pearson, 2001. 344 p. |
| 11 | Básica | Empreendedorismo e Inovação em Sistemas de Informação | `RIES Lean startup` | 3. RIES, Eric. **Lean startup:** a startup Enxuta. São Paulo: Sextante, 2019. |
| 12 | Básica | Governança de Tecnologia da Informação | `FERNANDES Implantando a governança` | 2. FERNANDES, Aguinaldo Aragon; ABREU, Vladimir Ferraz de. Implantando a governança de TI: da estratégia à gestão dos processos e serviços. Rio de Janeiro: |
| 13 | Básica | Inovação nos Processos de Negócios | `CAMPO Modelagem de Processos` | 3. CAMPO, André L.N. **Modelagem de Processos de Negócios com BPMN**. – 2. ed. São Paulo: BRASPORT, 2014. Disponível em: Biblioteca on line da PUCPR [Bibliote |
| 14 | Complementar | Desenvolvimento Ágil de Produto II | `BROWN Design Thinking –` | 1. BROWN, Tim. Design Thinking – Edição Comemorativa 10 anos. [Digite o Local da Editora]: Editora Alta Books, 2020. E-book. ISBN 9788550814377. Disponível em:  |

## Motivo provável (amostra de 10 das 15)

Conferi cada uma com uma busca manual mais simples (só sobrenome + palavra-chave). Os motivos são prováveis, não comprovados item a item.

- **#0**: provável erro do critério: a busca `Piva algoritmos` devolve `PIVA JUNIOR, Dilermando…` (autor presente no acervo); a ref. traz `2.` como edição e título com `de computadores`, e a checagem de título não casou.
- **#1**: erro do critério: o termo de busca ficou com o travessão (`Matemática discreta –`), e a busca simples `Scheinerman` devolve `Matemática discreta: uma introdução` (3. ed.) — a obra está no acervo.
- **#2**: erro do critério / título abreviado: o acervo tem `HTML5: guia prático` e `Html 5`; a grafia `HTML 5` e o termo terminado em `-` atrapalham.
- **#3**: edição diferente / título abreviado: o acervo tem `Php 5` (7. ed., 2013, Érica); a ref. traz o subtítulo longo e o termo com `5 -` não casou.
- **#5**: título abreviado / edição diferente: o acervo tem `Android` (2. ed.) e `Android 6 para programadores` dos Deitel; a ref. traz `Android como programar`, sem edição.
- **#6**: obra provavelmente fora do acervo: a busca `Sobral Design de interfaces` devolveu só 1 resultado sem relação (outro autor).
- **#11**: título diferente: a ref. traz `Lean startup: a startup Enxuta`; o acervo tem `RIES, Eric. A startup enxuta…` (a obra existe, o critério de título falhou).
- **#12**: edição diferente: o acervo tem `FERNANDES, Aguinaldo Aragon; COSTA, Ivanir; ABREU, Vladimir…` (outra edição, com 3 autores); a ref. do PPC é de 2008 com 2 autores.
- **#13**: obra provavelmente fora do acervo: `Campo Modelagem de Processos` devolveu só resultados sem relação (não conferi com outro termo).
- **#14**: obra provavelmente fora do acervo: nenhum resultado de BROWN para `Design Thinking`; só outros autores.

**Leitura:** das 10 da amostra, 7 têm a obra (ou outra edição) no acervo e escaparam por limitação do critério (termo com pontuação, título abreviado, título em português diferente, edição diferente), e 3 provavelmente estão fora do acervo. A taxa real de cobertura do Pergamum deve ser um pouco maior que 95,59 %.
