# FlightSimCarreira v0.7.7 Midnight Ops Alpha.1

## Novidades
- **Persistência de combustível por avião**: reparo do bug no primeiro contato após dias de inatividade. A leitura inicial do MSFS não pode ser tomada como consumo entre sessões; o inventário salvo no SQLite passa a ter prioridade. Tanques se sincronizam por SimConnect apenas quando aeronave e configuração batem, em solo.
- **Desgaste por exemplar**: desgaste da frota salvo em voos contratados e voos livres, preservando condições por unidade e pelo Cessna inicial.
- **Avisos visíveis a 20%**: dois alertas críticos no aplicativo para combustível restante e condição da aeronave; mensagens 2D no MSFS ficam para integração futura.
- **Missões identificáveis**: nomes fictícios de passageiros, materiais específicos e massa em kg persistida no contrato. Carga/assento 2 é verificado antes de escrever, sem alterar peso do piloto.
- **Despacho automático ao aceitar contrato**: na sessão MSFS conectada, sem confirmação adicional, solicita o plano .PLN com coordenadas oficiais do catálogo de instalações do simulador e carrega o peso da missão. A leitura de peso é confirmada depois; o carregamento pode ficar pendente por modelo incorreto, MTOW excedido ou SimVar ausente. **Nenhuma dessas falhas é anunciada como sucesso.**
- **Bônus automático de peso +2,5%** no pagamento e XP da missão quando a carga da estação 2 foi confirmada e o MSFS reporta peso de decolagem <=MTOW. Checklist manual não concede esse componente.
- **Combustível em litros**: popup de abastecimento parcial ou total. Devolução de combustível pode ressarcir dinheiro, mas apenas do volume comprado no addon e ainda não consumido. Tudo é registrado no ledger SQLite; não é possível gerar dinheiro com o combustível gratuito da primeira calibração.
- **NOAA prioritário no destino**: MSFS é fallback apenas quando METAR NOAA válido não está disponível. Comparação MSFS/NOAA permanece reservada para configuração futura.
- **Navegação por dados MSFS 2020**: AIRPORT_LIST do SimConnect é usado para corrigir coordenadas ICAO e gerar rotas. Se a lista oficial estiver indisponível, a interface identifica o fallback e deixa o auto-envio .PLN pendente.
- O botão **Preparar Voo / Despacho** usa a silhueta de decolagem fornecida pelo usuário; **novo ícone global do app não foi instalado sem aprovação**.

### Cautelas técnicas
- `PAYLOAD_STATION_WEIGHT:2` é configurável por SimConnect, mas nem todas as aeronaves possuem layout de estações idêntico. A Alpha bloqueia operações sem leitura de estações/MTOW; a estação 1 do piloto não é tocada.
- A API `FlightPlanLoad` pode retornar sem confirmar visualmente a rota no GPS; o status do aplicativo diferencia solicitação e confirmação.
- O catálogo MSFS 2020 é recuperado por API de facilities; alguns aeroportos de cenário personalizado podem não aparecer. Não declarar como oficial um ponto importado de outra base.
- A interface nativa de peso do MSFS pode divergir da física mesmo com SimVars corretas. Testar station weights, peso total e barras de combustível na aeronave real.
- A proposta do ícone global ainda precisa de aprovação. O pacote não altera a identidade aprovada.
- **Antes de testar:** feche o app, faça backup de `%APPDATA%\AeroCarreira-Lab\carreira.db` e extraia o novo ZIP numa pasta separada. Banco atualizado somente por migrações aditivas.

Veja [especificação de testes v0.7.7](docs/V077_PERSISTENCIA_CARGA_NAVDATA.md).

---

# FlightSimCarreira v0.7.6 Midnight Ops Alpha.1 — Mapa em contratos, proa e taxiamento

- Menu lateral **Mercado** único; abas internas **Aeronave particular / Serviços freelancer**, preservando as ofertas Nordeste da v0.7.5.
- Detalhes do contrato redesenhados em cards: origem/destino, distância em NM, duração de voo calculada com velocidade de cruzeiro do modelo da missão, remuneração, aeronave e requisitos.
- Mapa do contrato: a mesma instância MapLibre e controles da Dashboard são movidos para a página do voo selecionado, sem duplicar API, créditos, canvas ou rota; zoom, pan e satélite permanecem disponíveis.
- Proa do simulador: passa a ler **PLANE_HEADING_DEGREES_MAGNETIC** além da verdadeira; HUD apresenta ambas como MAG / TRUE. Marcador continua girando segundo a orientação verdadeira do mapa geográfico. Não é aplicada correção fixa de 20 graus.
- **Autoconexão SimConnect na inicialização**, com reconexão automática do worker se o MSFS ainda não estiver disponível. Testes headless não abrem SimConnect.
- Clima ao vivo: removido da interface de bônus de realismo e do cálculo de XP/pagamento. Campos antigos do checklist continuam aceitos no banco para compatibilidade, mas não são exibidos nem premiados.
- Táxi: leitura opcional de ON ANY RUNWAY; velocidade >25 kt em pista não é punida como táxi. Sem sinal confiável, aceleração em linha reta rumo à decolagem reduz risco de falso positivo; curva em alta velocidade pode pontuar.
- Pós-pouso: frenagem é isenta até diminuir a velocidade, sair da pista ou entrar em curva significativa. Após essa transição, táxi rápido sustentado gera **−2 XP**, debitados uma única vez do mesmo voo já registrado. Sem alterar R$ ou outros voos.
- Preservados pagamentos idempotentes, recuperação de checkpoints e regras da carreira.

