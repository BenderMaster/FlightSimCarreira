# FlightSim v0.9.0 InGame Alpha.1 — build e homologação no MSFS 2020

**Estado:** projeto-fonte de Community para compilar no SDK MSFS 2020; **não é pacote SPB pronto**. O SDK e o MSFS real não estão disponíveis nos runners do GitHub Actions. A branch de testes é separada da main v0.8.7.

## Downloads no Actions

Na execução da branch `feature/v0.9.0-ingame-foundation`, baixe **dois artifacts**:

1. `FlightSim-0.9.0-ingame-alpha1-Windows`: extraia o aplicativo completo em uma **pasta nova** e abra `FlightSim.exe`.
2. `FlightSim-InGame-0.9.0-SDK-Source`: contém o projeto-fonte SDK (`package.xml`, `PackageDefinitions`, `PackageSources`) e **precisa ser compilado** no MSFS.

Não coloque o ZIP do SDK, o diretório `PackageSources` ou os arquivos `.py` diretamente na Community. O artefato de source não substitui o pacote final do MSFS.

## Compilar no PC Windows com MSFS 2020 Steam

1. Faça backup de `%APPDATA%\AeroCarreira-Lab\carreira.db` e, se usar múltiplos pilotos, dos bancos de perfis. **Não é necessário apagar o banco atual.**
2. Extraia o ZIP Windows inteiro em uma pasta nova, sem substituir arquivos da v0.8.7. Execute `FlightSim.exe` e conecte ao MSFS. A interface Windows permanece normal.
3. Com o FlightSim aberto, teste `http://127.0.0.1:8769/` no navegador do PC. Deve exibir **FlightSim InGame 0.9.0**, telemetria e saldo. Verifique `http://127.0.0.1:8769/api/v1/health`: o campo `read_only` deve ser `true`. Se o serviço não abrir, confira o log do FlightSim, firewall local e se outra aplicação está usando a porta 8769.
4. Ative **Developer Mode** nas opções gerais do MSFS 2020. Na barra superior de desenvolvimento, menu **Help > SDK Installer** se o SDK não estiver instalado; siga a versão compatível com seu MSFS.
5. Extraia o artifact **FlightSim-InGame-0.9.0-SDK-Source** em `C:\FlightSim-InGame-v090` (qualquer pasta sem permissão restrita). Confira que `package.xml` aparece **na raiz** da pasta extraída, ao lado de `PackageDefinitions` e `PackageSources`.
6. No MSFS, abra **Project Editor**. Selecione **Open Project** e aponte para `C:\FlightSim-InGame-v090\package.xml`. Selecione o pacote `flightsimcarreira-panel`. Verifique que aparecem os grupos de assets **SPB** e **Copy**.
7. Use **Build All** (ou **Build Package**) e abra **Debug > Console** para conferir erros. O resultado esperado é uma pasta de package compilado sob `Packages`, contendo pelo menos `manifest.json`, `layout.json`, `InGamePanels\*.spb` e `html_ui\InGamePanels\FlightCare\...`. Se o compilador acusar erros, **não copie o build incompleto para a Community**; envie o log do Console para corrigirmos.
8. Para localizar a Community certa da instalação Steam: no Developer Mode, abra **Tools > Virtual File System**, expanda **Packages Folders** e clique **Open Community Folder**. É mais confiável que presumir um caminho de AppData.
9. Feche o MSFS. Copie **somente a pasta final compilada do package** (por exemplo `flightsimcarreira-panel`, com `manifest.json` e `layout.json` na raiz) para dentro da Community. Não coloque a pasta `Packages` inteira, `Build`, `_Temp` ou o projeto-fonte.
10. Abra novamente o MSFS, carregue um voo e abra a toolbar superior. Procure o botão FlightSim — se não aparecer, confira a personalização/itens ocultos da toolbar e o Content Manager. O FlightSim Windows deve permanecer aberto durante o teste.
11. Clique FlightSim. Deve surgir o painel Midnight compacto com os dados reais. Alterne **Completo/Compacto**, confira missão e mapa, compare velocidades/altitude com o cockpit e teste fechar/abrir o painel.

## Teste de aceitação da Alpha.1

- [ ] Ícone FlightSim aparece na toolbar sem conflitos com outros addons
- [ ] Painel abre e fecha, sem impedir interação com o avião
- [ ] Painel apresenta status SIMCONNECT ATIVO, aeronave e valores reais
- [ ] Ao desconectar o simulador, estado aparece como RECONECTANDO/DESCONECTADO
- [ ] Ao reconectar, dados novos aparecem sem reiniciar o MSFS
- [ ] O traçado de rota vem somente de aeroportos verificados no MSFS
- [ ] Modo completo mostra proa verdadeira e razão vertical
- [ ] Nenhum botão altera saldo ou contrato pela toolbar nesta Alpha
- [ ] FPS é comparado com o mesmo voo/cenário com painel fechado e aberto

## Diagnóstico se algo falhar

**Ícone não aparece:** capture a saída do SDK em Debug > Console, confirme que o SPB foi compilado e que `manifest.json`, `layout.json`, SVG da toolbar e os arquivos `FlightCare` aparecem no package instalado. Confirme a pasta Community pelo Virtual File System. Verifique se o painel está desabilitado na personalização da toolbar.

**Painel abre mas não carrega:** com o FlightSim Windows aberto, confira `http://127.0.0.1:8769/` em navegador comum. Se funcionar no navegador, o problema pode estar no iframe/Coherent: abra o Coherent Debugger do MSFS e capture mensagens de CSP, mixed-content, iframe ou rede. **Não desative autenticação/CSP do motor principal** para contornar o problema.

**Valores antigos ou sem dados:** confirme a conexão com MSFS na janela Windows e teste no navegador. O modo `Demo` é separado de telemetria real. Conferir log de conexão e título da aeronave. No console do painel, não publicar tokens, dados pessoais ou bancos SQLite.

**Package com erros de compilação:** envie print/texto integral do Console do SDK. Esta Alpha não afirma que o SPB já foi compilado e homologado: essa é justamente a validação física.

## Limites intencionais

- Read-only: comandos de contratos, pagamentos, frotas, planejamento e carreira **ficam para v0.9.1**.
- Um único motor Python/SQLite; o package Community só contém uma interface.
- API `/api/v1/status` utiliza chave efêmera gerada pelo motor e inserida apenas na página servida por loopback; nenhuma chave fixa no package. `/api/status` legado de diagnóstico permanece somente leitura por compatibilidade.
- Nenhuma integração garantida com o mapa VFR, GPS, multiplayer ou alterações de aeronave do simulador.
- O mapa leve é um esquema de coordenadas, **não** carta aeronáutica; a rotação segue proa real se a SimVar estiver disponível.
- Portal Coherent/iframe depende de aprovação física no MSFS 2020 Steam. Se bloqueado, será necessário um modo alternativo de apresentação empacotada, sem comprometer segurança.

## Fontes técnicas

- SDK Overview / Community: https://docs.flightsimulator.com/html/Introduction/SDK_Overview.htm
- Project Editor e Build All: https://docs.flightsimulator.com/html/Developer_Mode/Project_Editor/The_Project_Editor.htm
- SDK Project/Packages: https://docs.flightsimulator.com/html/Introduction/Using_The_SDK.htm
