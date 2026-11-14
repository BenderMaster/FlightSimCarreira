# FlightSim InGame v0.9.0 Alpha.4 — projeto SDK MSFS 2020

Este diretório é o **source** compilável do package Community, ainda **não**
um package com SPB, manifest.json e layout.json prontos. A compilação e a
visualização física na toolbar só podem ser homologadas com SDK/MSFS 2020.

## Compilar no MSFS

1. Extraia esta pasta em algum diretório no Windows, com `package.xml`,
   `PackageDefinitions/` e `PackageSources/` lado a lado.
2. Abra `FlightSim.exe` da versão **0.9.0** e confirme
   `http://127.0.0.1:8769/` no navegador do computador.
3. No MSFS Steam, habilite Developer Mode, instale o SDK em Help se necessário.
4. Na tela Project Editor, preencha `Default Creator Name = FlightSim`,
   `Default Company Name = flightsim` e defina `Content-Type = MISC` no
   Inspector do pacote (os grupos continuam com tipos `SPB` e `Copy`).
   Abra o Project Editor, abra `package.xml`, selecione `flightsimcarreira-panel`,
   confira os assets SPB e Copy e use **Build All**.
5. Copie **somente a pasta compilada** dentro de `Packages/` que contém
   `manifest.json`, `layout.json`, `InGamePanels/` e `html_ui/`
   para a Community correta (Tools > Virtual File System > Open Community Folder).
6. Reinicie o MSFS, inicie um voo, habilite o ícone FlightSim na toolbar e abra.

O painel usa um iframe local read-only em `127.0.0.1:8769`. O código
do simulador **não executa** o Python automaticamente. Se o iframe não
carregar no Coherent, compare com o navegador do Windows e envie os
erros de Debug > Console/Coherent. Não tente abrir CORS na aplicação principal.

Guia completo de aceitação e troubleshooting:
`docs/INGAME_V090_BUILD.md` na raiz do repositório.
