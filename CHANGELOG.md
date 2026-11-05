## v0.8.1 Midnight Ops Alpha.2 — renda da carreira e imagens do mercado

- Novas propostas regionais, freelancer e de companhia têm pagamento recalculado durante a geração conforme nível e reputação persistidos; o ganho por NM favorece serviços de curta distância. Contratos já aceitos não mudam.
- Mudança de versão do gerador de ofertas faz a primeira atualização de mercado aplicar o novo cálculo sem sobrescrever saves ou pagamentos já realizados.
- C172, Baron G58, King Air 350i e Citation CJ4 agora têm ilustrações originais em SVG no catálogo, sem downloads ou créditos externos; C152 mantém a fotografia autorizada com crédito.
- Etiqueta NEW na aba Novas e nas miniaturas da lista.
- Ficha central com rolagem própria, imagens limitadas em altura e rodapé sem texto duplicado.
- Preservadas regras MSFS-only, integridade financeira/SQLite e SimConnect.

## v0.8.1 Midnight Ops Alpha.1 — Mercado de Aeronaves e reconexão discreta

- A v0.8.0 Frota/Hangar, testada pelo piloto, é integrada à `main` e passa a ser a base estável.
- Tela de Mercado de Aeronaves separada do mercado de contratos e da Frota, com abas novas/usadas/aluguel/venda, preview e caixa da carreira.
- Cotações produzidas pelo motor econômico, checkout com confirmação explícita, operações no worker Tk proprietário e resultado informado no painel.
- Validação de aeródromos exclusivamente do MSFS da sessão, proximidade, pouso, ausência de missão ativa, disponibilidade semanal de usada e saldo suficiente.
- Vendas limitadas a exemplares adquiridos no aeródromo onde se encontram, starter e legados protegidos. Aluguéis não entram na Frota própria.
- Solicitações financeiras com token único persistido em `fleet_market_requests`, atomicamente com a transação de compra/aluguel/venda.
- Falha de conexão ao SimConnect registrada uma vez por período de indisponibilidade, mantendo as tentativas automáticas e os demais avisos.
- Regressões novas de backend, segurança HTTP e interface Playwright do mercado.

## v0.8.0 Midnight Ops Alpha.1 — Bloco 1 Frota / Hangar

- v0.7.8.2 homologada pelo piloto integrada à main, sem alterar o save.
- Interface Frota dedicada em três colunas, apenas aeronaves adquiridas na carreira; aluguéis e freelancer não aparecem.
- Seleção visual independente do avião ativo; operações explícitas de ativação, abastecimento e manutenção (legada ou nova).
- Fotos por exemplar persistidas como JPEG normalizado em `fleet_photos` no SQLite, com mesma foto na Dashboard e no Hangar, proporção preservada e crédito da fotografia padrão do C152.
- Rota local de imagem com chave opaca HMAC por sessão, sem upload web arbitrário nem exposição do caminho da máquina.
- Testes de isolamento por exemplar, reinstalação/reabertura SQLite, normalização de retrato e paisagem, navegador e segurança do transporte.

## v0.7.8.2 Midnight Ops Alpha.3 — correção de 20.587 bytes e ícone interno

- Recebe pacotes de aeroportos MSFS 2020 com tamanho `28 + N×33 + 33`, reconhecendo o bloco adicional do SDK sem criar aeroporto extra.
- Cobertura de teste para pacote real de 20.587 bytes e 622 registros; continua proibida qualquer base de aeroportos externa.
- Solicitação mundial adiada para a aeronave permanecer em solo por 3 segundos e limitada a uma vez por sessão SimConnect.
- Tick do Dashboard reduzido de 4 para 2 atualizações por segundo e mapa configurado sem antialias nem cópias mundiais para reduzir atividade da interface.
- Ícone aprovado agora ocupa a barra de título interna do addon, substituindo o avião SVG antigo.
- Persistência da carreira, combustível, peso e contratos sem mudanças.

## v0.7.8.1 Midnight Ops Alpha.2 — Hotfix de alinhamento SimConnect

