# Flight Operations — v0.8.2 Alpha.1

## Escopo consolidado (Alpha.1 + Alpha.2)
A página **Planejamento de Voo** substitui a ficha genérica Midnight e concentra:
- Rota VFR livre ou vinculada ao contrato, ICAOs de origem e destino, altitude, até 8 waypoints USER definidos por coordenadas;
- Estimativas de distância, rumos verdadeiros e duração por perna, além de ETA/combustível total (fator de reserva 35% da referência);
- Mapa MapLibre compartilhado, sem segunda instância WebGL. O mapa offline SVG também suporta os trechos;
- Despacho de aeronave designada, manifesto, combustível, peso/MTOW quando o SimConnect informar, origem/destino NOAA/MSFS com proveniência separada;
- Checklist pré-voo persistente, exportar .PLN, solicitação ao SimConnect e estados do ATC.

## Regras invioláveis
1. **Voo livre NÃO é contrato.** Não cria ledger, XP, salário nem missão fictícia; .PLN de voo livre possui recompensa zero em objeto temporário, nunca vai para `Career.accept`.
2. **Contrato ativo é imutável quanto a ICAOs e pagamento.** Waypoints complementam a navegação, não mudam aeroporto de origem/destino nem remuneração.
3. Aeroportos devem ser retornados pelo **catálogo da sessão MSFS** para salvar/exportar; jamais usar um dataset externo quando o inventário não está pronto. Na Demo, catálogo demonstrativo explícito.
4. Waypoints são coordenadas declaradas manualmente pelo piloto, até 8, com label ASCII limitado; não se apresentam como instalações de aeroportos, auxílios reais ou rotas autorizadas.
5. Sem importação garantida em GPS/mapa VFR. `FlightPlanLoad` é pedido ao SimConnect/ATC e pode não sincronizar aviônicos.
6. As opções do checklist de pista e rota continuam **declarações**; combustível e MTOW dependem de dados válidos; relógio/assistências usam audit disponível. **Clima real não rende bônus**.
7. A distância planejada com waypoints não reduz o percurso direto usado no cálculo de combustível do bônus. O valor é congelado na decolagem e não retroage.
8. Nunca salvar aeronave/aviônico/configurações externas automaticamente nem alterar banco financeiro fora dos fluxos já estabelecidos.

## Arquitetura
- `aerocarreira/flight_operations.py`: validação e projeção pura; persistência via chave `flight_operations_v1` do SQLite existente. Contratos associam `mission_id`; um contrato cancelado não pode herdar plano antigo.
- `aerocarreira/flightplan.py`: exportação .PLN com waypoint USER inserido antes do destino, mantendo API histórica sem argumentos.
- `aerocarreira/app.py`: ação nativa segura para salvar, exportar e solicitar ATC; pré-voo `preflight_v1` conserva compatibilidade.
- `aerocarreira/dashboard_controller.py`: valida ações, retorna notificações com sequência; não confia na UI.
- `aerocarreira/midnight_server.py`: loopback, token e Origin obrigatórios; JSON de no máximo 4096 bytes para planos, sem aceitar parâmetros financeiros.
- `aerocarreira/midnight/flight-operations.js`: formulário e estados na UI nativa, sem executar código remoto. `app.js` e `free-map.js` reutilizam a mesma árvore/canvas.

## Roteiro de homologação no MSFS 2020
1. Com catálogo de aeroportos MSFS carregado, abrir Planejamento; alternar voo livre/contrato e confirmar restrição de ICAOs do contrato.
2. Criar rota SBRF → SBJP com pelo menos dois waypoints de coordenadas distintas, salvar, reiniciar aplicativo e conferir campos, pernas, mapa e ETA.
3. Exportar `.PLN`; inspecionar ordem partida → USER 1 → USER 2 → destino. Se envio ATC for usado, testar em solo e confirmar resposta sem afirmar que GPS está sincronizado.
4. Em contrato, conferir que a rota editada alimenta a estimativa de combustível e checklist e que o bônus só é congelado na decolagem.
5. Testar leitura de combustível e peso/MTOW no C152 e no C172; sem leitura, demonstrar indisponibilidade em vez de valor fictício.
6. Demonstrar voo livre completo: nenhum contrato, dinheiro ou XP deve surgir da exportação/planejamento.
7. Testar desconexão/reconexão e tentativa de alteração do planejamento em voo; não devem gerar alterações financeiras ou travamentos.
8. Confirmar o mesmo mapa e créditos no Dashboard, detalhes e planejador, sem duplicar WebGL; validar dimensões Windows 1280×720 e 1600×900.

## Fora do escopo
SID/STAR, navegação IFR, cartas oficiais, conflito de terreno, importação universal de aviônicos e mudança automática de aircraft/posição. Isso permanece futuro; nenhuma implementação simulada de tais funções nesta entrega.

## Segurança de versões
A v0.8.1 Alpha.3 foi integrada à `main` via PR #15, homologado pelo piloto.
A v0.8.2 vive em PR #16 (branch separada) até CI e teste físico, preservando o motor, o ledger, SimConnect e as fotos aprovadas.
