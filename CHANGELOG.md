## v0.9.0 InGame Alpha.3 — executável sem CMD, fonte PT-BR e arraste nativo

- **Windows GUI:** PyInstaller `--windowed` para iniciar o FlightSim sem a janela CMD; validação do subsistema PE GUI no CI e smoke tests preservados.
- **Unicode:** fontes Barlow Regular/SemiBold já existentes no projeto são servidas com MIME `font/ttf` e `font-src 'self'` no CSP da ponte InGame, com `@font-face` e UTF-8 explícito. Acentos são preservados; validação dos glifos deve ser feita no Coherent real.
- **Toolbar:** sincronização com eventos `panelActive` e `panelReady`; tenta restaurar `draggable` do `ingame-ui` somente em painel ativo, sem interceptar mouse no iframe e sem substituir a barra de título nativa.
- **Distribuição:** executável Windows e source SDK Alpha.3 separados, reteste físico necessário para confirmar arraste e glifos no MSFS.
- `main` permanece na v0.8.7 homologada até aprovação.

---

## v0.9.0 InGame Alpha.2 — Midnight Tablet e painel ajustado

- Corrige o wrapper do SDK após o primeiro teste físico: remove `content-fit`, melhora preenchimento e dimensões iniciais, mantém o movimento sob responsabilidade do MSFS.
- Substitui os cards estreitos por um tablet Midnight de quatro páginas reais de leitura, menu lateral adaptativo e visual responsivo. O modo InGame continua sem ações financeiras.
- Testes de browser passam a verificar navegação, atualização, mapa, conexão e diversas resoluções. Build Windows e SDK source distribuídos separados.

## v0.9.0 InGame Alpha.1 — Foundation, toolbar e telemetria read-only

- **Ajuste após primeiro teste físico:** usuário confirmou painel visível na toolbar, conexão real com SimConnect e dados carregados. Movimento/redimensionamento do wrapper exigiu patch (ainda pendente de reteste no MSFS).
- **Tablet Midnight:** layout EFB horizontal com navegação lateral Painel, Mapa, Aeronave e Carreira (inferior em janela estreita); interface unificada e responsiva. Sem habilitar comandos de carreira nesta Alpha.
- **Wrapper SDK:** removido `content-fit`, iframe com dimensões internas flexíveis, mínimo SPB aumentado e tamanho inicial mais adequado. Movimentação e bordas seguem sob controle do MSFS 2020, recomendando Reset Panels quando a geometria fica travada.


- **FlightSim InGame:** painel Midnight compacto/completo com contrato, saldo, aeronave, instrumentos, combustível, rumo e mapa SVG leve baseado em coordenadas verificadas.
- **Ponte:** evolução da `LocalPanelServer` em `127.0.0.1:8769`, sem POST ou ações financeiras. Protocolo 2, estado real publicado do motor Tk/SimConnect, endpoint v1 autenticado por chave de leitura efêmera injetada em página local e health/diagnostics.
- **SDK:** package-fonte para MSFS 2020 com SPB + Copy, wrapper da toolbar, icon SVG próprio em ambas localizações compatíveis e iframe para a aplicação local; compilação real depende de SDK e MSFS físico.
- **Resiliência:** dados indisponíveis não são inventados; estado offline/reconectando, atualização manual, atualização periódica 1,5 s, reconexão sem gravar no SQLite.
- **Validação:** testes unitários de host, token, endpoints, somente leitura, assets e XML; Playwright em bridge real com resolução variada e reconexão. CI segue compilação Windows, unit Linux/Windows 3.11/3.13 e dashboard.
- **Distribuição:** Windows 0.9.0 e artifact de código-fonte InGame separado; manual do Project Editor, Community Steam e diagnóstico em `docs/INGAME_V090_BUILD.md`.
- A primeira Alpha **não comprova** que o SPB funciona no MSFS real, nem habilita comandos no jogo: homologação física pendente na branch. A `main` permanece v0.8.7.

---

## v0.8.7 Midnight Ops Alpha.1 — Configurações, companhias e conquistas com foco