- Suporta cabeçalho de 28/32 bytes e registros de aeroporto de 33/36/40 bytes na listagem MSFS 2020.
- Valida contagem, paginação, ICAO, coordenadas e altitude; rejeita layouts ambíguos/incompletos, mantendo mercado bloqueado em falha.
- Evita repetir indefinidamente mensagens idênticas de erro durante a importação.
- Acrescenta testes de regressão que reproduzem os pacotes alinhados reportados na v0.7.8.
- Preserva payload, combustível, mapa, versão de banco e a restrição a aeroportos da sessão MSFS.

## v0.7.8 Midnight Ops Alpha.1 — catálogo oficial do MSFS e refuel
- Catálogo de aeroportos restrito ao MSFS 2020 via SimConnect, paginação completa, validação de ICAO/coordenadas, sem fallback externo ou arquivo CSV empacotado. Ofertas e exportação exigem origem/destino existentes na sessão atual.
- Contratos antigos preservados no save, mas bloqueados quando inexistentes no catálogo entregue pelo MSFS.
- Corrigido HTTP 400 no abastecimento em litros por incompatibilidade JSON número × string, mantendo controles de autorização e entradas válidas.
- Diferencia solicitação do plano de voo ao ATC e sincronização do mapa VFR/GPS, que o SimConnect do MSFS 2020 não garante.
- Ícone principal aprovado incorporado ao executável Windows; conversão em .ico multi-resolução durante build.
- Mantido payload automatizado confirmado no MSFS da versão anterior.
- Testes de inventário SimConnect, fonte de coordenadas e protocolo de abastecimento, com CI Windows/Linux.

## v0.7.7 Midnight Ops Alpha.1 — Combustível, peso, manifesto e facilities

- Corrigida persistência de combustível em reaberturas após dias sem uso, sem reset de desgaste individual.
- Popup de reabastecimento por litros, custo/reembolso e crédito rastreado, bloqueio MTOW e estorno automático em falha de escrita confirmada.
- Avisos de estado crítico (combustível e condição ≤20%) no painel e log.
- Manifestos ficcionais de cargas/passageiros com massa por contrato e persistência.
- Auto despacho após aceitar: exportação e pedido de carregamento de rota e peso pelo MSFS com estado pendente/confirmado.
- XP extra +5 e bônus de peso do checklist confirmado somente se payload foi carregado e está dentro de MTOW.
- Preferência NOAA na meteorologia; MSFS somente fallback salvo escolha futura.
- Nova leitura de coordenadas do MSFS via API SimConnect Facilities por ICAO, cache por origem e destino; fonte externa continua como fallback rotulado.
- Redesenhado ícone do despacho; ícone principal permanece candidato à aprovação.
- CI unitário e navegação atualizados; homologação em simulador real pendente.

## v0.7.6 Midnight Ops Alpha.1 — Proa magnética, mapa de missão e autoconexão

- Mapa MapLibre da Dashboard reutilizado na página de detalhes, com rota real do contrato selecionado, tempo estimado pelo modelo da aeronave e apresentação em cartões.
- Menu lateral mantém somente Mercado; alternância Regional / Freelancer nas abas internas.
- Proa magnética e verdadeira via SimConnect sem correção fixa; avião desenhado com proa verdadeira e bússola MAG no HUD.
- App se conecta ao MSFS automaticamente e tenta reconectar sem interromper a UI quando ele abre depois.
- Clima ao vivo não possui verificação de preset; campo removido da apresentação e do cálculo de pontuação, com leitura retrocompatível de planos antigos.
- Classificador de táxi utiliza ON ANY RUNWAY quando disponível, aceleração e curva como fallback, e janela separada para taxiamento após frenagem de pouso.
- Penalidade pós-pouso registra até −2 XP no voo recém-encerrado (nunca voos anteriores), transação SQLite idempotente e checkpoint recuperável.
- Testes de navegador, estimativa, sensores, runway, partida, toque e frenagem; homologação do MSFS físico pendente.

## v0.7.5 Midnight Ops Alpha.1 — Procedimentos e mercado freelancer Nordeste

