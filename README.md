# AeroCarreira Lab — v0.1.1 Alpha

**Nome provisório.** Aplicativo de carreira **original** para Microsoft Flight Simulator 2020, feito em Python 3.11 com interface Windows Tkinter e base de dados SQLite própria.

Dois objetivos em paralelo:

1. **SimConnect em modo somente leitura:** painel de telemetria, detecção inicial de decolagem e pouso, diário de bordo e contratos simples de carga.
2. **NeoFly 4:** estudar **cópia** dos possíveis arquivos `common.db` ou `std.bin`, sem modificar dados originais, para avaliar importação de progresso numa versão posterior.

Não é uma modificação do NeoFly; não copia sua implementação nem reproduz o código proprietário. Não é software aeronáutico para voo real.

## Rodar no Windows (primeiro a demo)

Requisitos: **Windows 10/11**, **Python 3.11 de 64 bits** instalado, com Tkinter (Python oficial inclui Tkinter). MSFS 2020 é necessário apenas para conectar telemetria.

1. Extraia o ZIP em uma pasta como `Documentos\AeroCarreira-Lab`.
2. Execute `instalar_windows.bat`. Ele cria `.venv` e instala adaptador opcional `SimConnect` do PyPI; é preciso Internet na primeira instalação.
3. Execute `iniciar_windows.bat`.
4. Clique **Demo sem MSFS**, selecione `SBRF → SIPE`, e clique **Aceitar contrato**.
5. Clique **Avançar demo** até pousar em Itapessoca. Deve receber **$850**, registrar voo e incrementar saldo de $5.000 para $5.850.

Se o adaptador SimConnect não instalar, a interface Demo e o inspetor NeoFly continuam funcionando usando apenas a biblioteca padrão Python: `py -3.11 -m aerocarreira`.

### Conexão ao simulador

1. Inicie **MSFS 2020** e entre num voo com o Cessna 152 em SBRF.
2. Abra AeroCarreira e clique **Conectar MSFS**.
3. Os 7 campos essenciais de telemetria devem atualizar. Combustível e aviso de estol são opcionais. Se houver erro, envie o texto do painel para diagnóstico.
4. Aceite contrato na origem, **em solo**, e voe até o destino. O avaliador decola/pousa apenas quando vê mudanças coerentes de `SIM ON GROUND`.
5. A recompensa é paga só depois de um pouso confirmado no aeródromo de destino, dentro de **3 NM** do seu ponto de referência.

**Limitações:** Não foi possível testar o SimConnect com o MSFS real neste ambiente. A captura da razão vertical é a **última leitura aérea antes do toque**, uma estimativa que pode diferir de sistemas de avaliação de pouso; não se deve interpretá-la como medição certificada. O intervalo de leitura de 0,4s pode perder o toque exato. Não existe missão completa para todas as aeronaves ou aeroportos. Os aeroportos incluídos são somente SBRF, SIPE e SBJP.

### NeoFly — localizar e analisar sem risco

**Atualização após teste físico:** demo e conexão ao MSFS 2020 foram confirmadas no Windows pelo piloto. O banco NeoFly ainda não foi localizado.

O arquivo varia conforme a versão/instalação do NeoFly:

