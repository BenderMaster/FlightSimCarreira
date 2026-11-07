# v0.8.4 Alpha.1 — FlightSim Financial Center

## Entrega consolidada
A aba Finanças passa a ser uma página nativa Midnight Ops com cinco abas: **Resumo**, **Extrato**, **Operações**, **Patrimônio** e **Banco**. A versão anterior (v0.8.3 Alpha.3) permanece na main enquanto esta versão aguarda homologação.

### O que é real no banco
- `settings.balance` continua o **único caixa**. Nenhum saldo é calculado pelo navegador.
- `finance_ledger` é a fonte única para entradas, despesas, seguros, serviços, aluguéis, compras, vendas, tributos e dívida.
- `financial_center.py` consolida receitas e custos operacionais e separa operações de capital (empréstimos, compras, vendas, parcelas e investimento na companhia).
- Seguros já pagos (`kind='seguro'`) constam do extrato e das despesas operacionais, sem dupla contagem por voo.
- `fleet_units` estima valor de revenda de bens comprados. Starter e frota legada não vendável aparecem no inventário sem valor inventado. Aluguel não entra no patrimônio.
- **Patrimônio líquido estimado = caixa + revenda estimada − dívida atual**, não se confundindo com resultado operacional.
- 500 movimentações recentes aparecem na interface, filtráveis por categoria, descrição e período. CSV possui **todo o ledger** com data UTC, referência, categoria e saldo após, sem truncamento.
- Operações por voo mostram valores efetivamente lançados no ledger vinculado ao `flight_key`. Voos históricos sem ledger permanecem sem custo/receita inventados.

### Banco e operações
- Valor de empréstimo entre **R$ 1.000 e R$ 150.000**, inclusive; custo **único de 8%** incorporado à dívida na contratação. Um empréstimo ativo por vez.
- Pagamentos parciais de R$ 1 até a dívida total, limitados ao caixa disponível. Não há juros recorrentes nem agendamento.
- Confirmação obrigatória dentro do WebView2 antes de enviar solicitações de crédito ou pagamento.
- UI envia UUID de operação; `finance_requests` garante idempotência transacional com o movimento no ledger, e operações repetidas são recusadas. Cadastro oficial e perfil Teste seguem separados por SQLite.
- Chaves de imposto 4% podem ser alteradas no painel, sem retroatividade; alteração financeira bloqueada durante voo.
- Exportação CSV é montada na **thread Tk** onde a conexão SQLite reside, servida via endpoint loopback autenticado `/finance-export`. Nenhuma leitura do SQLite ocorre em threads HTTP e não há escrita de arquivos sobre o banco.

### Layout e regras de UI
- Header com saldo e quatro indicadores; escalas, valores, unidades, legendas e barras por período.
- Comprovantes de transações somente leitura, com ID, referência do ledger, categoria, valor e saldo após.
- Controles de crédito desabilitados conforme dívida/caixa e conferidos novamente pelo backend.
- Seguro/manutenção permanecem operados no Hangar existente; Finanças os contabiliza imediatamente.
- Dados de anos anteriores ao ledger não são reconstruídos.
- Não alterar controles do MSFS, combustível físico, contratos aceitos, XP ou preço dos aviões.

### Testes de homologação
1. Abra Finanças com carreira oficial e confirme caixa, seguro já pago e extrato sem discrepância.
2. Aplique filtros por categoria/tempo e abra o comprovante de uma operação existente.
3. Confira os dois gráficos: receita e despesas por mês; seguro presente na decomposição por categoria.
4. Confira frota comprada, valor estimado de revenda e ausência de valor artificial no C152 inicial.
5. No perfil Teste/Admin, contrate R$ 150.000, confira dívida de R$ 162.000; recuse R$ 150.001; pague parcela e confirme saldo, dívida e duplicação recusada.
6. Exporte CSV e confira o total de linhas do extrato integral.
7. Teste layout em 1280×720, 1600×900 e 1920×1080, trocas de aba e Scroll independente.
8. Reinicie app/perfil e confirme persistência. Não mesclar na main até testes físicos e visuais do piloto.