- Mercado lateral consolidado com abas internas Regional/Freelancer; buscador freelancer sobre polígono aproximado Nordeste e autonomia por modelo, até seis ofertas.
- SimConnect opcional lê assistências específicas, IA, Zulu, luzes, motor e G sem forçar controles.
- Despacho: bônus +3% relógio Zulu sincronizado e +3% assistências monitoradas desligadas. Clima ao vivo não verificável, sem premiação por declaração.
- XP segurança entre -15 e +7, incluindo pouso suave +4 só sem arremetida. Arremetida e toque-e-arremetida não liquidam contrato.
- Checkpoint mantém novos indicadores; XP/receita de cada voo continuam atômicos e idempotentes por decolagem.
- Atualizados testes de sensor, arremetida, táxi, iluminação, XP e mercado; CI e homologação MSFS real são etapas distintas.

## 0.7.4 Midnight Ops Alpha.1 — Menu persistente e mercados em páginas

- Navegação no conteúdo principal mantendo sidebar no lugar; mercados Regional e Freelancer separados no menu e acessíveis por abas, sem modal.
- Busca e seleção de contratos com detalhes/aceite em página própria; backend Python/SQLite/SimConnect e validações de oferta preservados.
- Planejamento, Frota, Piloto, Finanças, Companhias, Logbook, Relatórios e Configurações ganham páginas de consulta de dados existentes. Edição avançada ainda depende do botão de ferramenta clássica, sem abrir janelas automaticamente ao navegar.
- HUD do mapa reorganizado: satélite no canto superior direito, crédito EOxCloudless compacto com atribuição completa disponível, e controles de zoom livres de obstrução.
- Regressão de navegador e testes estáticos atualizados; homologação MSFS real ainda necessária.

## 0.7.3 Midnight Ops Alpha.1 — Layout full-map, heading verdadeiro e mercado WebView2

- **Mapa full-width**: contêiner MapLibre visível antes da inicialização do canvas; observador e resize após janela/área mudarem de tamanho. Pan, scroll e zoom preservados.
- HUD reorganizado: zoom/centralizar no lado direito, satélite no canto inferior direito, crédito EOxCloudless no canto inferior esquerdo, sem sobreposição. Removido texto indevido "Google Satélite" do canto superior.
- **Proa verdadeira ao vivo**: SimVar opcional `PLANE_HEADING_DEGREES_TRUE` (radianos); conversão para graus, sinalização de leitura ausente e ícone vetorial ciano rotacionado independentemente da posição/velocidade.
- **Missões/Freelancer dentro do Midnight Ops**: modal com ofertas do backend, filtro regional/freelancer, pesquisa e aceite com validação existente, sem janelas Tk escondidas atrás da WebView.
- Sem alterações nas regras homologadas do motor de carreira. Testes automatizados abrangem rumo no solo, dados de contrato, controles e proporções do mapa, seleção de missões e build WinForms.

## v0.7.2 Midnight Ops Alpha.1 — Hotfix da janela nativa, mapas grátis e clima
- Reinclui Python.Runtime/CLR e cffi no pacote Windows, desativa UPX e testa WinForms em .exe real.
- Mapa OpenFreeMap com MapLibre local, sem Google; satélite EOxCloudless 2016 opcional com créditos.
- Posição, rota, marcador ciano; scroll, arraste, reenquadramento e fallback offline.
- NOAA METAR no destino com cache async; clima do MSFS na origem/chegada via SimConnect.
- Contratos, dinheiro, XP, combustível e aeronaves sem alterações de regra.

## 0.7.1 Midnight Ops Alpha.1 — Reputação e Google Satélite

- Implementa reputação virtual persistente (reconstruída do diário SQLite histórico, sem migrar esquema e sem duplicar ganhos).
- Substitui NASA Blue Marble pelo mapa Google Satélite por API oficial, com chave configurável localmente, scroll, arraste e reenquadramento.
- Sem chave Google: fallback local interativo, sem tiles NASA.
- Troca marcador por silhueta vetorial ciano proporcional, com orientação aproximada via deslocamento observado.
- Adiciona controles e testes de regressão, documentação de licenciamento e faturamento do Google Maps.
- Não muda SimConnect, motor de voos, pagamentos, XP ou combustível.
- Integração Google ainda requer chave configurada e homologação real no MSFS do piloto.

