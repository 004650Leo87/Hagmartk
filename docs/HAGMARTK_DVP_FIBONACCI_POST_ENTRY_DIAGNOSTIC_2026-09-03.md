# HAGMARTK DVP — Fibonacci pós-entrada: diagnóstico de fronteira

Data: 2026-09-03

## Objetivo

Avaliar, sem promover regra de saída, se a mesma escada Fibonacci usada como confluência pré-reversão pode ser reutilizada como escada de objetivos após a entrada.

## Contrato congelado

- Coorte: 17 eventos HDF_DVP que passaram `STRICT_PRE_REVERSAL + MICRO_2_2` e efetivamente ativaram entrada.
- A escada analisada é a mesma derivada dos dois pivôs pré-reversão já conhecidos no instante da decisão.
- Apenas níveis ainda à frente da entrada, na direção da operação, foram acompanhados.
- Stop estrutural do padrão encerra a observação de cada nível.
- Nenhum nível é tratado aqui como regra oficial de saída.
- Não há otimização nem escolha retrospectiva de âncoras.
## Resultado agregado

- Eventos ativados avaliados: **17**.
- Sem qualquer nível pré-reversão ainda à frente da entrada: **4**.
- Com ao menos um nível ainda à frente: **13**.
- Ambiguidade intrabar nível/stop: **0**.

Por nível ainda à frente da entrada:

- 100%: 7 atingidos antes do stop; 2 stops antes do nível.
- 161,8%: 5 atingidos antes do stop; 6 stops antes do nível.
- 200%: 4 atingidos antes do stop; 8 stops antes do nível.
- 261,8%: 5 atingidos antes do stop; 8 stops antes do nível.
- 61,8%: nenhum caso permaneceu como nível futuro após a entrada.

Essas contagens têm denominadores diferentes porque nem todos os níveis permaneciam à frente da entrada em todos os eventos.
## Decisão

A hipótese "uma única escada Fibonacci serve simultaneamente como confluência de reversão e como escada universal de objetivos" está **rejeitada** para o motor atual.

Quatro eventos já haviam ultrapassado toda a escada antes da ativação. Nos demais, a quantidade de níveis futuros varia conforme a posição da entrada. Logo, reutilizar silenciosamente essa escada como target policy produziria uma regra inconsistente entre eventos.

Próximo gate de fidelidade: definir separadamente, com base em fonte, a construção Fibonacci de projeção de objetivos pós-reversão/pós-entrada. Até isso ser resolvido, os níveis medidos aqui são somente diagnóstico estrutural.

## Fronteira de interpretação

Isto não mede lucratividade da DIVAP original nem do HAGMARTK DVP. Também não valida percentuais de realização parcial. O resultado apenas demonstra que a construção Fibonacci usada para confirmar a reversão não deve ser promovida automaticamente como política de targets.
