# FlightSimCarreira — v0.3.0 Alpha.1 (Bloco 2: contratos e freelancer)

**Nome provisório.** Aplicativo de carreira **original** para Microsoft Flight Simulator 2020, feito em Python 3.11 com interface Windows Tkinter e base de dados SQLite própria.

## Bloco 2 — Mercado regional e freelancer (NOVO)

O botão **Mercado regional / Freelancer** abre contratos gerados perto da posição atual do piloto (ou de sua base cadastrada se o MSFS estiver fechado). Uma nova lista é gerada por dia UTC e por origem, **sem gerar contratos para todos os aeroportos globais**. A lista atual tem no máximo **10 contratos regionais e 3 freelancers**. Contratos já concluídos não podem ser pagos novamente, mesmo depois de reiniciar. Cada novo voo continua registrado em SQLite.

**Tipos e nível mínimo inicial**: carga (1); turismo e passageiros (2); táxi aéreo (3); humanitária (4); transporte médico (6); executivo (8); resgate (10); operações especiais (12). Além de nível, algumas missões exigem habilitações PPA/PCA/IFR/PLA e horas voadas. O XP determina o nível, com progressão gradual; XP e habilitações anteriores permanecem. Esses níveis são balanceamento preliminar do jogo, não exigências regulatórias reais.

**Freelancer**: o contrato indica a **aeronave disponibilizada pelo contratante** (ex.: Cessna 152). O piloto recebe pagamento pelo serviço e não compra/aluga a aeronave dentro da economia do addon. **Nesta Alpha, ainda é necessário escolher esse avião no MSFS manualmente** antes da decolagem. O SimConnect tenta ler o título do modelo; para pagar um freelancer, o modelo precisa ser confirmado na decolagem e no pouso. Se o título estiver indisponível ou não corresponder, o voo é registrado, mas o contrato não é pago. Os contratos de avião avançado levam em conta experiência por família e, quando necessário, no modelo exato. A propriedade real da aeronave/tail number não é verificada ainda: isso virá com gestão de frota.

**Aeroportos globais:** `v0.3.0`0 usa a base MIT **airportsdata 2026.8.2**, instalada por `instalar_windows.bat`. O catálogo pode conter aeroportos que não existem na instalação atual do MSFS, portanto confirme os destinos no mapa do simulador antes de aceitar. Sem o pacote disponível, o programa preserva o catálogo local básico SBRF, SIPE, SIFC e SBJP e informa essa limitação. Nada é importado do banco do NeoFly para gerar missões.

**Como testar (voo curto):** abra MSFS 2020, coloque o Cessna 152 em **SIPE** no solo, abra o app e conecte SimConnect; cadastre o piloto em **Meu piloto / Habilitações**; clique **Mercado regional / Freelancer** e escolha uma proposta para SIFC. Missões regionais exigem decolagem na origem e pouso dentro de 3 NM do destino; freelancing exige também o modelo designado. Se um contrato antigo estiver ativo, cancele antes de aceitar outro. A demo fixa continua separada, com a rota SBRF→SIPE.

**O que ainda não está pronto:** estas são categorias de contrato com geração, progressão, aeronave e pagamento. Mecânicas específicas (busca de vítimas, embarque de passageiros, objetivos turísticos, urgência médica, reputação e carga/peso) virão nos próximos subblocos. O addon ainda não altera a aeronave no MSFS, não usa inventário próprio de frota e não tem interface in-game nesta versão. As opções independentes de provas e falhas estão aprovadas no escopo, mas seus controles de configuração ainda serão implementados.

Mais detalhes: [Bloco 2](docs/BLOCO_2_CONTRATOS.md) e [Escopo aprovado](docs/ESCOPO_CARREIRA.md).

### Bloco 1 agora disponível

Use **Meu piloto / Habilitações** no topo do programa para cadastrar nome do piloto, indicativo e base ICAO. A partir daí o painel mostra voos, horas, XP e uma trilha de habilitações **virtuais**, com pré-requisitos de XP e quantidade de voos. A habilitação inicial PPA é concedida no cadastro; as seguintes são conquistadas conforme os requisitos provisórios. Não são documentos aeronáuticos reais.

Ao criar o piloto, o aplicativo **não reseta saldo nem histórico** do banco existente em `%APPDATA%\AeroCarreira-Lab\carreira.db`. Voos anteriores contam nas estatísticas, sem gerar XP retroativo. **Novos** voos após criar o piloto geram 25 XP ao pousar e mais 15 XP se o contrato pagar recompensa, tudo na mesma transação e com proteção contra duplicação. O cadastro é **um piloto por carreira** nesta versão; sua edição não reinicia a carreira. As novas missões do Bloco 2 aplicam os requisitos de nível, habilitações e experiência.

Detalhes e requisitos futuros: [Escopo aprovado](docs/ESCOPO_CARREIRA.md).

Dois objetivos em paralelo:

