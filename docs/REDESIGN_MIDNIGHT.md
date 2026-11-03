# FlightSimCarreira — direção visual aprovada: Midnight Ops

## Decisão do piloto (03/11/2026)
O piloto aprovou o mockup visual da tela principal (referência mostrada na conversa). **Não é uma tela já implementada.** Este documento preserva o escopo para implementação incremental.

## Identidade visual
- Tema escuro e sofisticado de central de operações aeronáuticas.
- Fundo azul-marinho quase preto, cartões azul petróleo, contornos discretos e detalhes em ciano elétrico.
- Âmbar/dourado para valores relevantes e alertas moderados; verde para estados confirmados; vermelho apenas para falhas críticas.
- Tipografia legível, microinterações discretas, ícones consistentes; evitar aparência de Tkinter padrão.
- Responsividade para janela Windows e futuro painel EFB na toolbar MSFS 2020.

## Estrutura-base aprovada
1. **Cabeçalho**: FlightSimCarreira, perfil/indicativo, nível e barra de XP, saldo em R$, estado do SimConnect.
2. **Sidebar**: Dashboard; Missões e Contratos; Mercado Regional; Frota/Hangar; Planejamento de Voo; Meu Piloto; Finanças; Companhias; Logbook; Análises; Configurações.
3. **Coluna de mercado**: ofertas próximas, categoria e remuneração, filtros, resumo de carreira.
4. **Centro principal**: missão ativa, rota/mapa dominante, METAR/clima e consulta de pistas, iluminação, peso e balanceamento; telemetria ao vivo; log e bônus.
5. **Painel da direita**: aeronave ativa, localização, estado, combustível virtual/controlado, abastecimento, manutenção e despacho.
6. **Tela cheia por módulo**: mercado, frota, carreira, finanças e logbook, preservando navegação consistente; interface não pode depender de abrir diversas janelas do Windows.
7. **In-game**: mesma linguagem de interface ao migrar para toolbar; primeiro validar ponte local/autorização e compatibilidade com MSFS.

## Regras de implementação
- **NÃO substituir o motor financeiro/telemetria/voos apenas para redesenhar**; preservar APIs e migrações SQLite.
- Fazer em etapas testadas: (A) design tokens e componentes reutilizáveis + shell, (B) dashboard e telemetria, (C) mercado/contratos, (D) frota/finanças/piloto, (E) painel in-game.
- Manter comparação com dados reais do app; valores e mapas do mockup são *ilustrativos*, não dados aeronáuticos certificados nem aeroportos garantidos.
- Não usar imagens, mapas, pinturas, fotografias ou marcas de terceiros sem licença/permissão e atribuição.
- Testes automatizados para cada recurso, smoke tests Windows, sem regredir decolagem/pouso, economia, combustível, SimConnect, checkpoint nem progressão.
- Confirmar ergonomia com screenshots reais e feedback do piloto antes de remover interface antiga; opcionalmente preservar modo clássico durante a migração.
- Atualizar README, CHANGELOG, testes e GitHub a cada versão.
