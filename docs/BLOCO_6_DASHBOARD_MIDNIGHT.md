# Bloco 6 — Midnight Ops Dashboard / Fase 1 (v0.6.2 Alpha.1)

## Objetivo

Trocar a tela principal anterior por um **dashboard operacional em três colunas com sidebar**, fiel à linguagem Midnight/ciano aprovada com o piloto, **reutilizando exclusivamente dados, ações e validações existentes**. Não reescrever o motor de carreira, SimConnect, financiamento, telemetria ou banco.

## Recursos implementados

- Cabeçalho: FlightSimCarreira, indicativo, modalidade da carreira, nível e barra XP, saldo do banco em R$, status de conexão, configurações, minimizar e fechar.
- Navegação lateral preparada para outros módulos. Os módulos antigos continuam abrindo suas janelas, até sua migração.
- Mercado lateral: até cinco propostas **regionais elegíveis**, consultadas no mesmo cache/banco do mercado existente. Ao clicar, abre o mercado completo; **não aceita contrato sem interação de escolha**. Os dados não são buscados em aeroportos de todo o planeta.
- Resumo: voos, horas e habilitações da carreira.
- Centro: contrato atual, recompensa, bônus do despacho salvo, mapa **esquemático** com rota e posição via SimConnect, atalhos de mapa/rota/pistas/peso, telemetria ao vivo sem repetir combustível, METAR marcado explicitamente como indisponível, registro de voo e checklist já salvo. Critérios do bônus são editáveis na janela de despacho já existente **somente em solo**, que persiste e valida as opções.
- Painel de aeronave: dados da aeronave selecionada no banco, localização, conservação, combustível recebido pelo MSFS e controles de combustível, abastecimento e revisão. As transações chamam o mesmo motor de economia/manutenção, respeitando confirmação, saldo e estado do voo.
- Ações principais: despacho e solicitação de carregamento do plano VFR com as validações existentes.
- Logbook, análise segura e configurações permanecem acessíveis. Modo demonstração continua disponível por Configurações.
- Fotografia do modelo real **não foi incorporada** nesta fase; imagem do Cessna 152 é arte ilustrativa original, retirada da referência visual gerada para o projeto. Não afirmar que representa a aeronave real do usuário ou a pintura instalada no MSFS.

## Limitações honestas

- O mapa **ainda não é satélite, Google Maps, carta VFR ou fonte de navegação**. É apenas traçado geográfico esquemático para o contrato e posição recebida. Satélite/tiles precisarão de API, licença, atribuição, cache e alternativa offline.
- METAR por aeroporto, horário, vento no destino e condições do campo **não são automaticamente conhecidos** nesta etapa. Se houver vento local pela SimVar, ele é identificado como telemetria, não como METAR.
- As abas secundárias usam janelas Tkinter existentes; migração completa para páginas internas ocorrerá em fases posteriores.
- Sem painel compilado para toolbar, sem autoseleção de aeronaves no World Map, sem intercâmbio de fotografias/liveries de addons. A ponte local continua experimental e somente leitura.
- A interface adapta-se a resoluções maiores; há rolagem vertical em displays menores. Sem testes no MSFS Steam nesta entrega.
- Não foi criado ou alterado nenhum arquivo original do NeoFly.

## Testes

- `python -m unittest discover -s tests -v` — 119 testes.
- `python tests/gui_dashboard_smoke_manual.py` com ambiente gráfico Windows ou `xvfb-run` Linux — abrir, perfil, ofertas locais, mapa de contrato e Configurações/Logbook.
- Smoke gráfico sob Xvfb com captura da janela na resolução 1920×1080.
- Testes manuais necessários: resolução Windows, uso com voo ativo, dados do MSFS via SimConnect e botões de abastecimento/revisão com confirmação.

## Segurança e migração

Nenhuma nova tabela SQLite foi criada. Todos os dados preexistentes são lidos por meio dos mesmos objetos `Storage`, `Career`, `FuelManager` e `FlightTracker`. O pacote **não altera** saldo, aeronaves, XP ou habilitações na instalação. Recomenda-se terminar qualquer voo e manter backup de `%APPDATA%\AeroCarreira-Lab\carreira.db` antes de atualizar.

## Próximas fases

1. Mapa satélite opcional com provedor licenciado, atribuições e route overlay, sem usar mapas proprietários sem autorização.
2. METAR real com fonte externa/autorizada, indicação de idade dos dados e fallback offline.
3. Redesign completo de Mercado, Frota, Piloto, Finanças, Companhias em páginas do mesmo shell.
4. Sidebar e dashboard compartilhados com painel compilado e validado dentro do MSFS 2020.