1. **SimConnect em modo somente leitura:** painel de telemetria, detecção inicial de decolagem e pouso, diário de bordo e contratos simples de carga.
2. **NeoFly 4:** estudar **cópia** dos possíveis arquivos `common.db` ou `std.bin`, sem modificar dados originais, para avaliar importação de progresso numa versão posterior.

Não é uma modificação do NeoFly; não copia sua implementação nem reproduz o código proprietário. Não é software aeronáutico para voo real.

## v0.4.0 Alpha.1 — Bloco 3: modalidades de carreira e plano VFR

- Todos começam **autônomos**. Novo botão **Vagas e companhias** na tela principal e no mercado.
- São geradas no máximo quatro **vagas semanais fictícias**, com empresas de referência AeroNordeste, Azul, GOL e LATAM. As oportunidades **não são vagas reais**, e as empresas não são afiliadas ao projeto.
- Candidatura limitada a **uma por semana**: acompanha os requisitos de nível, horas e habilitações. O resultado só é revelado a partir da semana seguinte, quando clicar **Ver resultado / atualizar**. Resultado estável, sem reroll por reinício.
- Se contratado, o piloto pode acessar **até dois trechos da empresa por dia no mercado regional**, usando o avião designado (selecionado manualmente no simulador). Pode pedir demissão e voltar ao autônomo. Nenhum salário periódico é pago automaticamente; os valores apresentados são referências, com pagamentos por trechos concluídos.
- **Endgame:** registro inicial de companhia aérea própria a partir do nível 18, 25 h, PLA e $100.000 de investimento. **Ainda não** existe gestão de frota, IA e lucro corporativo.
- **Plano VFR:** aceitar contrato e clicar **Preparar plano VFR da missão**. Gera `.PLN` em `%APPDATA%\AeroCarreira-Lab\planos_vfr`. Com avião **em solo** e MSFS conectado, podes solicitar o carregamento pela API `SimConnect_FlightPlanLoad` com confirmação. Isso **não muda automaticamente o avião ou posição**, e a atualização do VFR/GPS precisa ser validada no MSFS 2020 real. Não clicar em pleno voo.
- O banco próprio passa por migração aditiva, preservando saldos, voos, XP, ofertas e checkpoint. **Se estiver voando na versão anterior, termina o voo antes de atualizar.**
- Consulte [Bloco 3 — documentação técnica](docs/BLOCO_3_CARREIRAS.md) e [roadmap](docs/ROADMAP.md).

### Testar sem perder progresso

1. Fecha o aplicativo antigo depois de pousar e concluir a missão; **não apagues** `%APPDATA%\AeroCarreira-Lab\carreira.db`.
2. Extrai o ZIP em pasta nova, executa `instalar_windows.bat` e `iniciar_windows.bat`.
3. Confere teu piloto, saldo e histórico. Abre **Vagas e companhias**. Vagas de níveis altos aparecem bloqueadas por requisitos, mas são apenas simulação.
4. Para testar `.PLN`, aceita contrato local, usa **Preparar plano VFR da missão**, confirma a carga **somente em solo**, abre o mapa VFR e vê se a rota apareceu. Se não aparecer, anota o log e verifica se a importação manual do `.PLN` funciona.
5. Para contratar, é necessário cumprir os requisitos e aguardar o próximo período semanal do simulador de carreira. Não antecipar relógio do sistema apenas para testar.

## Rodar no Windows (primeiro a demo)

Requisitos: **Windows 10/11**, **Python 3.11 de 64 bits** instalado, com Tkinter (Python oficial inclui Tkinter). MSFS 2020 é necessário apenas para conectar telemetria.

1. Extraia o ZIP em uma pasta como `Documentos\AeroCarreira-Lab`.
2. Execute `instalar_windows.bat`. Ele cria `.venv` e instala `SimConnect` e `airportsdata`; é preciso Internet na primeira instalação.
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

**Limitações:** A conexão SimConnect e o pouso real foram validados pelo piloto na v0.1.2; o novo leitor de TITLE e o mercado mundial ainda requerem teste físico. A captura da razão vertical é a **última leitura aérea antes do toque**, uma estimativa que pode diferir de sistemas de avaliação de pouso; não se deve interpretá-la como medição certificada. O intervalo de leitura de 0,4s pode perder o toque exato. O catálogo pode listar aeroportos não presentes no simulador; o modo local de contingência inclui SBRF, SIPE, SIFC e SBJP.

### NeoFly — localizar e analisar sem risco

