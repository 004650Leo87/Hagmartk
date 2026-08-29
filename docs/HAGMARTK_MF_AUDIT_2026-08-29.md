# HAGMARTK MF — Auditoria Técnica 2026-08-29

## Baseline auditada
- Repositório: 004650Leo87/Hagmartk
- Base: `main` em `4a9b00c`
- Worktree isolado: `chore/audit-housekeeping`
- A branch experimental `feature/cycle-theory-v111-fidelity` foi preservada sem alterações.

## Evidências confirmadas
- Baseline `main`: 250 testes passaram, 1 skipped, 0 falhas.
- Frontend: build passou; npm audit encontrou 0 vulnerabilidades.
- Frontend lint: 14 warnings, incluindo dependências ausentes em React hooks.
- Python compileall falhava por marcador `*** End Patch` deixado em código versionado.
- Dois arquivos `.pyc` estavam indevidamente versionados.
- Arquivos temporários de ferramenta (`.git_diff*.txt`, `apply.js`) estavam versionados.
- Backend não possuía manifesto de dependências reproduzível.
- Testes geram `data_cache/*.db-journal`; padrão não estava ignorado.

## Segurança
- Não foram encontrados segredos óbvios na árvore atual pelas buscas realizadas.
- CORS está restrito a origens localhost.
- A API não possui autenticação/autorização.
- Existem endpoints mutáveis para Shadow Mode, backtests e watchlist.
- Dados de conta e posições MT5 são expostos por endpoints de leitura.
- Sem exposição pública, o risco é limitado ao host local; publicação externa exige autenticação antes de qualquer deploy.

## Pendências abertas
- Cycle Theory Gate 3D: 2 falhas em 350 testes executados na branch experimental.
- `terminal_unrealized_r` não reflete posição terminal aberta no harness atual.
- Ledger não encontra registro de uma posição criada diretamente no mock broker.
- 774 warnings na suíte experimental, majoritariamente `datetime.utcnow()` depreciado.
- FastAPI usa `@app.on_event`, API depreciada; migrar para lifespan.
- `MarketChart.jsx` possui dependências faltantes em `useEffect` e código morto.
- Bundle frontend supera 500 kB minificado; avaliar code splitting antes de distribuição web.
- `scratch/` contém evidências e scripts de pesquisa versionados; classificar antes de remover.

## Política de correção
1. Não alterar HDF/candidato congelado durante housekeeping.
2. Não misturar correções estruturais com mudanças de estratégia.
3. Toda correção deve passar compileall, pytest, lint/build e `git diff --check` aplicáveis.
4. A branch experimental só será integrada após Gate 3D ficar determinístico e verde.
5. Nenhuma execução real de ordens será habilitada como efeito colateral da auditoria.

## Correções aplicadas nesta branch
- Remoção do marcador de patch inválido do diagnóstico.
- Remoção de bytecode e artefatos temporários do índice Git.
- Inclusão de manifests de dependências Python runtime/dev.
- Reforço do `.gitignore` para artefatos locais e SQLite journal.