# Changelog

## 0.7.0-midnight.alpha.1 — branch de redesign sobre v0.6.1 (03/11/2026)

- Dashboard HTML/CSS local em WebView2, cabeçalho, sidebar, mercado, contrato, mapa, telemetria, METAR indisponível, log, checklist e frota.
- Apresentação com dados reais; comandos retornam ao motor existente na thread Tk, com transporte loopback autenticado e limites de entrada/fila.
- Foto de piloto local, país da base, progresso real de XP, inventário de combustível e ações de manutenção/abastecimento.
- Foto C152 CC BY-SA 4.0, cenário decorativo gerado por IA, assets vetoriais originais e fonte Barlow Semi Condensed OFL embarcada.
- Testes de apresentação/segurança, matriz gráfica de 15 áreas lógicas e build Windows PyInstaller em CI.
- Main preservada; PR de integração em draft para reconciliação das alterações posteriores da v0.6.2/0.6.3.
- Mapa NASA GIBS Blue Marble histórico com grade offline de recuperação e coordenadas reais.
- Limitações: detalhe geográfico limitado, ilustração genérica para modelos sem foto, telas secundárias Tk, METAR/reputação indisponíveis, sem validação física MSFS/WebView2.


## 0.6.1-alpha.1 — localizador e combustível em SimConnect (03/11/2026)
- Starter C152, aeronaves compradas e alugadas agora têm aeroporto atualizado no pouso (inclusive voo sem contrato), sem movimentar avião de freelancer/companhia.
- Backfill controlado e único do último pouso conhecido do starter, sem alterar dinheiro/XP. Backup SQLite pré-v0.6.1.
- Inventário de combustível por aeronave (`fleet_fuel`) com primeira calibração no solo e consumo acompanhado por tanques individuais.
- Detecção de reabastecimento manual no MSFS e restauração pelo SimConnect, somente quando o modelo, a capacidade e a telemetria forem compatíveis. Três tentativas máximas sem confirmação.
- Abastecimento no Hangar contra pagamento em R$, sem dupla cobrança de consumo ao concluir voo gerenciado.
- Toggle de controle de combustível, ligado por padrão; desligado congela penalidade de 30% na decolagem sobre recompensa e XP, com lançamento em extrato e idempotência.
- Guardas para combustível ilimitado, aeronaves de terceiros e leitura parcial; não afirma sucesso da escrita sem prova física do MSFS.
- Testes automatizados de localização, consumo, calibração, correção e restauração, além de regressão integral; suporte experimental ao MSFS 2020 ainda precisa ser validado em PC real.


## 0.6.0-alpha.1 — frota individual, despacho e ponte de painel local

- Frota avançada com novas/usadas (instâncias próprias, registro individual), aluguel, revenda, mercado semanal local, serviços e localização; preserva frota legada.
- Detector read-only de modelos e liveries em `aircraft.cfg` do Official/Community, sem afirmar posse na conta.
- Despacho offline para contratos na base do piloto + exportação `.PLN` e pedido explícito de carga SimConnect ao entrar no mundo.
- Checklist de realismo com fatores de previsão, peso e combustível com telemetria opcional, e declarações manuais explicitamente identificadas.
- Até 18% de bônus sobre recompensa e XP do contrato, congelado na decolagem em checkpoint e pago atomicamente no pouso; comportamento idempotente após reinício.
- Correção: títulos SimConnect com prefixo do fabricante são reconhecidos como mesmo modelo de aeronave no despacho.
- Ponte HTTP local apenas loopback/somente leitura, UI no navegador com esboço geométrico de rota, saldo e posição; projeto-fonte de toolbar que requer SDK e validação física.
- Migração aditiva SQLite com backup `pre_v060`, sem alterar perfil, caixa, XP, voos ou NeoFly.
- Testes unitários de frota, mercado, scanner de aeronaves, despacho, bônus, persistência e bridge, mais fluxo ponta a ponta em Tk/SQLite e reinício simulado.
- **Limitação assumida:** não existe integração validada que monte Mapa-Múndi/avião automaticamente, nem VFR nativo, clima real confirmado pelo simulador ou painel toolbar já compilado.