- **Configurações:** última tela Midnight Ops nativa com seis seções (Simulador, Carreira, Interface, Dados e backups, Diagnóstico e Sobre), mantendo navegação lateral. Preferências persistentes e autenticação do backend, sem operações de SQLite no JavaScript.
- **Conexão:** tentativa inicial e reconexão automática configuráveis; estado, telemetria, aeronave ativa e catálogo MSFS exibidos com disponibilidade real. Ferramentas avançadas e Demo separadas.
- **Carreira:** controle de combustível e penalidade 30% R$/XP, imposto virtual 4%, preferência futura de falhas (ainda não injeta falhas), bloqueios em voo.
- **Interface:** escala 80–150%, redução de animações, satélite inicial e notificações de desbloqueios configuráveis.
- **Backups:** cópia consistente por SQLite backup API dos bancos de todos os perfis (inclusive fotos) em ZIP; restauração valida arquivo e cria *novos* perfis. Nenhum save é substituído automaticamente; avatar restaurado tem caminho atualizado.
- **Companhias:** Azul, GOL e LATAM possuem catálogos específicos conforme escopo, A320neo incluído nas três; AeroNordeste preserva cinco clássicos e aceita avançados habilitados. Salários-base 30 mil/23 mil/17 mil/9 mil por sete dias reais, mantendo as metas semanais e a independência dos voos particulares.
- **Habilitação de modelo:** voos MSFS reais no modelo reconhecido, com dois treinos de pelo menos 10 minutos e pousos válidos; banco separado de habilitações por tipo e validação no backend. Cessna 152 não permite contrato GOL. Freelancer antigo preservado.
- **Conquistas:** evento persistido imediatamente; modal só abre quando FlightSim estiver visível e com foco, com fila e confirmação após fechar, sobrevive a reinícios.
- Testes novos de regras, ambiguidade de títulos, certificação, fila de eventos, backups/segurança; Playwright de navegação Configurações e foco. Build Windows e CI obrigatórios, homologação física no MSFS pendente.
- Documento de aceitação: docs/V087_SETTINGS_AIRLINES_FOCUS.md. PR de homologação #22 separada da main.

---

## v0.8.6 Midnight Ops Alpha.1 — Logbook + Análises e Relatórios

- Duas telas nativas Midnight Ops, acessíveis pelo menu lateral, sem abrir a interface Tk clássica.
- **Logbook:** histórico SQLite do piloto ativo, data local/UTC, coordenadas registradas, modelo, modalidade, contrato, duração, taxa de pouso, alertas, XP e resultados pessoais/empresariais (sem misturar patrimônios).
- Busca por aeronave/contrato/anotação, filtros 7/30/90 dias/toda a carreira, modalidade/modelo, ordenação e paginação de 12 voos por página.
- Ficha de voo com dados imutáveis e anotações editáveis em nova tabela `flight_notes`. POST autenticado, limite de 1.200 caracteres, sem mutação das tabelas de voo, XP ou finance.
- Exportação CSV compatível com Excel brasileiro (UTF-8 BOM, separador ;), respeitando os filtros; escape preventivo de fórmulas em células de texto.
- **Análises:** voos/horas, média dos pousos, XP dos voos, resultados pessoais/empresariais, salários semanalmente liquidados, despesas operacionais, horas por modelo, modalidades, categorias de pouso, atividade mensal e comparação entre aeronaves.
- Sem inferir ICAO de coordenadas antigas e sem apresentar distância em linha reta como distância efetivamente percorrida. Informações ausentes aparecem como ausentes.
- Caching de snapshot baseado nos registros de voos, notas, XP e ledgers; sem recalcular tudo a cada polling de 500ms, e sem adicionar escrita automática.
- Testes unitários de histórico e integridade do SQLite; testes de API com autenticação; Playwright em estado vazio e com amostras de voos; executável Windows PyInstaller com os dois novos assets.
- Regras de frota/qualificações de Azul, GOL e LATAM documentadas no escopo da mesma branch, **ainda não implementadas nesta Alpha.1**; não alterar as regras de contratação sem o mecanismo de habilitação por modelo.

## v0.8.5 Midnight Ops Alpha.2 — Planner VFR interativo

- Companhias AeroNordeste, Azul, GOL e LATAM exibidas sem os sufixos “fictícia” ou “simulação”, mantendo códigos, critérios de admissão, salários, contratos e regras inalterados.
- Editor de rota com **Planejar rota** para calcular a linha direta em prévia antes do salvamento. Clique direito no mapa adiciona waypoint imediatamente; até oito pontos com nomes FSC01, FSC02… e coordenadas válidas. Shift+clique e toque longo também funcionam.
- Waypoints do MapLibre arrastáveis pelo mouse; posição e pernas atualizadas ao soltar. O mapa SVG alternativo oferece a mesma edição por alças arrastáveis.
- X vermelho visível ao passar o mouse na linha do waypoint (ou em foco/touch) exclui o ponto e atualiza a rota no mapa sem clicar em salvar.
- Distância total, pernas, proas e duração aproximada recalculadas ao editar. Prévia autoritativa validada pelo motor em função do catálogo aeroportuário confirmado do MSFS e sem gravação no SQLite; atualização geométrica imediata na UI enquanto aguarda retorno.
- **Salvar planejamento** continua transação explícita, necessária antes de exportar .PLN ou enviar ao MSFS. Nenhuma alteração em economia, XP, contratos ou aeronave é causada ao editar a rota.
- Engrenagem das Configurações substituída por SVG simétrico, mantendo tema Midnight e navegação.
- Protegidos testes de transporte autenticado, ausência de persistência da prévia, edição/remoção de waypoints, labels das companhias, interface em Playwright e compilação Windows/Linux.
- MP3 de conquistas permanece removido por solicitação anterior. PR fica em rascunho até homologação no MSFS; `main` inalterada.

