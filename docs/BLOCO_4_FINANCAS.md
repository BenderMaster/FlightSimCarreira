# Bloco 4 — Economia em reais, finanças e manutenção (v0.5.0-alpha.1)

## Regra de migração

A moeda do addon passa a ser **real fictício (R$)**, **sem conversão cambial**: 7.130 unidades antigas serão mostradas como **R$ 7.130**, e não convertidas por taxa USD/BRL. Essa é uma mudança de denominação interna do jogo. Nenhum valor de voo já registrado é alterado. Um backup SQLite `carreira.pre_v050.backup.db` é criado uma vez antes da migração. Não remover `%APPDATA%\AeroCarreira-Lab`.

## Mercado mais atraente

- Contratos REGIONAIS e FREELANCER usam função pura `market_reward`: **R$ 550 + R$ 48 por minuto estimado**, com piso de R$ 1.050 e multiplicador por categoria. Um voo de ~20 min rende cerca de **R$ 1.510 brutos** em carga básica.
- Minutos estimados: tempo direto à velocidade de planejamento de 90 kt + 5 min de preparação, com piso de 8 min. Não há promessa de tempo real, pois vento, trajeto e procedimentos alteram a duração.
- Freelancers recebem 78% do valor-base ajustado; **o avião pertence ao contratante**, sem combustível ou taxa operacional cobrados do piloto.
- Distâncias máximas sugeridas: nível 1–2: **55 NM**; 3–5: 90 NM; 6–9: 130 NM; 10+: 190 NM. Contratos continuam limitados aos aeroportos próximos do local atual; nada de pré-gerar contratos globais.
- O cache local de **ofertas anteriores** é invalidado uma única vez ao migrar, para mostrar o novo preço. **Contratos aceitos** preservam a recompensa original no checkpoint.
- Valores de mercado são artificiais de jogo, **não preços reais da aviação**.

## Finanças e extrato

- `finance_ledger`: eventos únicos de receita, combustível, taxa aeroportuária, imposto opcional, seguros, compra, revisão, companhia e financiamento.
- **Operações transacionais** no SQLite. Pouso + pagamento + despesas + desgaste + XP + checkpoint são confirmados juntos. Evento de voo repetido não duplica receita, despesa, XP ou horas de desgaste.
- Imposto virtual de 4% opcional, **desligado por padrão**. Não representa tributação brasileira oficial.
- Empréstimo virtual de R$ 1.000 a R$ 30.000; UI disponibiliza R$ 10.000 por operação, com **8% de custo fixo** agregado à dívida; pagamento parcial via UI. Ainda não há cobrança de juros por calendário.
- Todos os novos custos são de **voos futuros**. Nada é cobrado retroativamente.

## Frota, combustível, revisão e seguro

- Botão **Finanças / Hangar**, com resgate **uma única vez** do Cessna 152 inicial sem custo, após cadastro de piloto. Se tu já tens o C152 no MSFS, isso registra a posse apenas na economia do addon.
- Compra no jogo dos modelos catalogados; C152, C172, Baron, King Air e Citation. Compra exige saldo suficiente e nunca substitui aeronave dentro do MSFS.
- **Desgaste** da aeronave própria de modelo identificado: percentual por hora monitorada, persistido por avião; não se aplica a avião do contratante.
- **Despesa de combustível**: consumo efetivamente medido pelo SimConnect entre decolagem e pouso, quando disponível e válido; senão **estimativa por tempo de voo**. O custo fictício é R$ 7/litro. A operação NÃO muda o combustível físico dos tanques do MSFS.
- **Taxa de operação** fixa por categoria de aeronave no pouso, apenas para avião próprio cadastrado e contrato pago. **Voo livre sem contrato não gera cobrança**, nesta versão.
- **Revisão** paga restaura condição para 100%, não modifica o modelo simulado no MSFS.
- **Seguro virtual**: prêmio único por modelo e estado persistido, ainda **sem processamento automático de sinistros**, que requer um bloco de eventos/acidentes. Não afirmar cobertura implementada nesta Alpha.
- A opção **Permitir falhas** pode ser armazenada, **desligada por padrão**; ainda não há injetor de falhas. Não controla as falhas globais do simulador.

## Segurança e limites

- A API atual usa telemetria somente leitura, não abastece, danifica ou troca aeronaves no MSFS.
- Não cobrar por avião não cadastrado na frota, nem cobrar despesas de aeronaves freelancer/empresa.
- XP do voo depende da **recompensa bruta**, nunca das despesas; não premiar pousos perigosamente suaves.
- O relatório do NeoFly continua somente leitura; não misturar valores/importar moeda automaticamente.
- Regressões no CI, com testes de migração, XP, custos, crédito, manutenção e pagamentos duplicados.

## Próximos refinamentos

- Componentes e intervalos de manutenção, avarias por sistemas e sinistros/seguradora.
- Sincronização opcional de abastecimento e manutenção com SimConnect (necessita API com permissão e teste físico).
- Serviços de solo, garagem por aeroporto, taxas regionais, aluguel, depreciação e impostos avançados.
- Mais configurações de economia, mapas e painel integrado no MSFS.
