# Especificação v0.7.7 — Frota, peso, NOAA e navdata

## Persistência real
`fleet_fuel` contém combustível por `aircraft_ref`, `fleet_units` e `owned_aircraft` contêm condição individual. A v0.7.7 corrige a brecha do relógio: o primeiro sample após um reinício não calcula consumo usando o intervalo entre dias; com MSFS em solo e dados compatíveis, a quantidade persistida tem prioridade e deve ser escrita novamente nos tanques, com confirmação posterior.

A migração aditiva cria `fleet_fuel_credit(aircraft_ref,refundable_liters)`; compras antigas em `finance_ledger` são creditadas de forma limitada ao combustível ainda presente, quando possível. Combustível da calibração inicial, não comprado, **nunca gera reembolso**. Observação de consumo reduz o crédito. Compra e devolução atualizam ledger/estoque/creditos na mesma transação SQLite.

## Alertas de condição
Se o combustível total salvo ÷ capacidade <=20%, o dashboard renderiza alerta crítico. A condição de manutenção é persistida por unidade e também alertada ao atingir 20% ou menos. São alertas informativos; o addon não injeta falhas mecânicas nem mensagens de cockpit nesta Alpha.

## Manifesto e distribuição
Cada missão recebe nome fictício de passageiro ou item (determinístico por ID), tipo e peso em kg. Para a carga o C152 utiliza estação de peso 2, sem tocar na estação do piloto 1. Requisitos antes do comando:
- MSFS conectado, avião parado em solo, modelo designado do contrato selecionado;
- `PAYLOAD STATION COUNT` >=2, `PAYLOAD STATION WEIGHT:2` legível, `TOTAL WEIGHT` e `MAX GROSS WEIGHT` válidos;
- peso projetado = peso total atual − massa da estação 2 + massa da nova carga, sem exceder MTOW;
- massa máxima conservadora por classe de modelo (não constitui tabela oficial de centros de gravidade);
- escrita assíncrona `aq.set('PAYLOAD_STATION_WEIGHT:2',lb)` via worker SimConnect, seguida de confirmação pela telemetria; se não confirmar em 15 s, estado ERROR e aviso.

**Ainda é necessário homologar CG e estação real por modelo**, pois a documentação de MSFS 2020 pode não refletir corretamente o menu nativo.

## Bônus de peso
+2,5% sobre pagamento e XP se a mesma missão demonstrou carga na estação 2 e `TOTAL WEIGHT <= MAX GROSS WEIGHT` na decolagem. Declaração no checklist permanece legível para históricos antigos, mas não gera bônus.

## Aceite e despacho
Um clique em Aceitar missão já autoriza as duas operações para a missão correspondente. Valida novamente elegibilidade e posição em solo. O carregamento fica pendente se o MSFS ou a aeronave designada não estiver pronto; não existe outro popup de confirmação. Para o arquivo .PLN, exige aeroportos com coordenadas recuperadas da lista de instalações do MSFS. O usuário pode atualizar o plano posteriormente ao chegar a navdata.

`SimConnect_FlightPlanLoad` aceita solicitação mas não fornece garantia de que o GPS visual refletirá a rota; reportar status enviado, jamais sucesso fictício.

## Aeroportos
Coordenadas são recuperadas de `SimConnect_RequestFacilitiesList` / `SIMCONNECT_RECV_AIRPORT_LIST` usando o layout MSFS 2020 (ICAO 6 bytes, região 3 bytes, lat/lon/alt double), filtrando região operacional Nordeste. O resultado atualiza `AirportCatalog`, revalida ofertas e é guardado em `settings.msfs_airports_v077` para continuação offline. Se o SDK não fornecer o ICAO, usar fallback **identificado**, sem declarar coordenada oficial.

## Combustível
O modal pede volume FINAL em litros, mostra atual, capacidade, custo ou reembolso elegível. Saldo insuficiente bloqueia compra; excesso bloqueado. Distribuição proporcional às capacidades lidas dos tanques. Uma devolução só paga o volume que foi comprado no addon e ainda não consumido. SimConnect pode rejeitar escrita; o inventário físico precisa de validação posterior. Testar no C152 antes de usar outros modelos.

## Meteorologia
NOAA válido e não vencido é fonte principal do destino. Dados MSFS aparecem somente se NOAA estiver indisponível; futura flag `show_msfs_with_noaa` permite comparação, ainda não exposta na UI.

## Homologação física
1. Abastecer e registrar inventário; fechar MSFS/addon por um dia e abrir de novo. Verificar preservação exata da quantidade.
2. Comprar litros, devolver parte e confirmar reembolso no ledger sem lucro de combustível gratuito.
3. Aceitar voo turístico, comparar nome, kg, estação de carga, total e MTOW.
4. Reduzir combustível para viabilizar carga que excederia MTOW, depois repetir despacho.
5. Comparar SNUW e outros aeroportos problemáticos com coordenadas do MSFS e plano real.
6. Verificar fallback NOAA, alertas 20%, desgaste por aeronave e pista do botão Despacho.
7. Repetir aceitação e reinício; garantir ausência de pagamento duplicado.