## v0.8.5 Midnight Ops Alpha.1 — Airline Operations

- Progressão como empregado com metas de horas/voos semanais e compromissos opcionais de 0%, 10% e 20%, com bônus ou redução proporcional por não atingir a meta escolhida.
- Contratos da empregadora contam para a folha semanal e não dão saldo nem XP imediatamente ao concluir cada voo.
- Companhia própria fundada com aporte de R$ 400 mil, caixa empresarial, frota e operações separados do patrimônio pessoal; receitas e custos dos voos corporativos permanecem no ledger da empresa.
- Finanças v0.8.4 integradas na branch de desenvolvimento; sem merge na main até homologação das versões pendentes.

## v0.8.4 Midnight Ops Alpha.1 — Financial Center

- Cinco abas financeiras nativas: Resumo, Extrato, Operações, Patrimônio e Banco.
- Indicadores de receita, despesas, caixa, resultado operacional e patrimônio estimado; gráficos legíveis de fluxo mensal e gastos por categoria.
- Ledger único preservado, seguradoras e prêmios efetivamente pagos incluídos na contabilidade, sem cobrança nova nem retroatividade.
- Extrato filtrável com comprovantes e exportação CSV **integral**, mantendo dados antigos inalterados.
- Rentabilidade do voo derivada de movimentos financeiros reais por flight_key, sem inventar dados onde não existem.
- Valor investido e valor de revenda apenas para aeronaves compradas; starter e aluguel não geram valor de revenda inventado.
- Banco: limites de R$ 1.000 a **R$ 150.000**, custo único 8%, parcela personalizada, confirmação antes do débito, deduplicação por UUID transacional.
- Endpoint CSV autenticado no loopback, sem acesso SQLite na thread HTTP, com testes Python/Playwright/Windows.
- PR rascunho isolado até homologação visual/funcional no MSFS, protegendo a main v0.8.3 Alpha.3.

## v0.8.3 Midnight Ops Alpha.3 — FlightSim: nome, insígnias e patrimônio pago

- Marca visual do aplicativo, certificados, janelas e nomes de exportação: **FlightSim**. Repositório, pacote Python `aerocarreira`, identificadores internos do painel SDK e banco original permanecem iguais para não quebrar integrações nem saves.
- Executável e distribuição Windows passam a se chamar `FlightSim.exe` e `FlightSim-0.8.3-midnight-alpha3-Windows`.
- Silhueta padrão de aeronave redesenhada a partir da referência enviada pelo piloto: vista superior, limpa, sem inclinação ou isometria. Ícones e marcadores de avião passam a usar o mesmo símbolo, inclusive no mapa (proa 0 = nariz para cima).
- Medalha **Primeira Aeronave** agora apresenta aeronave centralizada em pista e número **1º** legível. Ajustados **Primeiro Voo**, **100 Horas** e os números **70%/90%** para não ficarem encobertos.
- Selos de licença PPA → PLA substituem a estrela deformada por silhueta aeronáutica simétrica, mantendo acabamentos progressivos já homologados.
- A propriedade do **C152 inicial gratuito não conta** em Primeira Aeronave nem Frota Estabelecida. Comprar um C152 adicional conta normalmente.
- Frota de três conta apenas unidades pagas que ainda pertencem ao piloto (vendas podem suspender a medalha). Primeira Aeronave reconhece compras históricas mesmo após venda, usando `fleet_log` de forma idempotente, sem apagar conquistas válidas.
- Testes de regressão de starter, compra, aluguel, venda, marca, ícones, interface e empacotamento. O PR permanece separado da `main` até homologação física e visual pelo piloto.

## v0.8.3 Midnight Ops Alpha.2 — identidade visual premium revisada

