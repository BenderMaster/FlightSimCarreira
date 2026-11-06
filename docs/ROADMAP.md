## v0.7.3 — Proa real e operações do mapa / mercado no Midnight Ops
- [x] Eliminar mapa dimensionado pela metade, manter responsividade e câmera controlada pelo piloto.
- [x] Separar o botão Satélite do zoom/recentralização e posicionar créditos sem sobreposição.
- [x] Ler proa verdadeira do MSFS em radianos via SimConnect, converter para graus e rotacionar ícone na posição fixa.
- [x] Abrir seleção de contratos regionais e freelancer em diálogo HTML do Midnight Ops; filtros e busca.
- [x] Preservar elegibilidade, aeronave designada, pagamento e motor Python.
- [x] Validar código e navegador por testes automatizados, incluindo mapa mock 100% de largura e WinForms empacotado.
- [ ] Homologar mapa WebGL e proa ao vivo em MSFS 2020 no Windows do piloto.

## v0.7.2 Midnight Ops — hotfix nativo e mapas sem cartão
- [x] Smoke de importação pythonnet/WinForms no pacote Windows; verificar CI do commit final.
- [x] Mapa OpenFreeMap e satélite opcional EOxCloudless 2016 CC BY 4.0.
- [x] Zoom, drag, reenquadramento e aeronave ciano; mapa offline mantido.
- [x] METAR NOAA em background e condições na posição do avião MSFS, próximas aos aeroportos.
- [ ] Homologar abertura na janela Windows real e clima/mapa externo com voo físico.
- [ ] Continuar migração das telas da carreira para a UI Midnight Ops.

## Marco homologado — v0.7.0 Midnight Ops (03–04/11/2026)

- [x] Piloto aprovou visualmente o Dashboard WebView2 no MSFS 2020 Steam.
- [x] Executável Windows abriu, carregou carreira e manteve conexão/telemetria SimConnect.
- [x] Mercado e contrato, mapa com rota correta, monitoramento de combustível, decolagem/pouso, crédito de contrato/XP e persistência após reinício validados em voo físico pelo piloto.
- [x] Motor funcional sólido v0.6.1 preservado; experimentos visuais Tk v0.6.2/0.6.3 **não incorporados**.
- [x] 133 testes antes do patch e compilação Windows do WebView concluídos no GitHub.
- [ ] Painel integrado diretamente na toolbar do MSFS continua pendente.

## Patch v0.7.1 Midnight Ops Alpha.1 — reputação e mapa

- [x] Reputação calculada do diário real, incluindo voos históricos e sem pagamentos/XP retroativos.
- [x] Mapa NASA retirado; Google Maps JavaScript API via chave local, satélite e overlay de rota/posição.
- [x] Ícone ciano vetorial proporcional, com rumo aproximado por deslocamento.
- [x] Zoom por scroll, arrastar, botões ± e reenquadramento, inclusive fallback de coordenadas sem chave.
- [x] Chave Google configurável no mapa, sem credencial hardcoded; documentação de faturamento/limites/privacidade.
- [x] 6 jobs CI aprovados (Windows/Linux + dashboard + pacote Windows) antes de homologação física.
- [ ] Configurar chave Maps JS no PC do piloto e validar renderização/controles reais no WebView2.
- [ ] Confirmar valor de reputação com banco de carreira existente e voo de teste, conferir saldo e combustível.
- [ ] Evoluir mapa com serviços aeroportuários e meteorologia sem afirmar dados não verificados.

## v0.5.1 Alpha.1 — progresso visual do piloto
- [x] Barra de nível no painel principal.
- [x] Horas, voos e XP com barras individuais por habilitação; janela rolável.
- [x] Requisitos de horas reais do diário e permanência de habilitações já obtidas.
- [ ] Validar visual e desbloqueios no Windows real do piloto.

# Roadmap

## v0.6.0 Alpha.1 — Bloco 5: Frota e planejamento
- [x] Compra nova/usada, aluguel, venda, serviços, localização e modelo ativo em frota individual.
- [x] Varredura read-only dos `aircraft.cfg` Official e Community (títulos/variantes de pintura).
- [x] Despacho de voo, checklist, limite de bônus de realismo +18% no XP e BRL, congelamento de critérios na decolagem.
- [x] `.PLN` disponível offline (a partir da base do piloto) e comando SimConnect de carga em solo.
- [x] Ponte HTTP local read-only e desenho de rota próprio; protótipo **fonte** SDK da toolbar criado.
- [x] Testes de frota, economia, duplicidade, scanner e ponte; GUI e voo artificial ponta a ponta com reinício validados no ambiente de desenvolvimento.
- [ ] Validar novas SimVars (peso, vento e sim rate) no MSFS 2020 Steam real, além do bônus real e da varredura de aeronaves instaladas.
- [ ] Compilar o projeto-fonte no SDK; testar permissões do iframe/Coherent e a toolbar dentro do jogo.
- [ ] Provar se existe mecanismo suportado de alternar aeronave e criar voo no Mapa-Múndi; **não implementado nem prometido**.
- [ ] Integração de mapa VFR real, multiplayer e dados operacionais de aeroporto/clima automaticamente verificados.
- [ ] Disponibilizar comandos de carreira autenticados no painel do simulador quando a comunicação for validada.