**Alpha em homologação:** SimVars de runway, diferença entre MAG e TRUE, comportamento do WebView2 após mover mapa e monitor pós-pouso precisam de teste físico no MSFS 2020. Fazer backup com o app fechado de `%APPDATA%\AeroCarreira-Lab\carreira.db`. Instalar o ZIP inteiro em pasta separada.

Ver [documentação técnica v0.7.6](docs/V076_MAPA_PROA_TAXI.md).

---

# FlightSimCarreira v0.7.5 Midnight Ops Alpha.1 — Realismo e mercado Nordeste

**Mudanças**
- Uma entrada **Mercado de Contratos** no menu lateral e duas abas: Regional (aeroportos próximos à base) e Freelancer (busca aproximada sobre o Nordeste brasileiro).
- Freelancer oferece até 6 contratos por dia, possivelmente para outros estados, com **autonomia estimada por aeronave**. A origem continua sendo o aeroporto do piloto; sem teleporte.
- Leitura opcional de assistências de pouso/decolagem, controle por IA, combustível ilimitado, horário Zulu, luzes, motor e força G. Dado ausente não equivale a opção desligada.
- Bônus de realismo da missão: +3% por relógio Zulu próximo do UTC real em simulação 1x e +3% quando assistências individuais verificadas estão desligadas. Estes sinais não comprovam todos os presets globais.
- Clima ao vivo **não pode ser comprovado** pelo SimConnect externo do MSFS 2020. Declaração manual não rende mais os antigos +3%.
- XP operacional: +4 por pouso final suave (-150 < toque estimado < 0 ft/min) **sem arremetida**; até +3 por luzes observadas; penalidades limitadas por estol, G extremo, episódios de táxi rápido e luzes desligadas após terem sido vistas funcionando.
- Arremetida **não penaliza** o piloto; toque-e-arremetida não encerra a missão e não gera pagamento intermediário.
- Checkpoint inclui estado de segurança e continua retrocompatível com voos salvos anteriormente. Nenhuma migração destrutiva de banco.
- **Homologação física pendente:** ainda precisamos confirmar cada SimVar no MSFS 2020 real com C152 e outros modelos.

Consulte [as regras e ressalvas da v0.7.5](docs/V075_PROCEDIMENTOS_NORDESTE.md).

Instale o ZIP inteiro numa pasta limpa. Preserve e faça backup de `%APPDATA%\AeroCarreira-Lab`.

---

# FlightSimCarreira v0.7.4 Midnight Ops Alpha.1 — Navegação por páginas

A barra lateral permanece visível enquanto o conteúdo central muda entre **Dashboard**, **Mercado Regional**, **Mercado Freelancer**, **Planejamento** e os demais módulos. Os dois mercados têm entradas separadas no menu e abas de acesso rápido no topo. Seleção e detalhes dos contratos agora são **páginas do aplicativo**, não modais.

- As missões de aeronave particular e os trabalhos freelancer são filtrados dos contratos reais produzidos pelo motor Python/SQLite; aceite e elegibilidade continuam no backend, sem alterações.
- Painéis dos módulos ainda em migração mostram os dados atuais da carreira em páginas próprias; um botão explícito permite abrir a ferramenta clássica quando uma operação avançada ainda não foi migrada. Clicar no menu lateral nunca abre uma janela Tk.
- Botão de satélite reposicionado para o alto à direita, distante do zoom/centralizar. Crédito EOxCloudless compacto no canto inferior direito, com texto completo e licença acessíveis ao clicar. Atribuições MapLibre/OpenFreeMap mantidas no mapa.
- Proa verdadeira, mapa/rotas e fallback offline preservados. **Nenhuma migração do banco**, cobrança de API ou mudança das regras do voo.
- **Homologação física pendente:** navegação, responsividade e contratos precisam ser verificados no WebView2 do Windows com o MSFS 2020 real.

Veja [Especificação e testes da v0.7.4](docs/V074_NAVEGACAO_PAGINAS.md). Instale o ZIP Windows **inteiro** em uma pasta limpa, preservando o diretório de dados `%APPDATA%\AeroCarreira-Lab`. A v0.7.0 continua sendo referência funcional homologada.

---

# FlightSimCarreira v0.7.3 Midnight Ops Alpha.1 — Mapa e Mercado

Correção do enquadramento do OpenFreeMap, créditos do satélite e proa do avião. **A v0.7.0 continua sendo a base de voo homologada**, preservada através das evoluções do Midnight Ops.

- Mapa MapLibre renderizado no tamanho inteiro da área, com canvas redimensionado após a janela ficar visível; scroll e arraste mantidos.
- Zoom +/- e botão centralizar separados do botão Satélite, que permanece no canto inferior direito. Créditos EOxCloudless/Sentinel-2 no canto inferior esquerdo, sem cobertura pelos controles.
- Marcador em ciano segue a proa verdadeira via SimConnect, inclusive com aeronave parada. A SimVar usa **radianos**, convertidos para graus; se indisponível, marcador pode usar direção estimada de deslocamento.
- Mercado Regional, Missões e Contratos e Ver todas as missões agora abrem um **diálogo dentro da janela Midnight Ops**, com busca e filtros Regionais/Freelancer, seleção de rota e aceite validado pelo mesmo motor Python existente.
- Nenhuma alteração em pagamentos, XP, detecção de voo, combustível, persistência ou regras de elegibilidade.
- Testes Windows/Linux, compatibilidade de UI em 15 combinações e smoke WinForms/WebView2 no .exe. A interface permanece nativa, não navegador externo.

