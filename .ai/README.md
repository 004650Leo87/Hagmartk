# Hagmartk AI Framework (HAF)

## 1. Objetivo
A pasta `.ai` foi criada para abrigar a fundação de infraestrutura de engenharia inteligente do Hagmartk. O objetivo é centralizar agentes autônomos, prompts de contexto, bases de conhecimento, históricos e memórias do desenvolvimento para orquestrar a evolução do projeto conduzida por IA.

## 2. Finalidade do Hagmartk AI Framework (HAF)
O HAF é a espinha dorsal metodológica para o desenvolvimento de software assistido por IA. Ele serve para:
- Padronizar o contexto e as restrições que agentes autônomos (como o Codex e outros modelos) devem respeitar ao modificar a base de código do Hagmartk.
- Registrar histórico de decisões arquiteturais.
- Validar conformidade de código antes e depois da implementação.
- Evitar regressões e perda de contexto durante transições de desenvolvimento ou trocas de sessões de IA.

## 3. Estrutura Inicial Prevista (Referência Futura)
A estrutura será populada gradativamente com os seguintes diretórios operacionais:

- **00-core**: Módulos vitais, regras e definições absolutas do framework HAF.
- **01-agents**: Configurações de personas de agentes autônomos e seus níveis de permissão.
- **02-memory**: Registros textuais/json para retenção de contexto de longo prazo (long-term memory).
- **03-prompts**: Engenharia de prompts padronizados para tarefas específicas e templates interativos.
- **04-workflows**: Arquivos definindo sequências automáticas de execução (ex: linting seguido de build).
- **05-knowledge**: Base de conhecimento com domínios de negócio e regras do mercado financeiro (Trading/MT5).
- **06-templates**: Modelos padronizados para a geração de novos componentes, funções ou testes.
- **07-audits**: Relatórios imutáveis gerados a cada nova inspeção e validação do repositório.

## 4. Filosofia de Desenvolvimento
A evolução do Hagmartk é pautada nos seguintes princípios:
- **Mutabilidade Controlada:** IA não deve adivinhar ou destruir estruturas sem validação explícita.
- **Rastreabilidade Absoluta:** O contexto anterior deve sempre orientar a próxima ação.
- **Test-Driven AI:** O desenvolvimento não termina com o código; a validação funcional é inegociável.
- **Idempotência Arquitetural:** Regras de arquitetura devem ser restritivas ao longo das iterações, garantindo padronização contínua.

## 5. Fluxo Oficial de Engenharia
Todos os agentes e sessões que operam sob o contexto do HAF devem obedecer rigorosamente ao seguinte pipeline:

1. **Análise**: Leitura inicial e entendimento do estado atual do repositório, dependências e relatórios recentes.
2. **Diagnóstico**: Identificação clara de gaps, vulnerabilidades e escopo real a ser modificado.
3. **Planejamento**: Proposição de um plano de ação (com passos reversíveis) aguardando aprovação explícita.
4. **Implementação**: Escrita focada no código, restrita aos arquivos previstos no planejamento, com commits pequenos e sem efeitos colaterais.
5. **Validação**: Verificação sintática e estática, build dry-run e simulação de ambiente (lints, tipagem, formatação).
6. **Testes**: Geração ou manutenção dos testes automatizados e execução da suíte (pytest, jest, vitest) para confirmar as alterações.
7. **Documentação**: Atualização da base de conhecimento (05-knowledge), registros de memória e relatórios de auditoria (07-audits).
8. **Commit**: Efetivação das alterações no repositório com rastreabilidade, vinculando a tarefa atual aos registros de auditoria.