Detalhes em [Bloco 5](BLOCO_5_FROTA_DESPACHO.md) e [Arquitetura in-game](ARQUITETURA_IN_GAME.md).

## v0.1 Alpha — entregue para validação no Windows
- [x] Aplicativo Windows Tkinter, modo Demo sem simulador.
- [x] Integração opcional SimConnect somente leitura com 8 SimVars (7 essenciais exibidas, 1 para estado de solo; mais 2 opcionais: combustível/estol).
- [x] Detector de voo por estado do solo, com anti-bounce e estimativa de razão vertical no toque.
- [x] Diário local persistente SQLite, uma carreira independente.
- [x] Três contratos iniciais em Pernambuco e Paraíba, com validação de origem e destino e recompensa única.
- [x] Inspetor somente leitura que faz cópia de common.db e extrai apenas estrutura SQLite.
- [x] Testes independentes de MSFS e ação CI.
- [x] Demo e conexão SimConnect ao MSFS 2020 confirmadas pelo piloto no Windows.
- [x] Inspeção do esquema real do NeoFly: relatório SQLite (54 tabelas, sem registros pessoais).

## v0.1.2 — falha de conexão em voo: patch entregue para validação física
- [x] Proteger a sessão de perdas pontuais de `GROUND_VELOCITY` / `VERTICAL_SPEED`.
- [x] Reconectar automaticamente em caso de queda persistente de SimConnect.
- [x] Checkpoint de missão/voo e retomada após reinício do app.
- [x] Pouso+crédito atômico sem recompensa duplicada; migração do SQLite anterior.
- [x] Rota SIPE → SIFC para teste rápido; testes automatizados e interface virtual aprovados.
- [x] Validar voo real SIPE → SIFC, pouso e crédito de $420 no MSFS 2020; saldo persistiu ao reabrir.
- [ ] Validar reconexão automática após queda real de SimConnect em voo.

## v0.1.3 — melhorias após teste físico
- Robustez de conexão e reconexão de SimConnect, frequência, dados nulos.
- Registro de múltiplos voos por sessão sem falso positivo em toques sucessivos.
- Atividade e logs de erro mais detalhados.
- Indicadores de combustível, aeronave, luzes, avisos de estol, arremetida.
- Refinamento de avaliação da aproximação e pouso para não incentivar comportamentos inseguros.

## v0.2.0-alpha.1 — Bloco 1: piloto e habilitações
- [x] Cadastro/edição de piloto virtual, indicativo e base ICAO.
- [x] Pontuação de XP atômica por voo concluído; requisitos e pré-requisitos de habilitações virtuais.
- [x] UI Meu piloto / Habilitações, migração aditiva de dados e testes automatizados.
- [ ] Validar UI e progressão no Windows real com o piloto.
- [ ] Alinhar requisitos realistas de cursos/provas antes de bloquear contratos e aeronaves.
- [x] Documentar escopo completo e opções futuras (falhas configuráveis, tráfego multiplayer, pinturas e companhias).

## v0.3.0-alpha.1 — Bloco 2: contratos e freelance
- [x] Nível do piloto derivado de XP, independente das habilitações; progressão balanceável.
- [x] Contratos com 9 tipos, restrições de nível, habilitação e horas.
- [x] Geração local por aeroportos do entorno; até 10 regionais + 3 freelancer, 1 origem ativa no banco, duração 1 dia UTC.
- [x] Base `airportsdata` MIT opcional via pip; fallback local e aviso ao piloto, sem usar dados do NeoFly.
- [x] Freelancer com aeronave designada pelo contratante, remuneração sem compra ou aluguel pelo piloto, experiência por modelo/família.
- [x] Validação de modelo na decolagem e no pouso; nenhuma recompensa se não houver confirmação.
- [x] Checkpoint de contrato dinâmico, pagamento único no SQLite e preservação de todos os registros antigos.
- [x] Tela de mercado e 49 testes automatizados + teste visual em ambiente virtual.
- [ ] Testar leitura TITLE do SimConnect e catalogação mundial no Windows/MSFS real.
- [ ] Mecânicas específicas de cada categoria (resgate, ambulância, passageiros, turismo, objetivos temporizados).
- [ ] Aeronaves fornecidas automaticamente por empresa/frota, e comprovação de propriedade, após gestão de frota e pesquisa SDK.
- [ ] Painel de toolbar in-game (requisito transversal).