Veja [Detalhes e homologação da v0.7.3](docs/V073_MAPA_MERCADO.md). Instale o ZIP Windows **inteiro** em uma pasta nova, sem reutilizar `_internal` de versões anteriores. Preserve `%APPDATA%\AeroCarreira-Lab` e faça backup com o aplicativo fechado.

---

# FlightSimCarreira v0.7.2 Midnight Ops Alpha.1

Hotfix nativo WebView2 e painel com mapa 100% livre e meteorologia.

Esta versão mantém **a janela do aplicativo**: não abre o Dashboard no navegador.
Empacotamento do pythonnet reforçado, com teste real de WinForms no .exe do Windows em CI.
Base funcional: v0.7.0 homologada pelo piloto, com motor v0.6.1.

Mapa: OpenFreeMap + MapLibre 5.24.0 (incluído no .exe), zoom/scroll, clique e arraste,
rota verdadeira, aeronave ciano e botão Satélite ON/OFF (EOxCloudless 2016, CC BY 4.0).
Sem cartão, chave, API paga ou Google Maps. Fallback local preservado sem rede.

Meteorologia: SimConnect próximo à origem e à chegada; METAR oficial NOAA Aviation Weather
para destino, em consulta assíncrona com cache e tolerância a aeroporto sem estação.

Manual: [v0.7.2 instalação, licenças e limitações](docs/V072_WINDOWS_MAPA_METAR.md).

Atenção: extraia **todo o ZIP** da distribuição numa pasta NOVA; mantenha a pasta _internal
junto do executável. Não apague %APPDATA%\AeroCarreira-Lab. Faça backup com o app fechado.
A instalação requer .NET Framework 4.8 e Microsoft Edge WebView2 Runtime.

---
# FlightSimCarreira v0.7.1 Midnight Ops Alpha.1 — reputação e Google Satélite

Novo patch sobre a v0.7.0 aprovada. Reputação calculada do histórico real, ícone ciano vetorial, Google Satélite oficial com scroll/arraste e mapa de coordenadas como fallback.

**Atenção:** Google Maps requer chave da Maps JavaScript API e configuração de faturamento/restrições do próprio piloto. Chave e fotos não devem ser enviadas ao GitHub. [Como configurar e testar](docs/V071_REPUTACAO_MAPA.md).

O motor SQLite/SimConnect, bônus, combustível, contratos e pagamentos continuam os mesmos da v0.7.0.

---

# FlightSimCarreira — Midnight Ops 0.7.0 Alpha 1

Esta branch reconstrói o dashboard sobre a **v0.6.1-alpha.1**, commit `3048bb86ee498770b93862ef449fb4d2ff6e061f`, preservando seu motor Python. A `main` v0.6.3 permanece independente.

Execute `instalar_windows.bat` e `iniciar_windows.bat`, ou use o pacote Windows compilado produzido pelo GitHub Actions. Requer Microsoft Edge WebView2 Runtime. Recuperação: `iniciar_classico_windows.bat`.

Leia [instalação, arquitetura e limitações](docs/MIDNIGHT_OPS.md) e [licenças dos assets](docs/MIDNIGHT_ASSETS.md). Esta alpha possui mapa com NASA GIBS e alternativa offline por coordenadas, foto licenciada do C152 e cenário decorativo original; **não é reprodução pixel a pixel** da referência. As telas secundárias preservam a UI Tk funcional da base.

---

# FlightSimCarreira — v0.6.0 Alpha.1 | Frota e Planejamento de Voo

**Instalação Windows:** termine o voo, feche o addon anterior, extraia o novo ZIP em pasta nova e execute `instalar_windows.bat` e `iniciar_windows.bat`. **Não apague `%APPDATA%\AeroCarreira-Lab`**: a carreira, a XP e os pagamentos ficam lá. A versão cria automaticamente `carreira.pre_v060.backup.db` antes da migração. Recomendamos ainda um backup externo do banco, sempre com o app fechado.

## Novidades desta Alpha

1. **Frota avançada:** abra `Finanças / Hangar` → `Frota avançada` para comprar aeronaves novas ou usadas, alugar, vender e revisar individualmente. O mercado de usadas renova por aeroporto e semana e não pode vender a mesma oferta duas vezes.
2. **Inventário do MSFS:** em `Frota avançada`, clique `Aeronaves instaladas no MSFS` para ler os `aircraft.cfg` do Official/Community, incluindo aeronaves e pinturas de addons. **Instalação detectada não equivale a licença/propriedade** na conta do jogo.
3. **Despacho pré-voo:** aceite uma missão e clique `Preparar voo / Despacho`. Planeje combustível, peso, altitude, confira clima, hora, assistências, pista, iluminação e rota. Enquanto conectado em solo, o painel aproveita leituras opcionais do SimConnect.
4. **Bônus de realismo:** no máximo **+18%** sobre valor bruto e XP do contrato, de acordo com verificações e declarações. O bônus fica congelado na decolagem e é concedido só no pouso legítimo, uma vez. Não é garantido só por marcar checkboxes: combustível e peso dependem de telemetria válida.
5. **Preparação de voo antes de conectar:** com piloto cadastrado, contrato no aeroporto-base pode ser reservado offline. Gere `.PLN` para importar manualmente no MSFS, ou tente o comando de carregar o plano quando já estiver em solo conectado ao SimConnect. Não cria o avião nem o voo completo no Mapa-Múndi automaticamente.
6. **Painel experimental local:** botão `Painel local (experimental)` abre `http://127.0.0.1:8769/` com saldo, telemetria e esboço geométrico da rota. Existe **código-fonte** de protótipo de toolbar em `in_game/toolbar`, mas ele exige build com SDK e teste físico, não é ainda addon in-game pronto para Community.

