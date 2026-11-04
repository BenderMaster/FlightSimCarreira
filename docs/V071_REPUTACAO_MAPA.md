# FlightSimCarreira v0.7.1 Midnight Ops Alpha.1 — mapa e reputação

Base funcional: 0.7.0 Midnight Ops WebView sobre o motor sólido da v0.6.1. A interface aprovada, SQLite, SimConnect, combustível, pagamentos, XP e contratos são preservados.

## Reputação virtual

A reputação aparece no Resumo da Carreira em escala de 0 a 100, com faixa visual colorida. Começa em 50 (neutro) e é derivada exclusivamente do diário SQLite, inclusive voos anteriores: +1 por voo concluído, +2 por contrato pago, -6 por alerta de estol (limitado a quatro por voo), -2 para toque de 400–649 ft/min em módulo e -5 a partir de 650 ft/min. Pousos muito suaves não fornecem bônus adicional. Não existe ganho de XP ou dinheiro através da reputação.

Como a reputação é função determinística de voos já persistidos, a atualização **não cria tabelas novas, não modifica histórico e não repete recompensas**. Os eventos de pouso continuam sendo registrados uma vez pelo mecanismo de voo existente.

## Google Satélite — integração oficial e controles

Esta versão substitui a camada NASA Blue Marble pelo **Google Maps JavaScript API** quando o piloto configura uma chave válida. A API mostra satélite real, trajetória do contrato, aeroporto de origem/destino e a aeronave em tempo real. A navegação possui **scroll para zoom**, **clique e arraste para deslocar**, botões +/− e reenquadramento. Quando a rota muda, a câmera enquadra automaticamente a nova missão; durante a atualização da telemetria **não recentraliza continuamente**, preservando zoom e movimentação definidos pelo jogador.

O marcador de avião é uma silhueta vetorial ciano inspirada na referência fornecida pelo piloto, com tamanho controlado e rotação aproximada pela direção inferida entre posições sucessivas (>25 m). Sem deslocamento suficiente, mantém a última orientação. Não afirma ler heading real: a v0.6.1 não disponibiliza tal campo no FlightSample.

### Configurar Google Maps

1. No Google Cloud Console, crie um projeto, habilite **Maps JavaScript API**, associe uma conta de faturamento e configure limites de uso.
2. Gere uma chave específica com **restrição de API ao Maps JavaScript API** e restrições de utilização apropriadas para origem local (o WebView abre em `http://127.0.0.1:PORTA`). Verifique no seu PC se a política de referenciador do Google aceita a restrição escolhida; não deixe uma chave aberta sem limites.
3. No Dashboard, clique no botão **⚙ dentro do mapa**, cole a chave e salve. Pode ser necessário reiniciar a janela para alterar uma chave já carregada.
4. Como alternativa, configure a variável de ambiente `FLIGHTSIM_GOOGLE_MAPS_API_KEY` antes de abrir o aplicativo.

A chave fica no SQLite local (ou variável de ambiente), **não** é enviada ao GitHub ou incluída no executável. Ela chega apenas ao WebView autenticado via loopback; como toda chave de API usada no navegador, pode ser vista nas requisições pelo próprio usuário do computador. Proteja-a com restrições e cotas. O Google recebe as coordenadas necessárias para desenhar o mapa, conforme os próprios termos. **A Google Maps Platform pode gerar cobranças por carregamento**, dependendo de uso e faturamento.

Sem chave, sem rede ou se a API for recusada, o dashboard usa um **mapa local de coordenadas com rota, zoom no scroll, arraste e silhueta vetorial**. Ele não utiliza tiles NASA. Não é carta aeronáutica certificada nem substitui navegação no MSFS.

Leituras do combustível, reconexão SimConnect, detecção de pouso e pagamento continuam inalteradas. O mapa Google não foi exercitado com uma chave faturável neste ambiente; validar fisicamente no Windows com a chave do piloto e testar fallback offline.

## Testes

- Testes de reputação para carreira nova, histórico existente, persistência, estol e pouso duro.
- Testes de apresentação para pontuação e estado vazio.
- Capturas do dashboard em cinco resoluções × três escalas.
- Teste no navegador de mapa offline com zoom por scroll, arraste e diálogo da chave.
- CI Windows/Linux e build Windows em GitHub Actions.

Status: **Alpha para homologação física**. Não declarar o Google Satélite validado sem chave real e MSFS em execução.
