# Constituição de Engenharia do Hagmartk

## 1. Propósito
Definir regras técnicas, operacionais e de governança para evolução segura, viável, mensurável e escalável do Hagmartk. Este documento governa qualquer trabalho realizado por humanos ou agentes de IA.

## 2. Princípios obrigatórios
- **Viabilidade antes de sofisticação**: Soluções simples que funcionam são superiores a arquiteturas complexas teóricas.
- **Evidência antes de afirmação**: Nenhuma funcionalidade está pronta sem logs, diffs e saídas de testes reais comprovando seu funcionamento.
- **Diagnóstico antes de alteração**: Nunca modificar um arquivo sem entender profundamente a causa raiz do problema atual.
- **Mudanças mínimas e reversíveis**: Favorecer pequenos commits e alterações localizadas que possam ser facilmente revertidas (rollback).
- **Preservação da arquitetura validada**: Respeitar as camadas, o EventBus e o Kernel da Arquitetura V2. Isolamento de domínios é inegociável.
- **Compatibilidade retroativa sempre que possível**: Não quebrar contratos de API ou estruturas de dados sem um processo rigoroso de transição.
- **Segurança de credenciais e dados**: Segredos nunca sobem para o repositório. O risco financeiro é controlado e monitorado por limites rígidos.
- **Observabilidade e rastreabilidade**: Código em produção deve poder ser diagnosticado rapidamente via logs estruturados e health checks.
- **Testes proporcionais ao risco**: Quanto maior o impacto no domínio financeiro ou core do sistema, maior a necessidade de cobertura rigorosa e estressada.
- **Valor concreto para o produto antes de aumento de complexidade**: Não adicionar camadas arquiteturais se o problema de negócio não exigir no momento.
- **Não introduzir tecnologia apenas por tendência**: Toda nova dependência ou framework deve ter um ROI (Retorno sobre Investimento) claro e justificável.
- **Não tratar possibilidade técnica como solução validada**: Protótipos não vão para produção sem validação sob carga real.

## 3. Fluxo oficial de trabalho
1. **Análise**: Inspeção do estado atual do repositório via leitura de arquivos e relatórios.
2. **Diagnóstico e causa raiz**: Investigação profunda para isolar o problema exato, separando sintomas de causas estruturais.
3. **Escopo e arquivos envolvidos**: Mapeamento restrito de todos os arquivos afetados.
4. **Avaliação de risco, custo e benefício**: Mensuração técnica (latência, complexidade) e financeira (tempo, uso de API) da alteração.
5. **Plano reversível**: Proposta estruturada passo a passo para execução e rollback, se necessário.
6. **Aprovação**: Revisão do plano pelo Architect (agente ou humano).
7. **Implementação localizada**: Codificação atômica focada apenas no escopo aprovado.
8. **Validação estática**: Execução rigorosa de linters e verificadores de tipagem (ex: oxlint, mypy).
9. **Testes automatizados**: Execução de suítes de teste (pytest, jest) mantendo ou aumentando a cobertura e garantindo contratos.
10. **Teste funcional**: Simulação realista nos limites do escopo (ex: inicializar o sistema sem conexão ao mercado para avaliar resiliência).
11. **Revisão de diff**: Inspeção de linha por linha do trabalho gerado comparado à base anterior.
12. **Documentação**: Atualização da base de conhecimento (05-knowledge), diagramas e registros arquiteturais necessários.
13. **Commit atômico**: Gravação da mudança no histórico, vinculada à sua motivação técnica.

## 4. Classificação de mudanças
- **Baixo risco**: Mudanças de estilo (CSS), textos, linters, ou pequenos bugs de display que não quebram lógica de negócio.
  - *Exigência*: Lints limpos e build passando. Aprovação Nível 3.
- **Médio risco**: Novos componentes Frontend, endpoints Backend puramente informativos, ou refatorações locais isoladas.
  - *Exigência*: Lints, build e testes unitários passando. Aprovação Nível 5.
- **Alto risco**: Modificação de contratos de API, mudanças no gerenciamento de estado global, atualizações de dependências críticas (ex: React, FastAPI).
  - *Exigência*: Todos os testes, validação estrita de regressão. Aprovação Nível 5 (obrigatória revisão estrita).
- **Mudança arquitetural**: Adição de novos Engines, alteração do Kernel, mudança no EventBus ou banco de dados.
  - *Exigência*: Revisão pelo Architect (Nível 7), ADR (Architecture Decision Record) preenchida, aprovação explícita obrigatória.
- **Mudança crítica de trading ou gestão de risco**: Qualquer alteração em lógica de entrada, saída, dimensionamento de lote (position sizing), ou integração direta com ordens MT5.
  - *Exigência*: Validação por Architect, testes de backtest (incluindo ticks reais e sensibilidade), simulação out-of-sample e forward test (dry-run). Nenhuma estratégia sobe sem métrica financeira validada.