- Evento de medalha, perda, reconquista ou promoção mantém o diálogo aberto depois da animação até o piloto fechar com botão, ESC ou clique no fundo.
- Distintivos de graduação passam a ter desenho vertical esguio, sem distorção CSS; removida a insígnia anterior do cabeçalho, preservando a patente Midnight e a medalha equipável na foto.
- Todas as 13 medalhas têm símbolos próprios: avião pousado com 1º para primeira aeronave, três aviões diante do hangar para a frota, check com 70%/90% e metal nobre para reputação, além de ícones específicos das demais conquistas.
- Licenças PPA, PCA, IFR, MLTE e PLA apresentam selos gráficos e progressão de acabamento, de aço a dourado, com títulos, dados e requisitos legíveis.
- Gráficos de sensibilidade de pouso, contratos mensais e horas por aeronave exibem escalas e unidades, valores visíveis, legenda, média de pousos e detalhamento por categoria.
- Prévia Admin continua separada do piloto oficial; Minha História e regras econômicas não foram alteradas.
- Testes Playwright reforçados: diálogo ainda aberto após duração da animação, reconquista, promoção, 13 motivos, 5 licenças, eixos/legendas e distintivo único no cabeçalho.
- Branch/PR permanecem não mesclados até homologação visual no MSFS 2020.

## v0.8.3 Midnight Ops Alpha.1 — Pilot Career e laboratório Teste

- A nova aba **Meu Piloto** reúne identidade premium, foto, brasão permanente, medalha especial equipável, progressão de XP, 18 graduações aeronáuticas de níveis 1–100 e 13 conquistas.
- Galeria de certificados premium PPA/PCA/IFR/MLTE/PLA, gráficos independentes de pouso, contratos e horas por aeronave, linha do tempo de promoções, eventos e conquistas.
- Conquistas condicionais (reputação 70/90 e frota de três aeronaves) perdem o estado ativo quando deixarem de cumprir o requisito; o emblema se divide discretamente na animação. Recuperar condição restaura conquista e registra novo evento. Conquistas permanentes nunca são retiradas por queda de estatística.
- Novo gerenciador de perfis: carreira oficial permanece em seu SQLite original, com backup consistente antes da migração, e novos pilotos ficam em banco independente. Troca somente desconectado/em solo.
- Perfil `Teste` com Admin/Showcase isolado para visualizar todos os distintivos/licenças/medalhas, simular nível/XP/reputação e testar animações, sem editar o XP e o saldo reais.
- Planejamento VFR: waypoint por clique direito/Shift+clique/toque longo no mapa com confirmação e botão Limpar Plano sem cancelar contratos nem apagar voos.
- Bônus de XP/dinheiro: exclusão de pontos por declarações manuais, recompensa apenas por amostras MSFS verificadas e congelamento seguro na decolagem.
- CI Windows/Linux, testes SQLite, Playwright, empacotamento Windows; publicação em branch separada para homologação antes de atualizar `main`.

## v0.8.2 Midnight Ops Alpha.1 — Planejador + Despacho unificados

- Página Flight Operations com editor de origem/destino, oito waypoints numéricos, altitude VFR e pernas (distância/rumo) calculadas pelo motor Python.
- Planejamento de voo livre separado de contratos, sem dinheiro, XP ou recompensa; modo contratado não permite trocar origem e destino.
- Waypoints USER gerados nos arquivos .PLN na ordem planejada. Estado salvo por carreira no SQLite, com revalidação de ICAOs pelo catálogo da sessão MSFS.
- Mapa MapLibre compartilhado entre Dashboard, detalhes de contrato e planejador; suporte a rotas com múltiplas pernas e sem duplicação de WebGL/créditos.
- Despacho operacional: checklist nativo, combustível estimado com reserva, peso/MTOW quando disponível, manifestos, meteorologia informativa e estados de envio pelo SimConnect.
- Bônus existentes seguem avaliados no motor somente para contratos, congelados na decolagem. Sem bônus por clima em tempo real; texto legado de log meteorológico removido.
- Envio ao SimConnect é indicado como ATC e jamais confirmado como GPS/VFR. Exportação de voo livre não altera a carreira.
- Testes automatizados e validação de pacote Windows; sem migração destrutiva de saves.

## v0.8.1 Midnight Ops Alpha.3 — Showcase fotorealista das aeronaves

- Substituídas as quatro ilustrações SVG por imagens fotorealistas originais aprovadas pelo piloto, referentes ao Cessna 172 Skyhawk, Baron G58, King Air 350i e Citation CJ4.
- JPGs otimizados 1100 × 825, incluídos no executável para uso offline. Não existe download automático, atribuição a terceiros nem alteração das fotos personalizadas da Frota.
- A foto padrão do Cessna 152 e seu crédito permanecem inalterados. O catálogo reutiliza a imagem por modelo em Novas, Usadas e Aluguel; Frota/Hangar e Dashboard também exibem o showcase quando não houver fotografia individual cadastrada. Venda e Frota sempre priorizam a foto própria.
- Verificações de catálogo, leitura JPEG e presença real dos arquivos no pacote Windows. Economia, regras de contratos, SQLite e SimConnect preservados.

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