**Não implementado:** seleção/troca automática de avião no MSFS 2020; injeção de clima/combustível, mapa VFR nativo, outros jogadores multiplayer, scanner de propriedade da conta, voo criado diretamente no Mapa-Múndi ou painel interativo pronto dentro do simulador. Continuam prioridades de pesquisa e testes no hardware real.

**Compatibilidade:** Windows 10/11, Python 3.11 64 bits, MSFS 2020 e pacote Python-SimConnect (instalado pelo `.bat`). `airportsdata` opcional para aeroportos do mundo. Falhas, seguros e companhias IA não são sistemas completos nesta Alpha. Voos e dinheiro anteriores preservados; custos só em missões futuras com aeronave própria identificada.

**Manual completo do bloco:** [Frota, despacho, bônus e SDK](docs/BLOCO_5_FROTA_DESPACHO.md). **Testes:** `py -3.11 -m unittest discover -s tests -v`.

---

# FlightSimCarreira v0.5.1 Alpha.1 — progresso visual e horas de voo

Patch incremental sobre a v0.5.0, sem perda de saldo, XP ou histórico.

- Cabeçalho: barra de nível abaixo do indicativo, com percentual do progresso **dentro do nível atual**; sem valores numéricos de XP no cabeçalho.
- Meu piloto / Habilitações: barra de nível e **três indicadores em cada habilitação** (horas de voo, voos e XP), com valor atual e meta escritos.
- Janela de habilitações com rolagem para caberem todos os requisitos.
- Desbloqueios passam a exigir **horas efetivamente registradas no diário**, além de voos, XP e pré-requisitos.
- Regras provisórias: PPA inicial; PCA 10 h / 8 voos / 160 XP; IFR 20 h / 16 voos / 320 XP; MLTE 30 h / 24 voos / 450 XP; PLA 60 h / 50 voos / 1500 XP.
- As habilitações obtidas antes do patch **não são revogadas**; nenhuma alteração retroativa no banco é necessária.
- Provas permanecem opcionais como requisito futuro, com chave de realismo documentada e ainda não implementada.
- Preservadas as funcionalidades financeiras e do mercado da v0.5.0.

## Instalação

Feche o aplicativo (não atualize durante o voo), extraia em uma **pasta nova**, execute `instalar_windows.bat` e depois `iniciar_windows.bat`.
Não apague `%APPDATA%\AeroCarreira-Lab`, onde está a carreira. Antes do teste, é prudente fazer também um backup externo de `carreira.db` com o app fechado.

## Testes

`py -3.11 -m unittest discover -s tests -v`

---

# FlightSimCarreira — v0.5.0 Alpha.1 (Bloco 4: finanças e manutenção)

## v0.5.0 Alpha.1 — Mercado equilibrado, reais e Finanças / Hangar

- **Moeda agora é R$ fictício** em todo o addon, sem câmbio: saldo R$ 7.130 é mantido numericamente a partir de 7.130 unidades anteriores. O saldo real pode ter mudado conforme voos posteriores.
- **Contratos regionais e freelancer recalculados**: cerca de R$ 1.500 brutos por frete de 20 minutos (planejamento, não tempo garantido), com distâncias máximas menores nos primeiros níveis.
- **Nova tela Finanças / Hangar**: resgatar C152 inicial uma vez, comprar modelos, consultar extrato, usar crédito e quitar parcelas, revisar desgaste e contratar seguro virtual.
- Combustível (estimado quando falta dado do SimConnect), taxa de pouso, desgaste por voo e tributação opcional. **Custos só entram em novos voos**, após possuir uma aeronave no addon. Voos com avião da empresa não pagam essas despesas.
- **Falhas do addon continuam desativadas;** a opção já é armazenada, mas injeção de falhas/sinistros NÃO está pronta.
- **Seguro já tem prêmio e cadastro, porém sinistros/cobertura automática ainda NÃO estão implementados.**
- Backup antes da migração em `carreira.pre_v050.backup.db`; preserva saldo, XP, voos e contratos aceitos, mas atualiza os preços de propostas ainda não aceitas.
- [Regras e limitações detalhadas](docs/BLOCO_4_FINANCAS.md).

**Teste no Windows**: termine o voo antes de atualizar, feche o addon, extraia o ZIP em pasta separada, rode `instalar_windows.bat` e `iniciar_windows.bat`. Cadastre o piloto, abra Finanças / Hangar e resgate o Cessna 152 inicial (apenas uma vez). Faça um frete curto pelo Mercado regional e confirme no extrato receita bruta, combustível/taxa, lucro líquido e condição do C152. Os custos são dados de carreira, não alteram os tanques do avião no MSFS.


**Nome provisório.** Aplicativo de carreira **original** para Microsoft Flight Simulator 2020, feito em Python 3.11 com interface Windows Tkinter e base de dados SQLite própria.

## Histórico: Bloco 2 — Mercado regional e freelancer

O botão **Mercado regional / Freelancer** abre contratos gerados perto da posição atual do piloto (ou de sua base cadastrada se o MSFS estiver fechado). Uma nova lista é gerada por dia UTC e por origem, **sem gerar contratos para todos os aeroportos globais**. A lista atual tem no máximo **10 contratos regionais e 3 freelancers**. Contratos já concluídos não podem ser pagos novamente, mesmo depois de reiniciar. Cada novo voo continua registrado em SQLite.

