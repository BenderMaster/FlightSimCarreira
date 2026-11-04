# v0.7.7 Alpha.1 — Critérios técnicos e validação

## Persistência / combustível
- Cada exemplar possui `fleet_fuel.aircraft_ref` com quantidades por tanque e capacidades. Condição/hours persistem nos registros de frota existentes.
- Ao abrir em solo, primeira leitura de outro nível no MSFS não vira consumo por dias desconectados; restauração usa inventário do banco. Não restaurar arbitrariamente combustível em voo.
- Refuel define quantidade **final** em litros, não volume adicionado. Divide proporcionalmente por capacidade de tanque e proíbe extrapolação. Operação exige modelo escolhido, solo, SimConnect e caixa suficiente.
- Crédito de devolução restringe-se ao `fuel_refundable_liters:<ref>` comprovadamente comprado e não consumido nesta implementação, inclusive evitando dinheiro infinito por combustível inicial gratuito. Valor é R$ 7 por litro fictício.
- `fuel_pending_adjustment:<ref>` guarda transação para confirmação pelo simulador. Erro explícito ou falta de confirmação após tentativas gera estorno financeiro único, restaura tanques anteriores e crédito comprado. Se o piloto gastou o crédito antes do estorno, a conta poderá ficar negativa, em vez de criar dinheiro artificial.
- Alertas 20% são somente painel/log. Extensão por overlay 2D dentro do MSFS continua futura.

## Payload
- `Mission` acrescenta campos opcionais (manifest_label, manifest_kind, passenger_count, payload_kg, nav_source), retrocompatíveis na leitura de JSON antigo.
- Manifesto determinístico baseado no ID, nomes fictícios, pesos de carga e 1 passageiro padrão em turismo. Aeronaves maiores podem receber serviços médicos; incompatibilidade de MTOW bloqueia carga, não altera física de voo.
- `PAYLOAD_STATION_COUNT` e `PAYLOAD_STATION_WEIGHT:index` são lidos opcionalmente (1..15). A estação 1 (piloto) é preservada; demais são atribuídas à missão. Antes de enviar é verificada a projeção de peso total sobre MTOW. A leitura posterior deve confirmar pesos dentro de 1,5 lb e MTOW.
- Ao aceitar, a ação explícita já envia o pedido; não há segundo popup de confirmação. Se não conectado, guarda preparação pendente. O payload precisa de estação/massa disponível e aeronave correta. Modelo freelancer não é trocado automaticamente.
- A confirmação congela +5 XP no voo e qualifica o componente de 2,5% de peso do despacho, se todos os requisitos se mantiverem na decolagem. Sem leitura ou excesso de peso, bônus indisponível.
- A atualização física do painel de peso do MSFS pode variar por aeronave/SDK. Nunca afirmar sucesso somente pelo envio de comando.

## Navegação VFR
- Usa `SimConnect_AddToFacilityDefinition` + `SimConnect_RequestFacilityData` para solicitar `LATITUDE` e `LONGITUDE` de aeroportos por ICAO, com limite por lote. DLL/wrapper sem suporte retorna fallback seguro.
- Coordenadas verificadas são guardadas em `msfs_navdata:<ICAO>` com fonte `MSFS`. Catálogo externo tem proveniência distinta.
- Uma missão é rotulada `MSFS` somente com os dois aeroportos verificados; com um só é `MISTO`, sem nenhum é `CATALOGO`.
- Importação **automática** para o MSFS espera confirmação dos dois ICAOs, para não criar rota errada. O botão de plano manual exporta a rota do catálogo externo quando as facilities não respondem. Testes físicos ainda são necessários para validar o parser de mensagens do SDK 2020 e aeroportos personalizados.
- Não há afirmação de alinhamento universal com cenário personalizado até validar API e instalação real.

## NOAA
- DESTINO NOAA prevalece assim que houver um METAR disponível; MSFS é mostrado somente quando NOAA não está disponível, salvo `weather_sim_alongside_noaa=1` no banco. Interface de alteração dessa preferência é trabalho futuro.

## Aceite
Aceitar um contrato válida requisitos do motor e registra no SQLite sem abrir confirmação Tk extra, então chama exportação/solicitação de .PLN e carga. A UI mostra estado de rota e carga separadamente. Falhas técnicas não criam um segundo pagamento nem um falso carregamento.

## Homologação
1. Comprar combustível, reiniciar app após outro dia e observar tanques restaurados. Repetir após desligar MSFS; testar falha de escrita.
2. Abastecer valor alvo, devolver volume pago e verificar estorno sem gerar R$ do tanque inicial. Tentar ultrapassar MTOW.
3. Aceitar missão com passageiro e cargo e verificar estação de payload no C152, C172; testar MTOW real e negar carga pesada sem reduzir peso da estação piloto.
4. Conferir coordenadas do MSFS para aeródromo com erro no catálogo e um cenário de terceiro; testar fallback quando API indisponível.
5. Confirmar NOAA primário, warnings 20%, persistência da condição, XP extra idempotente por flight_key.
