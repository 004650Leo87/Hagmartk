# HAGMARTK — Cycle Theory V111 Fidelity Patch

Este pacote adiciona a implementação research/fidelity da Teoria dos Ciclos V111
sem alterar HDF, Shadow live ou execução real.

Inclui uma correção de fidelidade adicional identificada na revisão independente:
ordens Limit agora preservam o volume submetido quando são preenchidas no MockBroker.
O port recebido anteriormente criava toda posição preenchida com volume fixo 0.01.

Validação deste pacote:
- 43 testes de fidelity passaram
- compileall passou

Ainda NÃO é prova final de paridade MQ5 ↔ HAGMARTK.
OrderCalcMargin continua modelado no research broker, e deep parity com eventos/ticks
reais deve ocorrer antes de qualquer otimização ou produção.