## v0.2 — fundação de carreira
- Importação opcional de campos de progresso do NeoFly após estudo de compatibilidade; nunca sobrescrever original.
- Cadastro de aeronaves, manutenção, abastecimento e seguro.
- Missões geradas a partir de catálogo licenciado de aeroportos, objetivos e regras realistas.
- Contratos diferenciados: turismo, carga, táxi aéreo.
- Progressão financeira, habilitações e reputação.

## v0.3+
- Histórias de voos e eventos narrativos originais.
- Companhia aérea, equipe, frota, empresas e contratos extensos.
- Pacote de instalação Windows em exe assinado, quando a arquitetura for estabilizada.

## Requisito prioritário: interface dentro do MSFS 2020
- [ ] Painel de toolbar dentro do simulador para mapa, contratos, diário de bordo e frota; sem Alt+Tab.
- [ ] Ponte local testada e package Community. Veja [arquitetura in-game](ARQUITETURA_IN_GAME.md).

Escopo completo em [ESCOPO_CARREIRA.md](ESCOPO_CARREIRA.md).

## v0.4.0 Alpha.2 — Bloco 3: carreiras e companhias
- [x] Modalidade autônomo por padrão, com migração de banco sem alterar dados.
- [x] Vagas semanais simuladas, requisitos e candidaturas com resultado estável após semana seguinte.
- [x] Emprego, demissão e trechos exclusivos da companhia, com confirmação de modelo em decolagem/pouso.
- [x] Registro de companhia própria no endgame (gestão de frota IA futura).
- [x] Exportar plano VFR XML .PLN com opção de solicitar carga SimConnect em solo.
- [ ] Testar voo/planejamento `.PLN` e atualização visual do mapa VFR no MSFS 2020 real.
- [ ] Troca segura da aeronave por voo salvo/template autorizado, sem alterar voos em andamento.
- [ ] Ler modelos/liveries instalados localmente; gerenciar frota IA com identidade das companhias.
- [ ] Integrar interface na toolbar sem Alt+Tab e implantar sistema trabalhista/folha/salário realista.
- [ ] Gestão completa da própria empresa: frota, pilotos IA, bases, manutenção, rotas e lucro.

Consulte [Bloco 3](BLOCO_3_CARREIRAS.md).

## v0.5.0 Alpha.1 — economia/finanças/manutenção
- [x] Moeda do jogo em R$, conservando numericamente as unidades legadas e saldo atual.
- [x] Oferta regional e freelancer rebalanceada, distância compatível com nível inicial e remuneração ~R$1.500 por 20 min.
- [x] Extrato persistente, custos futuros de combustível e operação, imposto fictício opcional.
- [x] Hangar: C152 inicial uma vez, compra, desgaste, manutenção e seguro virtual.
- [x] Financiamento fictício com custo fixo de 8%, parcelas e proteção contra saldo insuficiente.
- [x] Migração/backups, pagamentos idempotentes e regressão automatizada.
- [ ] Validar v0.5 no MSFS 2020 real, principalmente identificação do C152 e leitura do combustível.
- [ ] Concluir cobertura de sinistros, abastecimento/serviços no MSFS, depreciação, aluguel e economia por aeroporto.
- [ ] Injetor de falhas opcional (configuração persistida; funcionalidade ainda não implementada).
- [ ] Painel integrado in-game MSFS 2020 sem Alt+Tab (requisito central mantido).

## v0.6.1 — hotfix localização + combustível (em validação física)
- [x] Corrigir posição de starter, aeronaves alugadas e voos livres; reconstituir último destino conhecido com critério conservador.
- [x] Inventário de combustível SQLite por aeronave, monitoramento de consumo e comandos de escrita SimConnect limitados aos tanques reconhecidos.
- [x] Abastecimento comprado em R$, sem custo de combustível duplicado no pouso sob controle do addon.
- [x] Toggle combustível controlado (padrão ON); OFF penaliza 30% recompensa e XP, decisão congelada no início do voo.
- [x] Regressões e testes de lógica SimConnect simulada; testes de interface.
- [ ] Validar escrita de tanques do Cessna 152 **no MSFS Steam real**, inclusive menu de combustível e desligamento do controle.
- [ ] Validar retroposição SBRF → SNAE no banco existente do piloto e persistência em Windows real.
- [ ] Ampliar suporte a complexos sistemas de combustível de addons sem injetar dados em tanques não identificados.

