# Bloco visual 7 — Midnight Ops Premium (v0.6.3 Alpha.1)

Implementação sobre a base funcional v0.6.2, sem migração da economia.

## Layout e ergonomia
- Cabeçalho horizontal: marca, avatar local opcional, indicativo, país da base, patente virtual (derivada da habilitação conquistada), nível e XP, dinheiro, conexão, configurações e controles da janela.
- Sidebar: acesso aos módulos existentes; preparada para novos módulos.
- Coluna de mercado: até cinco contratos próximos, títulos, preços e previsão; resumo e progressão.
- Centro: contrato compacto, mapa esquemático, telemetria sem combustível, vento local quando existe, espaço METAR corretamente indicado como não integrado, log e bônus de realismo que podem ser editados pelo despacho.
- Coluna direita: aeronave, imagem ilustrativa de C152 mesclada ao painel, local, estado e combustível, toggle de combustível, abastecer, revisar e despachar/carregar VFR.
- Nada de scrollbar na página principal. Usar expansão proporcional com mínimos adequados. Testes de visualização em 1280×720, 1366×768, 1650×930, 1920×1080. Ao reduzir a altura, informação redundante pode ser recolhida, mas as ações essenciais ficam visíveis.

## Limites, segurança e integridade
- Ativar/desativar combustível continua sujeito às regras já existentes, e mantém penalidade de 30% congelada na decolagem.
- País da base **não** implica nacionalidade legal do piloto: se não for encontrada correspondência no catálogo, usar marcador neutro.
- Emblema indica progresso virtual do jogo, não uma habilitação aeronáutica real.
- A foto é escolhida pelo usuário e fica apenas no diretório de dados da carreira. Não acompanha ZIP nem GitHub.
- Reputação não é inventada: barra permanece sem preenchimento até existir valor real no motor de carreira.
- Carta satélite/Google e METAR online requerem licença, integração, atualizações e testes; esta versão exibe claramente mapa esquemático/sem METAR remoto.
- Testes regressivos existentes e adicionais, nenhuma alteração do esquema SQLite.

## Próximos passos
1. Conferir em monitores Windows reais, incluindo escala DPI de 125/150%, e corrigir qualquer corte.
2. Padronizar estilos de frota, mercado e janelas modais no mesmo tema.
3. Mapa de provedor autorizado com licenciamento e linha de rota/posição, fonte alternativa offline, com adaptação para o painel in-game.
4. Fotos específicas de aeronaves de origem/licença verificadas, atlas local de aeroportos, METAR e indicadores de reputação real quando implementados.
