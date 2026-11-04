# v0.7.3 Midnight Ops Alpha.1 — mapa, proa e contratos

## Correções

1. **Mapa ocupa toda a área:** o contêiner MapLibre fica visível antes de construir a tela WebGL, e `map.resize()` é chamado após o layout e quando as dimensões mudarem. Uma mudança da janela não pode congelar a largura do canvas na metade.
2. **Controles e atribuição:** botões +, − e centralização continuam na borda direita da área de mapa. Botão Satélite OFF/ON separado na borda inferior direita. Texto de crédito EOxCloudless/Sentinel‑2 2016 CC BY 4.0 na borda inferior esquerda acima da atribuição do mapa, sem cobrir ou ser coberto pelos botões. Foi eliminada a indicação incorreta de Google Satélite.
3. **Proa real:** coleta opcional `PLANE_HEADING_DEGREES_TRUE` pelo SimConnect, convertida de **radianos** para graus e normalizada a 0–359,9. A orientação do ícone independe do deslocamento; virar 015° no solo deve fazê-lo rotacionar para 015°. Se indisponível, o mapa pode conservar o último rumo ou inferir o deslocamento, sem declarar essa estimativa como proa real. Nada da leitura de heading afeta detecção de pouso, combustível ou pagamentos.
4. **Mercado no app:** os botões Missões e Contratos, Mercado Regional e Ver todas as missões abrem um modal com todas as ofertas efetivamente geradas para a região, com filtro Regional/Freelancer, pesquisa e exibição da aeronave fornecida pelo contratante. A confirmação de aceite acontece no próprio WebView; o backend revalida elegibilidade, contrato já pago, localização e solo através do motor preexistente. Não há janelas invisíveis do Tkinter para essas escolhas.

## Testes

- Suíte Python Windows/Linux em Python 3.11/3.13 e smoke `--verify-native-webview` no exe Windows.
- Navegador: seleção e filtros do mercado; rotação do SVG offline com heading 15° e 135° sem mudar posição.
- Teste controlado MapLibre: contêiner renderizado com largura real antes do canvas, `resize()` acionado na mudança de viewport, marcador girando sem movimento, créditos do satélite sem colisão.
- Capturas do layout 1280×720 até 2560×1440, escalas 100%, 125%, 150%.

**Homologação real pendente:** verificar proa do C152 com o MSFS ligado, renderização inteira do OpenFreeMap e imagens de satélite em diferentes níveis de zoom, além de rota/aceite real de freelance no Windows. Nenhum teste CI é prova de voo físico.

Instalar sempre extraindo o ZIP inteiro numa pasta limpa. Não apagar `%APPDATA%\AeroCarreira-Lab`. A v0.7.0 homologada permanece como referência de motor.