## 5. Níveis de autonomia dos agentes
- **Nível 0**: Responder dúvidas técnicas sem realizar análises profundas no repositório.
- **Nível 1**: Inspecionar, ler e analisar o repositório, identificando estado atual (somente-leitura).
- **Nível 2**: Propor um plano de ação, baseado na análise do Nível 1.
- **Nível 3**: Editar código limitando-se restritamente ao escopo aprovado no Nível 2.
- **Nível 4**: Executar validações, builds e testes (interagir com ferramentas de terminal e scripts de CI locais).
- **Nível 5**: Revisar o código de outros agentes (Code Review) e recomendar aprovação/rejeição com base em evidências.
- **Nível 6**: Delegar tarefas, fragmentando escopos maiores em partes menores para Coders.
- **Nível 7**: Definir arquitetura, gerenciar a Constituição, tomar decisões sobre padrões globais e ter poder de veto final (O Architect).
> **Atenção**: Nenhum agente pode ultrapassar o nível recebido para a tarefa atual.

## 6. Regras de edição
- Ler integralmente os arquivos diretamente envolvidos antes de iniciar a edição para preservar o contexto local.
- Não reescrever um arquivo inteiro quando uma alteração localizada e cirúrgica for suficiente.
- Não modificar arquivos fora do escopo aprovado no planejamento (evitar o "já que estou aqui...").
- Listar previamente todos os arquivos que sofrerão impacto (se forem muitos, reavaliar o escopo).
- Não alterar nomes de variáveis, contratos, estilos ou comportamento de funções que não possuam relação direta com a tarefa imediata.
- Não instalar dependências (npm, pip) sem justificativa clara, análise de impacto e aprovação explícita.
- Não apagar código apenas por parecer antigo ou mal otimizado, sem entender o histórico.
- Não ocultar falhas silenciosamente com fallbacks artificiais ou dados mockados fabricados (a menos que seja explicitamente um ambiente de teste isolado).
- Interromper a edição imediatamente se a causa raiz da falha que originou a tarefa não estiver suficientemente comprovada.

## 7. Regras de validação
As validações são exigidas de acordo com o domínio afetado:

**Frontend**:
- Lint (`npm run lint`).
- Build sem erros (`npm run build`).
- Teste funcional (quando interativo).
- Regressão visual (verificar distorções na UI) quando aplicável.

**Backend**:
- Execução de testes na virtual environment (`.venv`) correta.
- Uso do `PYTHONPATH` correto durante a execução.
- Teste de endpoints (rotas respondendo adequadamente e respeitando schemas).
- Verificação cautelosa de logs de erro e exceções tratadas (sem traceback silencioso).

**MT5 e mercado**:
- Verificação de conexão ativa/inativa.
- Mapeamento correto de símbolos, limites e propriedades de timeframes.
- Consistência histórica (merge sem duplicação de candles, offset correto).
- Consideração sobre variação de spread e ticks.
- Conta correta retornando o patrimônio e posições reais.
- Comportamento de fallback estruturado e elegante em cenários de terminal desconectado ou indisponível.

**Estratégias e EAs**:
- Backtest rigoroso operando com modelagem de ticks reais.
- Divisão de amostras de dados rigorosas: In-sample (IS) e Out-of-sample (OOS).
- Avaliação com metodologia Walk-forward (quando viável).
- Simulação de Monte Carlo para avaliar rebaixamento máximo estressado.
- Teste de sensibilidade de parâmetros.
- Simulação obrigatória de restrições do mundo real: spread dinâmico, comissão e latência (slippage).
- Validação em ambiente simulado avançado (Forward test em Demo).
- Mecanismos explícitos de prevenção contra viés preditivo (look-ahead bias), recálculo retroativo (repaint) e sobreajuste de curva (overfitting).

## 8. Governança de arquitetura
Decisões arquiteturais relevantes devem ser formalizadas via registros claros (o conceito de ADR - Architecture Decision Record, embora não exija um template rígido de arquivo agora), contemplando obrigatoriamente:
- Problema central resolvido.
- Alternativas analisadas (com prós e contras).
- Decisão adotada.
- Justificativa técnica ou de negócio.
- Consequências (trade-offs assumidos).
- Riscos residuais e mitigações.
- Data e responsável (Agente/Humano) pela decisão.

## 9. Segurança
- NUNCA exibir ou registrar chaves de API, senhas ou tokens sensíveis nos relatórios ou logs de análise.
- NUNCA inserir segredo no código-fonte para ser enviado em commit (sempre usar variáveis de ambiente ou secrets management).
- NUNCA executar comando de terminal de natureza destrutiva (`rm -rf`, `drop table`, `git reset --hard`) sem aprovação explícita e redundante.
- NUNCA usar uma conta real (live account) para testes iniciais, validações de fluxo ou backtest de desenvolvimento.
- NUNCA ativar ou permitir a ativação de qualquer automação financeira sem que limites absolutos de risco e chaves globais de desligamento de emergência (kill switches) estejam implementados e testados.
- Dados sensíveis de clientes ou contas devem ser minimizados no tráfego e devidamente isolados da camada pública.