**Atualização após teste físico:** modo demo, conexão ao MSFS e voo real SIPE → SIFC foram validados pelo piloto. Foi recebido e documentado um relatório com a estrutura SQLite do NeoFly; a importação de registros ainda não foi implementada.

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
py -3.11 -m aerocarreira --inspect-neofly "C:\CAMINHO\PARA\std.bin" --output "$env:TEMP\neofly-inspecao"
```

**Compartilhe somente o relatório `neofly_schema_report.json`.** Não publique `common.db`, `std.bin`, a cópia nem arquivos pessoais no GitHub. O repositório informado está público neste momento. O aplicativo não envia dados para GitHub por conta própria.

## v0.1.2 — voo real com recuperação automática

**Por que atualizamos:** no primeiro voo MSFS SBRF → SIPE o leitor parou após
`SimVar sem resposta: GROUND_VELOCITY`

O FlightSimCarreira agora trata velocidade de solo/razão vertical ausentes como
telemetria **degradada**, exibindo `~` na velocidade estimada. Leituras críticas
faltantes são toleradas temporariamente, sem gerar amostras falsas. Persistindo a
falha, ele tenta reconectar automaticamente (o simulador pode ficar indisponível).

**Checkpoint**: durante voo conectado, registra missão e fase a cada ~2s,
na mesma base local. Reiniciar o aplicativo durante um voo **já monitorado por esta
versão** permite recuperar o estado em voo e continuar até o pouso. Um voo anterior
com v0.1.1, sem checkpoint, **não é recuperável automaticamente**. As recompensas
são lançadas junto do pouso numa só transação, com chave única por decolagem.

**Rota rápida nova:** `SIPE → SIFC`, aeroporto Coroa do Avião (Igarassu/PE),
aproximadamente 11,4 NM em linha reta, recompensa de teste `$420`. Referência de
localização: [AISWEB SIFC](https://aisweb.decea.mil.br/?codigo=SIFC&i=aerodromos).
É aeródromo privado na realidade; esta versão é **somente simulação**.
Confirme que `SIFC` está disponível no mapa do teu MSFS 2020 antes de decolar.
O pagamento exige decolagem perto de SIPE e pouso confirmado perto de SIFC.

**Teste recomendado no MSFS:**

1. Feche o FlightSimCarreira v0.1.1. Descompacte esta versão em pasta nova,
   instale/inicie normalmente. O saldo e o histórico antigos da pasta APPDATA
   são preservados e o SQLite recebe migração aditiva segura.
2. Posicione o avião em solo em **SIPE**. Clique **Conectar MSFS** e aguarde dados.
   Se aparecer um contrato antigo ativo, cancele antes de aceitar o novo.
3. Selecione a opção `SIPE → SIFC` e aceite o contrato **em solo**.
4. Decole e siga para SIFC. Se ocorrer uma falha transitória, o worker deve
   continuar; se a conexão cair, deve tentar reconectar sozinho. Não precisa
   clicar em 'Conectar MSFS' durante o voo.
5. Após pousar em SIFC e permanecer em solo por 2s, o app deve registrar o voo,
   acrescentar **$420** e remover o contrato. O botão **Salvar log** exporta
   diagnóstico local para conferir em caso de erro.
6. Para testar recuperação completa, feche o app **durante o voo**, abra de novo
   e reconecte: a missão e o status anterior devem permanecer. Faça isso apenas
   em um voo de teste, sem mexer no NeoFly.

**Limitação:** reconexão automática, inclusive com SimConnect genuinamente
encerrado, ainda depende de validação física no teu MSFS/Windows; testes
automatizados simulam amostras, reconexão e reinício, mas não o SDK real.
A interface in-game permanece no [roadmap](docs/ARQUITETURA_IN_GAME.md).

## Integração no cockpit (planejada)

A interface Windows é transitória: o requisito prioritário é operar todo o gameplay pelo painel in-game na toolbar do MSFS 2020. O mapa VFR e o multiplayer precisam de prova de conceito técnica; não afirmamos que o SDK permita reaproveitar o mapa nativo ou ler jogadores online diretamente. Veja [arquitetura](docs/ARQUITETURA_IN_GAME.md) e [escopo](docs/ESCOPO_CARREIRA.md).

## Onde os dados são salvos

`%APPDATA%\AeroCarreira-Lab\carreira.db`: banco **nosso**, separado da instalação NeoFly. O saldo inicial desta carreira é **$5.000 fictícios**; não reproduz o saldo real do NeoFly, que ainda não foi importado.

## Testes

```powershell
py -3.11 -m unittest discover -s tests -v
```

Os testes de regras, SQLite e simulação são independentes do MSFS e da biblioteca SimConnect. CI usa Linux e Windows com Python 3.11 e 3.13. Nenhum simulador real é necessário no CI.

## Arquitetura

- `aerocarreira/domain.py`: amostras, fases, contratos, distâncias e saldo.
- `aerocarreira/pilot.py`: requisitos e validação dos perfis/habilitações virtuais.
- `aerocarreira/storage.py`: base SQLite própria e diário de bordo.
- `aerocarreira/sim_adapter.py`: adaptador opcional Python-SimConnect, exclusivamente leitura.
- `aerocarreira/neo_inspect.py`: inspetor de banco NeoFly com cópia isolada.
- `aerocarreira/demo.py`: amostras artificiais para validar fluxo sem MSFS.
- `aerocarreira/app.py`: interface desktop.
- `aerocarreira/contracts.py`: níveis, elegibilidade, catálogo de aeroportos, propostas regionais e freelancer.

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