**Tipos e nível mínimo inicial**: carga (1); turismo e passageiros (2); táxi aéreo (3); humanitária (4); transporte médico (6); executivo (8); resgate (10); operações especiais (12). Além de nível, algumas missões exigem habilitações PPA/PCA/IFR/PLA e horas voadas. O XP determina o nível, com progressão gradual; XP e habilitações anteriores permanecem. Esses níveis são balanceamento preliminar do jogo, não exigências regulatórias reais.

**Freelancer**: o contrato indica a **aeronave disponibilizada pelo contratante** (ex.: Cessna 152). O piloto recebe pagamento pelo serviço e não compra/aluga a aeronave dentro da economia do addon. **Nesta Alpha, ainda é necessário escolher esse avião no MSFS manualmente** antes da decolagem. O SimConnect tenta ler o título do modelo; para pagar um freelancer, o modelo precisa ser confirmado na decolagem e no pouso. Se o título estiver indisponível ou não corresponder, o voo é registrado, mas o contrato não é pago. Os contratos de avião avançado levam em conta experiência por família e, quando necessário, no modelo exato. A propriedade real da aeronave/tail number não é verificada ainda: isso virá com gestão de frota.

**Aeroportos globais:** `v0.3.0`0 usa a base MIT **airportsdata 2026.8.2**, instalada por `instalar_windows.bat`. O catálogo pode conter aeroportos que não existem na instalação atual do MSFS, portanto confirme os destinos no mapa do simulador antes de aceitar. Sem o pacote disponível, o programa preserva o catálogo local básico SBRF, SIPE, SIFC e SBJP e informa essa limitação. Nada é importado do banco do NeoFly para gerar missões.

**Como testar (voo curto):** abra MSFS 2020, coloque o Cessna 152 em **SIPE** no solo, abra o app e conecte SimConnect; cadastre o piloto em **Meu piloto / Habilitações**; clique **Mercado regional / Freelancer** e escolha uma proposta para SIFC. Missões regionais exigem decolagem na origem e pouso dentro de 3 NM do destino; freelancing exige também o modelo designado. Se um contrato antigo estiver ativo, cancele antes de aceitar outro. A demo fixa continua separada, com a rota SBRF→SIPE.

**Limitações do Bloco 2 original:** estas são categorias de contrato com geração, progressão, aeronave e pagamento. Mecânicas específicas (busca de vítimas, embarque de passageiros, objetivos turísticos, urgência médica, reputação e carga/peso) virão nos próximos subblocos. O addon ainda não altera a aeronave no MSFS nem possui interface in-game. A frota virtual foi adicionada na v0.5.0. As opções independentes de provas e falhas estão aprovadas no escopo, mas seus controles de configuração ainda serão implementados.

Mais detalhes: [Bloco 2](docs/BLOCO_2_CONTRATOS.md) e [Escopo aprovado](docs/ESCOPO_CARREIRA.md).

### Bloco 1 agora disponível

Use **Meu piloto / Habilitações** no topo do programa para cadastrar nome do piloto, indicativo e base ICAO. A partir daí o painel mostra voos, horas, XP e uma trilha de habilitações **virtuais**, com pré-requisitos de XP e quantidade de voos. A habilitação inicial PPA é concedida no cadastro; as seguintes são conquistadas conforme os requisitos provisórios. Não são documentos aeronáuticos reais.

Ao criar o piloto, o aplicativo **não reseta saldo nem histórico** do banco existente em `%APPDATA%\AeroCarreira-Lab\carreira.db`. Voos anteriores contam nas estatísticas, sem gerar XP retroativo. **Novos** voos após criar o piloto geram 25 XP ao pousar e mais 15 XP se o contrato pagar recompensa, tudo na mesma transação e com proteção contra duplicação. O cadastro é **um piloto por carreira** nesta versão; sua edição não reinicia a carreira. As novas missões do Bloco 2 aplicam os requisitos de nível, habilitações e experiência.

Detalhes e requisitos futuros: [Escopo aprovado](docs/ESCOPO_CARREIRA.md).

Dois objetivos em paralelo:

1. **SimConnect em modo somente leitura:** painel de telemetria, detecção inicial de decolagem e pouso, diário de bordo e contratos simples de carga.
2. **NeoFly 4:** estudar **cópia** dos possíveis arquivos `common.db` ou `std.bin`, sem modificar dados originais, para avaliar importação de progresso numa versão posterior.

Não é uma modificação do NeoFly; não copia sua implementação nem reproduz o código proprietário. Não é software aeronáutico para voo real.

## v0.4.0 Alpha.1 — Bloco 3: modalidades de carreira e plano VFR

- Todos começam **autônomos**. Novo botão **Vagas e companhias** na tela principal e no mercado.
- São geradas no máximo quatro **vagas semanais fictícias**, com empresas de referência AeroNordeste, Azul, GOL e LATAM. As oportunidades **não são vagas reais**, e as empresas não são afiliadas ao projeto.
- Candidatura limitada a **uma por semana**: acompanha os requisitos de nível, horas e habilitações. O resultado só é revelado a partir da semana seguinte, quando clicar **Ver resultado / atualizar**. Resultado estável, sem reroll por reinício.
- Se contratado, o piloto pode acessar **até dois trechos da empresa por dia no mercado regional**, usando o avião designado (selecionado manualmente no simulador). Pode pedir demissão e voltar ao autônomo. Nenhum salário periódico é pago automaticamente; os valores apresentados são referências, com pagamentos por trechos concluídos.
- **Endgame:** registro inicial de companhia aérea própria a partir do nível 18, 25 h, PLA e $100.000 de investimento. **Ainda não** existe gestão de frota, IA e lucro corporativo.
- **Plano VFR:** aceitar contrato e clicar **Preparar plano VFR da missão**. Gera `.PLN` em `%APPDATA%\AeroCarreira-Lab\planos_vfr`. Com avião **em solo** e MSFS conectado, podes solicitar o carregamento pela API `SimConnect_FlightPlanLoad` com confirmação. Isso **não muda automaticamente o avião ou posição**, e a atualização do VFR/GPS precisa ser validada no MSFS 2020 real. Não clicar em pleno voo.
- O banco próprio passa por migração aditiva, preservando saldos, voos, XP, ofertas e checkpoint. **Se estiver voando na versão anterior, termina o voo antes de atualizar.**
- Consulte [Bloco 3 — documentação técnica](docs/BLOCO_3_CARREIRAS.md) e [roadmap](docs/ROADMAP.md).