## 0.5.1-alpha.1 — barras de progresso e habilitações com horas (02/11/2026)
- Barra visual de nível do piloto no cabeçalho, com progresso relativo ao nível atual.
- Barras visuais individuais e texto atual/meta para horas, número de voos e XP por habilitação.
- Requisitos novos e configuráveis em código: PCA 10 h/8 voos/160 XP, IFR 20 h/16 voos/320 XP, MLTE 30 h/24 voos/450 XP, PLA 60 h/50 voos/1500 XP.
- Janela de perfil rolável; visual Midnight preservado.
- Respeita horas somadas do diário (sem arredondar para conceder habilitação).
- Habilitações já concedidas não são removidas, saldos e banco sem migração destrutiva.
- Testes adicionais de metas, persistência, progressão de nível e elegibilidade.
- V0.4.0: piloto confirmou no MSFS voo, missão, XP e carregamento do plano VFR.


## 0.5.0-alpha.1 — Mercado/Finanças/Manutenção (03/11/2026)
- BRL fictício com migração 1:1 do valor nominal, sem cambial; UI financeira e mercado em R$.
- Rebalanceamento de propostas regionais e freelancer com piso e cálculo por tempo estimado; rotas mais curtas para nível baixo.
- Cache de propostas invalidado apenas uma vez, sem reescrever contratos aceitos.
- Ledger financeiro com receitas, combustível, taxas, impostos opcionais, compra, seguro, manutenção e empréstimos.
- Hangar com aeronave inicial Cessna 152 resgatável uma vez, registro de frota, desgaste e revisão.
- Combustível real medido no simulador quando disponível, senão estimado, cobrado apenas no livro da carreira.
- Financiamento 8% fixo e pagamento parcial; seguro registrado, mas sinistros ainda pendentes.
- Pouso/crédito/XP/despesas/desgaste numa transação; proteção contra eventos duplicados.
- Backup independente da v0.5 e migração aditiva da base; sem custos retroativos.
- Testes de compatibilidade e de finanças. [Detalhes](docs/BLOCO_4_FINANCAS.md).

## 0.4.0-alpha.1 — modalidades de carreira e plano VFR (02/11/2026)
- Nova modalidade `autonomo` por padrão, `empregado` após seleção semanal, e `empresario` como registro inicial de companhia no endgame.
- Catálogo limitado de quatro vagas semanais **fictícias**, com empresas de referência e validação de nível/horas/habilitações; uma candidatura por semana, resultado após o ciclo, sem duplicidades.
- Trechos regionais para piloto contratado, com modelo obrigatório e pagamento único; não existe pagamento periódico de salário sem voar nesta Alpha.
- Acesso ao registro de empresa própria no endgame, com dedução única e sem gestão operacional nesta versão.
- Exportação de `.PLN` VFR e comando explícito para carregar no MSFS 2020 em solo pela biblioteca SimConnect; não troca aeronave. Integração ainda depende de teste no MSFS real.
- Migração SQLite aditiva, testes de regressão e documentação de futura frota IA/liveries.


## 0.3.0-alpha.1 — Bloco 2: contratos regionais e freelancer (02/11/2026)
- 9 categorias de missão com níveis de desbloqueio, horas e qualificações (PPA/PCA/IFR/MLTE/PLA); progressão XP → nível sem perda de dados anteriores.
- Catálogo mundial opcional fornecido pela dependência MIT `airportsdata==2026.8.2`, com fallback local. Não gerar ofertas do mundo inteiro: no máximo 13 contratos perto da origem atual.
- Mercado por aeroporto-base/posição atual, propostas determinísticas por dia, cache local SQLite com vencimento e limpeza por região.
- Freelancer com salário e aeronave de contratante (C152/C172/G58/King Air/CJ4), escolhida manualmente no MSFS até integração futura; validação de modelo na decolagem e no pouso.
- Experiência por família/modelo da aeronave em novos voos, sem inventar XP ou aeronave dos voos antigos.
- Checkpoint preserva missões dinâmicas durante reconexão/reinício; bloqueio transacional de pagamentos repetidos por contrato e por voo.
- Tela dedicada ao mercado com seleção de proposta e detalhes; contratos fixos anteriores mantidos para testes e regressão.
- Migração SQLite aditiva, sem apagar piloto, habilitações, XP, saldo ($6.270 registrado pelo usuário), histórico ou checkpoint.
- **49 testes automatizados locais e teste gráfico do mercado aprovados.** A geração global e a leitura TITLE pelo SimConnect real ainda precisam ser verificadas no Windows.
- Limitações: variantes de missão têm a mesma conclusão básica por chegada ao destino; freelancer não injeta uma aeronave no simulador nem valida tail number/propriedade. Painel MSFS in-game segue prioridade transversal.