## v0.7.5 — Segurança e freelancer Nordeste
- [x] SimVars opcionais de luzes, assistências de decolagem/pouso, controle por IA, relógio UTC Zulu e G.
- [x] XP operacional atômico com bônus de toque suave e continuidade de missão após arremetida.
- [x] Freelancer em recorte geográfico Nordeste com alcance por aeronave e 6 ofertas; menu com aba Regional/Freelancer.
- [ ] Homologar sensores no C152/aviação complexa no MSFS 2020 físico.
- [ ] Melhorar identificação de taxiway/runway para pontuação precisa de velocidade antes e depois do pouso.
- [ ] Verificar preset de clima ao vivo e assistências gerais somente quando API oficial pública disponível.

## v0.7.6 — Navegação de contrato, rumo e classificação do táxi
- [x] Mercado único no sidebar, com abas Regionais e Freelancer.
- [x] Detalhes com cards, mapa interativo MapLibre reutilizado e ETA pela aeronave.
- [x] Proa magnética do cockpit + proa verdadeira do mapa, sem offset arbitrário.
- [x] Conexão automática ao MSFS com mecanismo de reconexão existente.
- [x] Clima real sem opção ou bônus não verificável; manter migração de planos.
- [x] Classificação conservadora com ON ANY RUNWAY, heading/aceleração e monitor pós-pouso.
- [ ] Homologar fisicamente em pistas e táxis do MSFS 2020; confirmar suporte a ON ANY RUNWAY nos cenários personalizados.
- [ ] Completar planejamento e aceitações integralmente em páginas nativas WebView2, eliminando telas Tk legadas.

## v0.7.7 — Persistência e manifesto
- [x] Combustível salvo por exemplar sem consumir dias de intervalo offline, revisão preservada no SQLite.
- [x] Alertas visuais/log de 20%.
- [x] Abastecimento em popup com litros, compra/devolução, trava MTOW e estorno.
- [x] Manifestos persistentes e automação de payload por estações, confirmação por telemetria.
- [x] Bônus de peso no pagamento/XP, sem dupla liquidação do voo.
- [x] NOAA prioritário por padrão no destino.
- [x] Facilities do MSFS por ICAO com proveniência; sem declarar coordenadas externas como oficiais.
- [ ] Homologar gravação/retorno de payload, combustível e Facilities no MSFS 2020 Windows.
- [ ] Mensagens 2D nativas dentro do simulador, sem afetar UI externa.
- [ ] Aprovação do ícone principal antes de atualizar .ico e empacotamento.

## v0.7.8 — homologação dos aeroportos e plano VFR
- [x] SimConnect_RequestFacilitiesList com paginação para aeroportos da sessão atual.
- [x] Nenhum aeroporto fora do MSFS nas ofertas, coordenadas ou aceites.
- [x] Sem dependência airportsdata no executável Windows.
- [x] Abastecimento aceita JSON numérico com autenticação.
- [x] Progresso do plano especifica envio ATC, sem fingir sincronismo dos aviônicos.
- [x] Aplicado ícone principal aprovado no build.
- [ ] Validar pacote de facilities no MSFS 2020 real.
- [ ] Explorar via SDK WASM/Coherent ou integração específica de aviônicos, sem prometer carregamento universal de GPS/VFR.

## v0.8.0 — Bloco 1: Frota / Hangar Midnight
- [x] Oficializar a base v0.7.8.2 homologada em simulador real na main.
- [x] Tela própria com lista de aeronaves adquiridas, visualização central e painel lateral de operações.
- [x] Ocultar aluguéis, freelancer e aeronaves de empresas na Frota do piloto.
- [x] Foto exclusiva por exemplar, SQLite no save da carreira, Dashboard sincronizada e imagens sem distorção.
- [x] Selecionar aeronave ativa, abastecer e manutenção com confirmação/pagamento real via motor existente.
- [ ] Homologar visual e foto personalizada no Windows real.
- [ ] Bloco futuro: Loja/Aluguel de aeronaves em página independente, sem misturar com Frota.

## v0.8.1 — Mercado de Aeronaves e SimConnect
- [x] Validar Frota e fotos no Windows real; mesclar v0.8.0 à main (PR #14).
- [x] Nova página de aeronaves separada do Mercado Regional (contratos) e da Frota (aeronaves próprias).
- [x] Quatro abas Novas / Usadas / Aluguel / Vender, cotação e confirmação no padrão Midnight.
- [x] Oferta semanal usada, tarifas por prazo, revalidação no backend e consistência do saldo, com bloqueio de compras remotas e voos.
- [x] Operações financeiras idempotentes com identificador de confirmação persistido e testado.
- [x] Registro de falha SimConnect apenas uma vez por período desconectado.
- [ ] Homologar v0.8.1 no Windows + MSFS real com compra, aluguel, venda e comportamento do log.
- [ ] Futuro: loja por aeroportos, modelos instalados, seguros individualizados e integração física de modelo no MSFS (dependente de API verificável).
