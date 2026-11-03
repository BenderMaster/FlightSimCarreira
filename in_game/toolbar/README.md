# Painel experimental da toolbar — MSFS 2020 (SDK NECESSÁRIO)

**Não é um pacote pronto para instalar.** Este diretório contém apenas o projeto-fonte da primeira prova de conceito. O `FlightCare` servido por `http://127.0.0.1:8769` já é funcional em navegador. O wrapper do jogo exige o **SDK do MSFS 2020** para compilar o SPB e **teste físico no MSFS Steam**. O CI atual não compila nem simula o SDK.

1. No FlightSimCarreira Windows clique **Painel local (experimental)** e teste no navegador em `http://127.0.0.1:8769/`. O serviço só responde em loopback e é somente leitura.
2. Instale e habilite o SDK no MSFS 2020 (Developer Mode, Help / SDK Installer). Salve uma cópia deste projeto em uma pasta simples.
3. No **Project Editor** do MSFS abra `in_game/toolbar/package.xml`, selecione o package e verifique o tipo **SPB** e o grupo **Copy**.
4. Execute **Build All**. O resultado deve conter o SPB em `InGamePanels` e arquivos HTML/JS em `html_ui`. **Se o SDK apontar erros de schema, registre o log e não instale uma build quebrada.**
5. Coloque **somente o package compilado** na pasta Community do MSFS, **não** a pasta `PackageSources` nem `Build` inteira. Feche e reabra o MSFS e inicie um voo. Localize o painel na toolbar. Alguns templates aparecem com ícone genérico.
6. Se o painel exibir erro ou tela vazia, teste o endereço de loopback no navegador do Windows, confira o console Coherent do SDK e informe mensagens. O iframe/loopback pode ser bloqueado por política da versão do Coherent.

## Limitações nesta etapa

- Somente leitura: posição, status, contrato, saldo, esboço geométrico de rota. **Não é mapa VFR do simulador**, não exibe cartas, outros jogadores, pista, iluminação, radar ou dados de meteorologia certificados.
- A interface integrada ainda é **não validada**. Não modificar a toolbar global nem recursos de terceiros.
- Esta versão não altera o modelo da aeronave, não grava valores no SimConnect e não oferece botões que gastem dinheiro.
- Um painel completo com ações seguras de contratação, mapa licenciado e administração in-game será desenvolvido depois de validar o wrapper e a ponte local.

## Fontes técnicas consultadas

- SDK MSFS: InGamePanels e SimConnect (documentação Microsoft Flight Simulator).
- Exemplos públicos de projetos de toolbar, consultados para referência **estrutural**, sem incorporar recursos gráficos ou código desses addons: `diagonalization-lab/msfs-panel-notepad`, `bymaximus/msfs2020-toolbar-window-template`.