## 0.2.0-alpha.1 — Bloco 1: Piloto e habilitações (02/11/2026)
- Cadastro e edição de piloto único por carreira: nome, indicativo e base ICAO.
- Painel próprio de piloto com progressão virtual, horas de voo, XP e cursos PPA/PCA/IFR/MLTE/PLA.
- XP por novos voos finalizados após criação do perfil: 25 por voo + 15 por contrato pago, atômico com o voo e sem duplicidade.
- Migração aditiva SQLite preserva saldo, histórico e checkpoint. Voos anteriores contam nas estatísticas, sem XP retroativo.
- Habilitações por pré-requisito (voos, XP e etapas anteriores); contratos existentes permanecem acessíveis.
- Requisitos adicionais (falhas opcionais, mapa in-game, multiplayer, companhias e pinturas) no documento de escopo.
- 34 testes automatizados locais aprovados e teste gráfico de criação/reabertura de perfil em ambiente virtual.
- **Ainda sem teste físico no Windows da nova UI; sem restrições de contratos por qualificação neste bloco.**

## Validação física v0.1.2 (02/11/2026)
- Voo real SIPE → SIFC completo: decolagem 19:45:14, pouso 19:55:07, −172 ft/min estimados, crédito de $420 e saldo $6.270.
- O piloto confirmou que, ao reabrir o programa, o saldo persistiu. Reconexão após falha real durante voo ainda pendente de teste específico.

## 0.1.2-alpha — patch telemetria e recuperação (02/11/2026)
- Corrigida desconexão fatal por `GROUND_VELOCITY` ausente em única leitura.
- Leitura degradada de velocidade de solo e razão vertical; perda de variável essencial causa descarte temporário, com reconexão após falhas consecutivas.
- Worker com reconexão automática em caso de sessão SimConnect quebrada; mensagens por geração evitam eventos de sessões antigas.
- Checkpoint de contrato/voo durante o voo, recuperado ao reabrir o aplicativo.
- Gravação atômica de diário e crédito com identidade única por decolagem; migração compatível com `carreira.db` anterior.
- Nova rota curta SIPE → SIFC (Coroa do Avião / Igarassu), recompensa de $420.
- Botão Salvar log para diagnóstico; UI informa `~` em velocidades de solo estimadas.
- Testes novos de regressão para falha de SimVar, reconexão, retomada, idempotência, migração e rota.
- Painel na toolbar do MSFS continua como próxima etapa documentada; não incluído neste patch.

## 0.1.1-alpha — 2026-11-02

- Demo e comunicação SimConnect confirmadas em Windows real pelo piloto.
- Busca local restrita de `common.db` e `std.bin` para versões/instalações diferentes do NeoFly.
- Seletor permite `.bin` e `.db`; ferramenta informa formatos não SQLite sem tentar leitura não autorizada.
- Documentação atualizada e mais testes automatizados.
- Dados de NeoFly **não** foram localizados nem importados nesta versão.

## 0.1.0-alpha — 2026-11-02

- Início de projeto **independente** NeoFly, nome provisório AeroCarreira Lab.
- Implementado motor de telemetria, voo, contrato e saldo.
- Implementado painel desktop no Windows com demo sintética e conexão opcional SimConnect.
- Persistência de voo/saldo em SQLite.
- Inspetor seguro do banco `common.db` que copia antes de ler, preservando fonte e não exportando registros.
- Testes de lógica, banco e análise.
- **Pendente:** validação com simulador real e análise do banco real do usuário.