### Testar sem perder progresso

1. Fecha o aplicativo antigo depois de pousar e concluir a missão; **não apagues** `%APPDATA%\AeroCarreira-Lab\carreira.db`.
2. Extrai o ZIP em pasta nova, executa `instalar_windows.bat` e `iniciar_windows.bat`.
3. Confere teu piloto, saldo e histórico. Abre **Vagas e companhias**. Vagas de níveis altos aparecem bloqueadas por requisitos, mas são apenas simulação.
4. Para testar `.PLN`, aceita contrato local, usa **Preparar plano VFR da missão**, confirma a carga **somente em solo**, abre o mapa VFR e vê se a rota apareceu. Se não aparecer, anota o log e verifica se a importação manual do `.PLN` funciona.
5. Para contratar, é necessário cumprir os requisitos e aguardar o próximo período semanal do simulador de carreira. Não antecipar relógio do sistema apenas para testar.

## Rodar no Windows (primeiro a demo)

Requisitos: **Windows 10/11**, **Python 3.11 de 64 bits** instalado, com Tkinter (Python oficial inclui Tkinter). MSFS 2020 é necessário apenas para conectar telemetria.

1. Extraia o ZIP em uma pasta como `Documentos\AeroCarreira-Lab`.
2. Execute `instalar_windows.bat`. Ele cria `.venv` e instala `SimConnect` e `airportsdata`; é preciso Internet na primeira instalação.
3. Execute `iniciar_windows.bat`.
4. Clique **Demo sem MSFS**, selecione `SBRF → SIPE`, e clique **Aceitar contrato**.
5. Clique **Avançar demo** até pousar em Itapessoca. Deve receber **$850**, registrar voo e incrementar saldo de $5.000 para $5.850.

Se o adaptador SimConnect não instalar, a interface Demo e o inspetor NeoFly continuam funcionando usando apenas a biblioteca padrão Python: `py -3.11 -m aerocarreira`.

### Conexão ao simulador

1. Inicie **MSFS 2020** e entre num voo com o Cessna 152 em SBRF.
2. Abra AeroCarreira e clique **Conectar MSFS**.
3. Os 7 campos essenciais de telemetria devem atualizar. Combustível e aviso de estol são opcionais. Se houver erro, envie o texto do painel para diagnóstico.
4. Aceite contrato na origem, **em solo**, e voe até o destino. O avaliador decola/pousa apenas quando vê mudanças coerentes de `SIM ON GROUND`.
5. A recompensa é paga só depois de um pouso confirmado no aeródromo de destino, dentro de **3 NM** do seu ponto de referência.

**Limitações:** A conexão SimConnect e o pouso real foram validados pelo piloto na v0.1.2; o novo leitor de TITLE e o mercado mundial ainda requerem teste físico. A captura da razão vertical é a **última leitura aérea antes do toque**, uma estimativa que pode diferir de sistemas de avaliação de pouso; não se deve interpretá-la como medição certificada. O intervalo de leitura de 0,4s pode perder o toque exato. O catálogo pode listar aeroportos não presentes no simulador; o modo local de contingência inclui SBRF, SIPE, SIFC e SBJP.

### NeoFly — localizar e analisar sem risco

**Atualização após teste físico:** modo demo, conexão ao MSFS e voo real SIPE → SIFC foram validados pelo piloto. Foi recebido e documentado um relatório com a estrutura SQLite do NeoFly; a importação de registros ainda não foi implementada.

O arquivo varia conforme a versão/instalação do NeoFly:

