# Especificação e teste FlightSimCarreira v0.7.6

## Navegação e mapa
O menu lateral contém somente "Mercado" como rota de mercado. Alternar Regional/Freelancer acontece em botões internos. Escolher um contrato abre uma página com origem, destino, remuneração, classe, elegibilidade, distância e duração.

A duração é estimada por `estimated_minutes(dist_nm, AIRCRAFT_ECONOMY[modelo].cruise_kts)`, com mínimo e margem preexistentes. A aeronave particular considera o modelo escolhido; freelancer considera o modelo do contratante. Se não houver modelo identificado, usa referência explícita de **90 kt**.

O mapa da Dashboard é uma única instância `FSCFreeMap`: o elemento `.map-area`, incluindo o canvas, tiles, controles, atribuições e eventos, é montado no contêiner de detalhes da missão. Ao fechar os detalhes, volta à Dashboard; nenhuma API ou segunda instância é criada. Quando os detalhes estão abertos, a fonte de rota aponta ao contrato selecionado. Fallback SVG usa os mesmos dados do contrato.

## Proa
`PLANE_HEADING_DEGREES_TRUE` e `PLANE_HEADING_DEGREES_MAGNETIC` são SimVars de **radianos**. O adaptador converte ambas para graus. O marcador rotaciona com a proa verdadeira para respeitar o norte cartográfico, mas o selo no mapa exibe **MAG** (comparável ao rumo de referência dos instrumentos) e **TRUE** (para navegação geográfica). Não ajustar automaticamente em 20°, pois a variação magnética depende da região. Se MAG não vier, mostrar somente TRUE.

## Autoconexão
Ao iniciar GUI normal, usar `root.after(700, _auto_connect)`. Não tentar em `FLIGHTSIM_HEADLESS=1`. `_auto_connect` verifica estado e chama `_connect()`; a thread de SimConnect permanece responsável por tentativas e reconexão. A interface continua útil sem simulador aberto.

## Clima
A escolha de clima ao vivo não é comprovável pelo adaptador externo do MSFS 2020. Não há checkbox novo, componente de realismo nem bônus por declaração. O campo `real_weather_declared` permanece na dataclass antiga somente para ler JSON de versões anteriores. Relógio UTC sincronizado e outras SimVars não provam uso de clima em tempo real.

## Táxi / decolagem
- `ON_ANY_RUNWAY=True` exclui velocidade sobre pista da penalidade de táxi, inclusive aceleração de decolagem.
- `ON_ANY_RUNWAY=False` e velocidade no solo medida >25 kt por >=8 s com IAS<45 kt geram incidente suspeito. Mesmo com False em pista customizada, o episódio é isento se a aceleração segue reta e sem frenagem até decolar.
- Com `ON_ANY_RUNWAY=None`, se o avião acelera quase reto, muda <=12° de proa, sem desaceleração significativa e decola dentro de 50s com GS elevada, classificar o trecho como corrida de decolagem (não infração). Curva em alta velocidade mantém suspeita.
- Nenhuma infração quando a velocidade no solo é estimada a partir de IAS ausente.

## Rollout e táxi após pouso
- Mantém confirmação de pouso em 2s e pagamento idempotente atual.
- Inicia monitor separado após o registro do voo. Enquanto se mantém em corrida de frenagem na pista, nenhuma penalidade de táxi é possível.
- Ativa fase de táxi quando GS<=10kt, ou quando **primeiro foi observada pista=True e depois False** com GS<=28kt, ou mudança de proa >=30° e GS<=32kt. Se o cenário devolver False desde o toque, não supor que a pista foi liberada.
- Nessa fase, se `ON_ANY_RUNWAY` não é True e velocidade medida supera 25kt continuamente por >=8s, descontar **2 XP daquele flight_key**; no máximo uma vez por voo.
- Transação de correção do XP verifica existência de `flights`, `pilot_xp_ledger` e um marcador idempotente `settings.postflight_taxi_v2:<flight_key>`. Não altera dinheiro, despesas, voo ou XP anterior. Monitor também fica em checkpoint para reconectar e retomar.
- Sem `ON_ANY_RUNWAY` os limites permanecem heurísticos. Em cenários com aeroportos personalizados ou taxiways fora da pista, validar fisicamente. Não penalizar decolagem, arremetida nem freada de pouso.

## Homologação manual
1. Ligar o app com MSFS fechado, depois abrir o simulador. Confirmar reconexão.
2. Comparar selo de MAG com bússola, TRUE com orientação no mapa e usar aeroportos com diferentes variações magnéticas.
3. Abrir contrato, zoom/pan/satélite, selecionar outro contrato e voltar ao Dashboard.
4. Acelerar na pista e decolar; depois taxiamento rápido fora dela com curvas; revisar XP da decolagem.
5. Pousar e frear de alta velocidade até <10kt sem punição. Em seguida taxiamento rápido >25kt e observar dedução única −2 XP.
6. Reiniciar app entre toque e fase de táxi e confirmar recuperação; testar voos repetidos e ausência de pagamento em duplicidade.

CI automatizado não substitui os ensaios físicos.
