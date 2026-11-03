# Bloco 3 — Modalidades de carreira e emprego (v0.4.0 Alpha.1)

## Modalidades

1. **Autônomo**: modalidade inicial; contratos regionais e freelancers permanecem disponíveis conforme nível/habilitações.
2. **Empregado**: concorre a vagas virtuais, passa por seleção semanal e, se aprovado, pode realizar até dois trechos exclusivos da companhia na região onde está. Não recebe compra de aeronave: o modelo é virtualmente fornecido, sendo necessário selecionar o mesmo modelo manualmente no MSFS.
3. **Empresário (endgame)**: registro inicial de empresa própria após nível **18**, **25 h**, habilitação virtual **PLA** e capital mínimo de **$100.000**. Dedução única do investimento; registro e modalidade persistem. Gestão de frota IA, tripulações, lucro operacional e expansão **não estão implementadas**.

Trocar de empregado para autônomo exige pedir demissão; o histórico do trabalho permanece salvo. As vagas são independentes de recrutamento real.

## Vagas semanais simuladas

- Exibir até **4** vagas a partir da região atual (ou base cadastrada, na ausência de telemetria).
- Nomes reais usados apenas como **referência de roleplay**: **Azul**, **GOL**, **LATAM**. Também há a fictícia AeroNordeste para início de carreira.
- Sem vínculo com as companhias reais, sem garantias de emprego real, sem logotipos ou livrées redistribuídos.
- Requisitos de nível, horas, habilitações. Uma candidatura por semana; status `pending` até a semana UTC seguinte.
- Resultado de seleção determinístico a partir da vaga e de um identificador do piloto **capturado no momento da candidatura**, com 55–85% de chance para candidatos elegíveis, ponderada por experiência. Não pode repetir a mesma vaga para tentar novo resultado.
- Um candidato empregado não pode se inscrever novamente sem pedir demissão.
- **Não há salário creditado semanalmente sem voar nesta versão**. Valor mensal/semanal exibido é referência para as **remunerações por trecho** da empresa. Esse comportamento será evoluído num futuro sistema de contratos de trabalho.
- Não gerar 1000+ vagas; no máximo quatro listadas sob demanda no aeroporto atual.

## Trechos da companhia

- Ao ser contratado, o mercado regional acrescenta até 2 voos do empregador no aeroporto atual e no período diário; ambos requerem modelo de aeronave e expertise compatíveis. O pagamento só é feito se a aeronave coincidir no pouso e na decolagem, e destino/origem estiverem corretos.
- Contratos de companhia começam por `EMP-` e são contabilizados uma única vez no livro de voos. Um piloto não empregado não tem direito a aceitá-los.
- O salário semanal indicado nas vagas **não** é depositado automaticamente.
- O passageiro/carga representa o tipo de atividade atual do motor, ainda não existem sistemas de tripulação ATC real, serviços de cabine ou contratos laborais complexos.

## Plano VFR — MSFS 2020

- O botão **Preparar plano VFR da missão** cria um arquivo XML `.PLN` entre os ICAOs de origem/destino e o salva em `%APPDATA%\AeroCarreira-Lab\planos_vfr`.
- Pode pedir **carregamento no simulador somente após confirmação explícita**, em solo, com SimConnect conectado; a solicitação é feita pelo `SimConnectWorker` na própria thread.
- O adaptador opcional Python-SimConnect oferece `load_flight_plan`, baseado na API oficial `SimConnect_FlightPlanLoad`.
- A API confirma que o comando foi aceito, **não confirma que o mapa VFR/GPS o exibiu**; validar manualmente no MSFS Steam. É possível importar `.PLN` manualmente se a chamada não funcionar.
- **Não** configura sozinho a aeronave do jogador ou o ponto de início. **Não** troca nem recarrega o voo em andamento. Troca de aeronave/posição exige futura solução de `.FLT` baseada em voo salvo pelo próprio usuário, com ação separada e confirmação; sem risco de perda de voo.
- **Não** seleciona plano IFR com procedimentos SID/STAR; piloto decide altitude de forma independente.

## Frota IA e liveries: desenho futuro

- Índice local, sem copiar assets: ler titles e configurações de aeronaves/liveries **instaladas pelo usuário** na Community/Official quando autorizado.
- Cada companhia virtual referencia `company_code`, `callsign`, `aircraft_model`, `livery_title` e `installation_status`. Não prometer representação de marcas licenciadas se não estão instaladas.
- Spawn da frota IA poderá usar `SimConnect_AICreate...` + modelo `container title` + plano da aeronave IA; exige PoC de compatibilidade e limitações de tráfego/multiplayer antes da implementação.
- Evitar conflito com tráfego real do MSFS. **Não** gerar aviões IA nesta versão.

## Regras de segurança e dados

- Nunca alterar/ler NeoFly para operar as funções novas. Usar DB próprio com migração aditiva.
- Não mudar de vínculo ou criar empresa durante voo/contrato ativo pela interface.
- Economia, checkpoint, XP e histórico preservados. Controle de falhas e provas de habilitação opcionais permanecem no roadmap.
- Tests unitários e CI Windows/Linux/Python 3.11 e 3.13.

## Próximos incrementos

1. Validar carregamento `.PLN` no VFR do MSFS real.
2. Validar seleção semanal, contratação de empresa e trechos no Windows; contratar empresa real exige altas horas/XP e ainda não é fácil chegar a esses níveis no piloto atual.
3. Seleção opcional de aeronave por modelo instalado, quando técnica segura estiver validada, sem substituição de avião durante voo.
4. Painel in-game na toolbar sem Alt+Tab.
5. Gestão de frota IA e liveries locais, depois empresa própria completa.
