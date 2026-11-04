# v0.7.4 Midnight Ops Alpha.1 — Navegação por páginas e mercado

## Decisão de UX
A barra lateral é persistente. O conteúdo à direita é trocado por `navigate()`, sem lançar diálogos para navegação. Mercado Regional e Mercado Freelancer são dois destinos próprios e duas abas na área principal. O clique em uma proposta abre a página de detalhes; Voltar retorna ao mercado de origem. O Dashboard continua como visão geral.

A migração de ferramentas antigas é **incremental**: Frota, Planejamento, Piloto, Finanças, Companhias, Logbook, Relatórios e Configurações têm uma página de consulta que usa apenas informações do snapshot existente. Operações de edição que ainda pertencem a janelas Tk continuam acessíveis **somente por botão explicitamente rotulado**. Não vender isso como migração completa dos formulários. Priorizar portá-los para HTML nas próximas etapas.

## Mapa e direitos
- Fonte cartográfica: OpenFreeMap/OpenMapTiles/OpenStreetMap; MapLibre mantém os créditos nativos.
- Satélite: EOxCloudless 2016, licenciado CC BY 4.0; após ativação, o mapa exibe `© EOxCloudless 2016` e abre a atribuição integral no controle de créditos. A atribuição resumida também acompanha o tile nativo; a string legal integral fica disponível no mesmo mapa.
- Texto legal: EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016 & 2017).
- Controles não devem colidir: toggle no canto superior direito, zoom em coluna no meio à direita, atribuições na faixa inferior.
- Google Maps tem qualidade superior em muitas regiões, mas exige integração licenciada com chave e billing. Não acessar endpoints não oficiais nem embutir chave pessoal em código distribuído.

## Sem mudança no motor
Sem alteração dos módulos Python que comandam voo, pagamentos, persistência, contratação, combustível e SimConnect. Os mercados leem o mesmo `snapshot().offers` e enviam `offer(id)` ao mesmo controlador.

## Testes e limites
- Unitário: contrato de DOM e página sem diálogo antigo.
- Browser: mercados em abas + navegação, detalhes/voltar, planejador, Dashboard persistente, orientação do marcador, HUD de satélite, 15 tamanhos/escalas e carregamento com MapLibre fake.
- CI Windows/Linux + executável e assets; **passar CI não significa homologar MSFS real**.
- Pendência: migrar formulários de edição Tk para painéis integrados um a um, cobrindo mutações com testes; ampliar testes visuais de páginas não-Dashboard.