## 10. Regras para trading e risco financeiro
- Nenhuma estratégia ou robô pode ser considerado "válido" ou "lucrativo" apenas por apresentar uma curva de backtest positiva.
- Nenhuma métrica isolada (ex: Win Rate ou Profit Factor) comprova a robustez operacional sistêmica.
- Todo risco aceito na operação deve ser calculado e restrito de forma monetária e percentual em relação ao patrimônio no momento da execução.
- Estratégias devem ser categorizadas e avaliadas cruzando diferentes regimes de mercado (tendência clara, lateralização, alta volatilidade, baixa liquidez).
- Os resultados financeiros expostos por backtests ou simulações devem obrigatoriamente descontar e separar custos transacionais: spread, comissão da corretora, swap e slippage estimado.
- Alterações em lógicas de entrada, algoritmos de saída, dimensionamento de lote (position sizing), posições de stop-loss ou rotinas de trailing/proteção são inerentemente *mudanças críticas* e exigem revalidação total.
- É princípio fundamental aceitar que resultados históricos, por mais otimizados que sejam, não garantem o desempenho operacional futuro.
- Todo relatório, análise de agente ou conclusão analítica gerada deve usar linguagem que distinga inequivocamente um *fato isolado*, de uma *hipótese teórica*, e de uma *inferência estatística*.

## 11. Controle de escopo e ROI (Return on Investment)
Antes de aprovar a entrada de uma nova funcionalidade no backlog ou a inicialização do fluxo de trabalho, o Architect ou a governança deve responder categoricamente:
- Qual problema ou ineficiência concreta essa funcionalidade resolve?
- Quem a utilizará e com qual frequência?
- Qual o ganho objetivo e mensurável esperado (ex: tempo economizado, aumento de estabilidade)?
- Qual o custo em complexidade para a construção e a subsequente manutenção dessa feature?
- Existe uma solução madura, confiável ou biblioteca padrão que possa ser integrada no lugar de construir "do zero"?
- Essa funcionalidade é essencial e pertence ao produto atual em desenvolvimento, ou é um "nice to have" de uma etapa hipotética no futuro?
- Qual é o critério final, restrito e objetivo de "pronto" (Definition of Done)?

## 12. Política de aprovação
Uma implementação realizada, seja por agente ou humano, **somente pode ser recomendada para commit e integração** quando houver o acúmulo de todas as condições abaixo:
- Diff inspecionado e revisado criteriosamente.
- Garantia documentada da ausência de mudança técnica não autorizada fora do escopo (sem side-effects intencionais).
- Validações estáticas executadas com sucesso pleno (Lint e tipagem sem alertas graves ignorados).
- Logs com a saída real atestando a passagem dos testes automatizados e builds de infraestrutura.
- Riscos residuais conhecidos devidamente listados e documentados (nunca ignorar um "warning" sem justificar).
- Documentação atualizada caso as mudanças interfiram no domínio de negócio ou regras de arquitetura.
- Critério de aceite originalmente acordado plenamente atendido na prática, não na teoria.

## 13. Política de falha e interrupção
Qualquer agente deve PARAR imediatamente seu fluxo e informar (elevar a ocorrência) ao humano ou agente supervisor quando:
- A causa raiz de um comportamento incorreto ou bug não estiver perfeitamente clara mesmo após análises sucessivas.
- Houver qualquer risco mensurável de corrupção ou perda irrecuperável de trabalho/dados no ambiente.
- Ficar claro que a tarefa vai exigir uma reescrita arquitetural ou refatoração extensa que não estava delineada ou aprovada no plano inicial.
- Surgirem necessidades obrigatórias de instalar dependências complexas ou de fontes que não foram mapeadas na viabilidade.
- Ferramentas cruciais de controle de qualidade e testes automatizados não puderem ser executadas por problemas ambientais.
- As evidências e resultados colhidos através dos logs e dos testes contradisserem frontalmente as hipóteses levantadas no Plano aprovado.
- Existir a menor dúvida razoável de que a alteração em desenvolvimento, da forma como está desenhada, puder afetar negativamente ordens e dinheiro real.

## 14. Critério de conclusão (Definition of Done)
Definir de forma irrefutável que uma tarefa só está "feita" quando encontra-se cumulativamente:
- **Implementada**: O código existe, está escrito e atende ao requisito especificado.
- **Validada**: A sintaxe, segurança e padrões de estilo foram inspecionados sem apresentar infrações (build/lint ok).
- **Testada**: Comportamento examinado via testes automatizados e funcionais atestando sua aderência ao domínio de negócio em cenários padrão e limite (edge-cases).
- **Revisada**: A arquitetura da solução e os side-effects locais foram checados no Diff por um nível igual ou superior (Nível 5+).
- **Documentada**: Em todos os casos em que a mudança afeta decisões e regras de arquitetura (05-knowledge atualizado, esquemas anotados e fluxos declarados).
- **Reversível**: Arquitetada de forma que, caso venha a se provar falha em Produção, possa ter seu estado desfeito ou desabilitado isoladamente.
- **Sem pendências ocultas**: Sem falsas resoluções, logs suprimidos apenas para calar erros no terminal ou "TODOs" maliciosos disfarçando tarefas inacabadas mascaradas como finalizadas.