- `C:\ProgramData\NeoFly\common.db` — caminho da [FAQ oficial](https://www.neofly.net/faq); `ProgramData` é oculto.
- `%LOCALAPPDATA%\Programs\NeoFly\std.bin` — relatado em instalações do NeoFly 4; **não assumimos que seja SQLite**.
- Se o NeoFly foi extraído de um ZIP para uma pasta personalizada, o arquivo pode estar lá.

**Localização automática (novo):** clique **Localizar arquivos NeoFly** no aplicativo. O programa procura os nomes conhecidos em pastas usuais, sem varrer o disco inteiro e sem abrir nem alterar o arquivo. Se encontrar um candidato, ele informa o caminho completo.

Também é possível executar no PowerShell na pasta do projeto:

```powershell
py -3.11 -m aerocarreira --find-neofly
```

Ou procurar manualmente colando `%ProgramData%\NeoFly` e `%LOCALAPPDATA%\Programs\NeoFly` na barra do Explorador do Windows.

**Analisar com segurança:**

1. Feche totalmente o NeoFly antes de copiar ou analisar.
2. No AeroCarreira, clique **Analisar common.db / std.bin** e selecione o arquivo encontrado.
3. O programa cria uma **cópia isolada** em `%APPDATA%\AeroCarreira-Lab\neofly_analise\neofly_copia_local.db`.
4. Caso a cópia tenha formato SQLite reconhecível, exporta apenas **nomes de tabelas, colunas e tipos** para `neofly_schema_report.json`; nenhuma linha de dados pessoal é exportada.
5. Se não for SQLite, identifica `desconhecido` e para, sem tentar extrair ou decifrar conteúdo. Isso não significa que a carreira não possa ser importada por outro meio autorizado no futuro.

Linha de comando para inspecionar o **arquivo que tu realmente encontrou**:

```powershell
py -3.11 -m aerocarreira --inspect-neofly "C:\CAMINHO\PARA\std.bin" --output "%TEMP%\neofly-inspecao"
```

**Compartilhe somente o relatório `neofly_schema_report.json`.** Não publique `common.db`, `std.bin`, a cópia nem arquivos pessoais no GitHub. O repositório informado está público neste momento. O aplicativo não envia dados para GitHub por conta própria.

## Onde os dados são salvos

`%APPDATA%\AeroCarreira-Lab\carreira.db`: banco **nosso**, separado da instalação NeoFly. O saldo inicial desta carreira é **$5.000 fictícios**; não reproduz o saldo real do NeoFly, que ainda não foi importado.

## Testes

```powershell
py -3.11 -m unittest discover -s tests -v
```

Os testes de regras, SQLite e simulação são independentes do MSFS e da biblioteca SimConnect. CI usa Linux e Windows com Python 3.11 e 3.13. Nenhum simulador real é necessário no CI.

## Arquitetura

- `aerocarreira/domain.py`: amostras, fases, contratos, distâncias e saldo.
- `aerocarreira/storage.py`: base SQLite própria e diário de bordo.
- `aerocarreira/sim_adapter.py`: adaptador opcional Python-SimConnect, exclusivamente leitura.
- `aerocarreira/neo_inspect.py`: inspetor de banco NeoFly com cópia isolada.
- `aerocarreira/demo.py`: amostras artificiais para validar fluxo sem MSFS.
- `aerocarreira/app.py`: interface desktop.

## Licenciamento e separação

- Nosso código nesta entrega é desenvolvido de modo independente, sem código NeoFly.
- A biblioteca de terceiros `Python-SimConnect` é opcional e distribuída separadamente pelo PyPI. Sua licença (AGPL-3.0 na implementação de referência) deve ser avaliada antes de distribuir um software proprietário; o adaptador foi isolado para eventual substituição pelo cliente oficial C# da Microsoft ou outro cliente de licença adequada.
- **Não incluímos binários do SDK Microsoft, arquivos do NeoFly ou dados do usuário.**

## Links de referência

- [SimConnect oficial Microsoft](https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/SimConnect_SDK.htm)
- [NeoFly FAQ: localização common.db](https://www.neofly.net/faq)
- [Python-SimConnect — projeto de referência](https://github.com/odwdinc/Python-SimConnect)
- [AISWEB: SBRF](https://aisweb.decea.mil.br/?codigo=SBRF&i=aerodromos)
- [AISWEB eAIP: SBJP](https://aisweb.decea.mil.br/eaip/A%2020-2026_2026_10_29/eAIP/AD%202%20SBJP-pt-BR.html)
- [ANAC: Itapessoca SIPE](https://pergamum.anac.gov.br/arquivos/PA2013-2126.pdf)