- `C:\ProgramData\NeoFly\common.db` — caminho da [FAQ oficial](https://www.neofly.net/faq); `ProgramData` é oculto.
- `%LOCALAPPDATA%\Programs\NeoFly\std.bin` — relatado em instalações do NeoFly 4; **não assumimos que seja SQLite**.
- Se o NeoFly foi extraído de um ZIP para uma pasta personalizada, o arquivo pode estar lá.

**Localização automática (novo):** clique **Localizar arquivos NeoFly** no aplicativo. O programa procura os nomes conhecidos em pastas usuais, sem varrer o disco inteiro e sem abrir nem alterar o arquivo. Se encontrar um candidato, ele informa o caminho completo.

Também é possível executar no PowerShell na pasta do projeto:

```powershell
py -3.11 -m aerocarreira --find-neofly
```

Ou procurar manualmente colando `%ProgramData%\NeoFly` e `%LOCALAPPDATA%\Programs\NeoFly` na barra do Explorador do Windows.

**Analisar com segurança:**

1. Feche totalmente o NeoFly antes de copiar ou analisar.
2. No AeroCarreira, clique **Analisar common.db / std.bin** e selecione o arquivo encontrado.
3. O programa cria uma **cópia isolada** em `%APPDATA%\AeroCarreira-Lab\neofly_analise\neofly_copia_local.db`.
4. Caso a cópia tenha formato SQLite reconhecível, exporta apenas **nomes de tabelas, colunas e tipos** para `neofly_schema_report.json`; nenhuma linha de dados pessoal é exportada.
5. Se não for SQLite, identifica `desconhecido` e para, sem tentar extrair ou decifrar conteúdo. Isso não significa que a carreira não possa ser importada por outro meio autorizado no futuro.

Linha de comando para inspecionar o **arquivo que tu realmente encontrou**:

```powershell
py -3.11 -m aerocarreira --inspect-neofly "C:\CAMINHO\PARA\std.bin" --output "$env:TEMP\neofly-inspecao"
```

**Compartilhe somente o relatório `neofly_schema_report.json`.** Não publique `common.db`, `std.bin`, a cópia nem arquivos pessoais no GitHub. O repositório informado está público neste momento. O aplicativo não envia dados para GitHub por conta própria.

## v0.1.2 — voo real com recuperação automática

**Por que atualizamos:** no primeiro voo MSFS SBRF → SIPE o leitor parou após
`SimVar sem resposta: GROUND_VELOCITY`

O FlightSimCarreira agora trata velocidade de solo/razão vertical ausentes como
telemetria **degradada**, exibindo `~` na velocidade estimada. Leituras críticas
faltantes são toleradas temporariamente, sem gerar amostras falsas. Persistindo a
falha, ele tenta reconectar automaticamente (o simulador pode ficar indisponível).

**Checkpoint**: durante voo conectado, registra missão e fase a cada ~2s,
na mesma base local. Reiniciar o aplicativo durante um voo **já monitorado por esta
versão** permite recuperar o estado em voo e continuar até o pouso. Um voo anterior
com v0.1.1, sem checkpoint, **não é recuperável automaticamente**. As recompensas
são lançadas junto do pouso numa só transação, com chave única por decolagem.

**Rota rápida nova:** `SIPE → SIFC`, aeroporto Coroa do Avião (Igarassu/PE),
aproximadamente 11,4 NM em linha reta, recompensa de teste `$420`. Referência de
localização: [AISWEB SIFC](https://aisweb.decea.mil.br/?codigo=SIFC&i=aerodromos).
É aeródromo privado na realidade; esta versão é **somente simulação**.
Confirme que `SIFC` está disponível no mapa do teu MSFS 2020 antes de decolar.
O pagamento exige decolagem perto de SIPE e pouso confirmado perto de SIFC.

**Teste recomendado no MSFS:**

1. Feche o FlightSimCarreira v0.1.1. Descompacte esta versão em pasta nova,
   instale/inicie normalmente. O saldo e o histórico antigos da pasta APPDATA
   são preservados e o SQLite recebe migração aditiva segura.
2. Posicione o avião em solo em **SIPE**. Clique **Conectar MSFS** e aguarde dados.
   Se aparecer um contrato antigo ativo, cancele antes de aceitar o novo.
3. Selecione a opção `SIPE → SIFC` e aceite o contrato **em solo**.
4. Decole e siga para SIFC. Se ocorrer uma falha transitória, o worker deve
   continuar; se a conexão cair, deve tentar reconectar sozinho. Não precisa
   clicar em 'Conectar MSFS' durante o voo.
5. Após pousar em SIFC e permanecer em solo por 2s, o app deve registrar o voo,
   acrescentar **$420** e remover o contrato. O botão **Salvar log** exporta
   diagnóstico local para conferir em caso de erro.
6. Para testar recuperação completa, feche o app **durante o voo**, abra de novo
   e reconecte: a missão e o status anterior devem permanecer. Faça isso apenas
   em um voo de teste, sem mexer no NeoFly.

**Limitação:** reconexão automática, inclusive com SimConnect genuinamente
encerrado, ainda depende de validação física no teu MSFS/Windows; testes
automatizados simulam amostras, reconexão e reinício, mas não o SDK real.
A interface in-game permanece no [roadmap](docs/ARQUITETURA_IN_GAME.md).

## Integração no cockpit (planejada)

A interface Windows é transitória: o requisito prioritário é operar todo o gameplay pelo painel in-game na toolbar do MSFS 2020. O mapa VFR e o multiplayer precisam de prova de conceito técnica; não afirmamos que o SDK permita reaproveitar o mapa nativo ou ler jogadores online diretamente. Veja [arquitetura](docs/ARQUITETURA_IN_GAME.md) e [escopo](docs/ESCOPO_CARREIRA.md).


## v0.6.1 Alpha.1 — Localização de frota e combustível comandado pelo addon

**Localização de aeronaves:** o pouso dentro de 3 NM de um aeródromo conhecido
atualiza o local do exemplar ativo, inclusive o Cessna inicial (`legacy:c152`),
aeronaves compradas e alugadas, mesmo em voo sem contrato. Não altera a localização
do avião privado quando a missão for freelancer/emprego. Na primeira execução,
recupera uma única vez o último pouso conhecido do Cessna legado (sem refazer
pagamento nem acrescentar voo). Cria backup SQLite `carreira.pre_v061.backup.db`.

**Controle de combustível:** em **Finanças / Hangar**, marque
`Combustível controlado pelo FlightSimCarreira` (ligado por padrão). A primeira
calibração com um modelo suportado ocorre **no solo**. Depois, o inventário do
addon acompanha consumo gradual e impede que combustível inserido no menu do MSFS
seja acrescentado gratuitamente: restaura os níveis **dos tanques individuais**.
O combustível total é apenas leitura. A sincronização tenta no máximo três
vezes se não conseguir confirmação da leitura. *Com tanques desconhecidos,
sem capacidade, combustível ilimitado ativo ou modelo incompatível, o addon
não escreve quantidades arbitrárias.*

**Abastecer:** em `Frota avançada`, selecione uma aeronave e clique `Abastecer`
com o simulador conectado, no solo e no mesmo modelo. Enche os tanques
identificados e desconta o valor em R$ no extrato. A despesa de consumo **não**
é cobrada novamente no pouso se o voo partiu usando combustível previamente
controlado pelo addon. O saldo e combustíveis de voos anteriores não são
recalculados. Não há abastecimento automático gratuito.

**Desligar controle:** a opção pode ser alterada **somente em solo**.
Com o controle desligado, o MSFS gerencia os tanques e o addon aplica
**-30% ao ganho bruto do contrato (inclusive bônus) e -30% ao XP do voo**.
A escolha fica congelada na decolagem e é recuperada ao reabrir o aplicativo.
Custos operacionais e impostos não recebem desconto pela penalidade. O extrato
registra a redução em separado e protege contra repetições.

**Validação física ainda necessária:** MSFS 2020/Steam e `Python-SimConnect` podem
recusar alterações de tanque em algumas aeronaves e add-ons complexos; nessa
situação o programa deve avisar e não forçar sincronização. Recomenda-se testar
no Cessna 152 **em solo** antes de iniciar um voo, e confirmar o indicador do
combustível no cockpit e na interface do MSFS após adicionar combustível pelo menu.
Se os tanques não forem sincronizados, **não** trate o controle como aprovado.

### Roteiro seguro de teste

1. Feche MSFS e FlightSimCarreira antes de trocar arquivos. Copie o banco da carreira antes da primeira migração, se desejar redundância; os backups automáticos também são criados.
2. Abra `Finanças / Hangar`: confirme que o controle de combustível está ligado.
3. Abra `Frota avançada`: confirme que o Cessna inicial voltou ao aeródromo do último pouso. Selecione o exemplar.
4. Carregue o Cessna 152 no simulador **no solo**, conecte o addon e aguarde `Combustível registrado` no log.
5. Acrescente alguns galões no menu de combustível do MSFS, volte e espere a leitura: o addon deve solicitar correção e a quantidade do cockpit deve retornar à registrada. Se aparecer `escrita recusada`, não prossiga com esse teste.
6. Experimente `Abastecer` dentro da Frota e confira o novo valor dos tanques no simulador e o desconto em R$ no extrato.
7. Em outro voo curto, desligue o controle ainda no solo e verifique que o dinheiro e XP do contrato foram reduzidos em 30% no pouso; retorne à opção ligada para os próximos voos.

**Atenção:** o inventário de combustível real é experimental. Não use no voo real;
não tenta interferir na aeronave se as SimVars forem insuficientes. Certifique-se
de ter combustível e reservas adequados antes de decolar. O FlightSimCarreira não
substitui o planejamento de combustível do MSFS.

## Onde os dados são salvos

`%APPDATA%\AeroCarreira-Lab\carreira.db`: banco **nosso**, separado da instalação NeoFly. O saldo inicial desta carreira é **R$ 5.000 fictícios**; não reproduz o saldo real do NeoFly, que ainda não foi importado.

## Testes

```powershell
py -3.11 -m unittest discover -s tests -v
```

Os testes de regras, SQLite e simulação são independentes do MSFS e da biblioteca SimConnect. CI usa Linux e Windows com Python 3.11 e 3.13. Nenhum simulador real é necessário no CI.

## Arquitetura

- `aerocarreira/domain.py`: amostras, fases, contratos, distâncias e saldo.
- `aerocarreira/pilot.py`: requisitos e validação dos perfis/habilitações virtuais.
- `aerocarreira/storage.py`: base SQLite própria e diário de bordo.
- `aerocarreira/sim_adapter.py`: adaptador opcional Python-SimConnect, exclusivamente leitura.
- `aerocarreira/neo_inspect.py`: inspetor de banco NeoFly com cópia isolada.
- `aerocarreira/demo.py`: amostras artificiais para validar fluxo sem MSFS.
- `aerocarreira/app.py`: interface desktop.
- `aerocarreira/contracts.py`: níveis, elegibilidade, catálogo de aeroportos, propostas regionais e freelancer.

## Licenciamento e separação

- Nosso código nesta entrega é desenvolvido de modo independente, sem código NeoFly.
- A biblioteca de terceiros `Python-SimConnect` é opcional e distribuída separadamente pelo PyPI. Sua licença (AGPL-3.0 na implementação de referência) deve ser avaliada antes de distribuir um software proprietário; o adaptador foi isolado para eventual substituição pelo cliente oficial C# da Microsoft ou outro cliente de licença adequada.
- **Não incluímos binários do SDK Microsoft, arquivos do NeoFly ou dados do usuário.**

## Links de referência

- [SimConnect oficial Microsoft](https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/SimConnect_SDK.htm)
- [NeoFly FAQ: localização common.db](https://www.neofly.net/faq)
- [Python-SimConnect — projeto de referência](https://github.com/odwdinc/Python-SimConnect)
- [AISWEB: SBRF](https://aisweb.decea.mil.br/?codigo=SBRF&i=aerodromos)
- [AISWEB eAIP: SBJP](https://aisweb.decea.mil.br/eaip/A%2020-2026_2026_10_29/eAIP/AD%202%20SBJP-pt-BR.html)
- [ANAC: Itapessoca SIPE](https://pergamum.anac.gov.br/arquivos/PA2013-2126.pdf)
