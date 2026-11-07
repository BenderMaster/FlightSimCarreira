# FlightSim v0.8.6 — Logbook + Análises e Relatórios

**Status:** Logbook e Análises/Relatórios implementados na Alpha.1 e aguardando homologação. A parte de frota de companhias e habilitações de modelo permanece no escopo, mas **não está implementada nesta primeira Alpha**. Branch isolada `feature/v0.8.6-analytics-logbook`. A v0.8.5 Alpha.2 foi homologada e mesclada em `main` no commit `bb5dded9c4e7443347304de10985e80bccb01c69`.

## 1. Regras de companhias aéreas (catálogo fixado pelo piloto)

As frotas abaixo definem quais modelos podem aparecer como aeronaves de contratos da companhia. São **regras internas do FlightSim**, não um detector automático da frota real. Não mostrar “fictícia”, “simulação” ou variações nos nomes das empregadoras.

| Companhia | Frota autorizada na carreira |
|---|---|
| **Azul** | Airbus A320neo; A321neo; A321P2F (cargueiro); A330-200 (ceo); A330-900neo; Embraer E195/E1; E195-E2; ATR 72-600; Cessna 208B; Cessna 408 SkyCourier |
| **GOL** | Boeing 737-700; 737-800; 737 MAX 8; Airbus A330-900neo; **Airbus A320neo** (adição expressamente pedida para o jogo) |
| **LATAM** | Airbus A319-100; A320-200; **A320neo**; A321-200; A321neo; A321XLR; Boeing 767-300ER; 777-300ER; 787-8; 787-9 |
| **AeroNordeste** | Qualquer aeronave compatível com a operação e com a habilitação do piloto; porta de entrada |

A hierarquia de valorização solicitada é **Azul > GOL > LATAM > AeroNordeste**. Permanecem os quatro patamares salariais atuais (R$ 9 mil / R$ 17 mil / R$ 23 mil / R$ 30 mil), sem aumento geral: proposta de reatribuição Azul R$ 30 mil, GOL R$ 23 mil, LATAM R$ 17 mil, AeroNordeste R$ 9 mil, mais fatores atuais de nível, reputação e graduação. Os ciclos semanais continuam sendo de **7 dias reais**, com o sistema de compromissos de 0%/10%/20%, sem alterar o pagamento de contratos particulares.

### Habilitação para contratação e voo

1. Candidatura Azul/GOL/LATAM exige os pré-requisitos gerais de carreira **e ao menos uma habilitação de modelo de sua frota**. Não basta possuir um Cessna 152/172 nem apenas a licença genérica MLTE.
2. Introduzir um registro separado de habilitações de tipo/modelo por piloto (não confundir com licenças PPA/PCA/IFR/MLTE/PLA, que permanecem separadas). Cada habilitação será obtida por uma progressão verificável e persistida, nunca por simples seleção manual.
3. Contratos corporativos exibem **somente modelos** para os quais o piloto possui habilitação e que estejam disponíveis no ambiente MSFS. Validar o modelo da aeronave conectada via SimConnect antes do despacho e no encerramento. Não prometer que o MSFS possui um avião sem evidência.
4. AeroNordeste mantém catálogo livre, mas continua respeitando a progressão mínima e as habilitações necessárias ao modelo escolhido. Não usar um Cessna 152 nas rotas da GOL.
5. O backend deve validar elegibilidade na candidatura e na emissão/aceite da rota (não somente desativar botões no navegador). Incluir testes negativos explícitos para C152 em GOL, ausência de habilitação e tipo não suportado.
6. Criar caminho acessível para obtenção de habilitações sem exigir compra de aeronaves caras (por exemplo, prova de treinamento em aeronave disponibilizada), a validar no design antes de codificar a regra de aquisição. A economia não deve criar licença “gratuita” em segredo.

### Limitações identificadas na v0.8.5

- O catálogo atual `EMPLOYER_FLEET` só contém C152, C172, Baron G58, King Air 350i e Citation CJ4.
- GOL e LATAM atualmente geram contratos com CJ4; Azul, com King Air. Isso deve ser substituído pelo catálogo acima antes da homologação v0.8.6.
- As licenças atuais são apenas PPA/PCA/IFR/MLTE/PLA e **não representam** habilitação individual em Boeing, Airbus, Embraer ou ATR.
- Os nomes recebidos do MSFS podem variar entre variantes e addons. Normalizar aliases com testes e **rejeitar ambiguidades** em vez de atribuir habilitação equivocada.

## 2. Tela Análises e Relatórios

**Objetivo:** acompanhar evolução e eficiência da carreira, não duplicar o Logbook ou o centro financeiro.

- Painel superior: total de voos, horas, distância efetivamente medida, taxa de conclusão de contratos (quando houver dados verificáveis), média de toque (ft/min), total de XP recebido em voos e salário semanal liquidado.
- Filtros: **7 / 30 / 90 dias / toda a carreira**, modalidade (particular/regional/freelancer/emprego/empresa) e aeronave. Todos os indicadores respondem aos mesmos filtros.
- Gráficos: voos e horas ao longo dos meses; horas por modelo; perfil de pousos; distribuição entre voos particulares, contratados e empresariais; ganho líquido operacional por período e suas despesas por categoria; crescimento da reputação apenas se houver série histórica persistida.
- Seção "Comparar aeronaves": horas, número de voos, aterrissagens registradas, receitas/custos associados **quando a atribuição for confiável**.
- Resumo de carreira em números + períodos com melhor desempenho. Sem pontuação baseada em clima real não verificável.
- Contabilidade pessoal e empresarial **separadas**; salário de companhia entra no pessoal apenas quando efetivamente liquidado.
- Dados originados exclusivamente do SQLite do piloto ativo. Sem escrever em tabelas financeiras; não fabricar campos históricos ausentes.
- Gráficos responsivos em viewport Windows 1366×768 e 1920×1080, sem barras microscópicas.

## 3. Tela Logbook (diário de voo)

**Objetivo:** livro de voo persistente, consultável e auditável.

- Tabela cronológica: data/hora local e UTC, aeronave (modelo detectado), modalidade, partida/chegada, duração, pouso (ft/min), avisos de estol, contrato associado, remuneração pessoal e XP atribuído.
- Origem/destino ICAO só aparecem quando **realmente associados a registro salvo/verificado**. Voos legados só com latitude/longitude devem mostrar coordenadas ou “aeroporto não registrado”; não inventar ICAO com base em aproximação.
- Selecionar um voo abre ficha completa: horário, duração, coordenadas, modelo, identificador de contrato, tipo de operação e dados de toque/alertas efetivamente registrados.
- Filtrar por período, aeronave, empresa/modalidade e busca por contrato; ordenação recente/antiga; paginação para carreira longa.
- Campo editável **anotações pessoais** em tabela separada vinculada ao ID do voo; nunca alterar valores históricos de voo, XP ou finanças.
- Exportar CSV compatível com Excel com todos os registros do filtro (UTF-8 BOM e separador adequado para pt-BR). Exportação PDF pode ser etapa posterior, não pré-requisito do primeiro build.
- Mesmo banco de dados isolado por piloto. Migrações aditivas com backup e testes de idempotência; registro automático não gera segundo lançamento financeiro.
- Nova tela distinta de “REGISTRO DE VOO” do Dashboard, que atualmente só exibe mensagens técnicas recentes da sessão.

## 4. Critérios de homologação

- Branch única `feature/v0.8.6-analytics-logbook`, PR em rascunho até aprovação.
- Preservar contratos e saldos de v0.8.5, fotos da frota, planejamento VFR e integração SimConnect.
- Testes unitários Windows/Linux Python 3.11 e 3.13, Playwright das duas telas (filtros, estado vazio e sessão com voos), empacotamento Windows, testes de inicialização e artifact ZIP.
- Testar bases antigas sem registros novos; métricas devem mostrar “sem dados” em vez de zero fictício ou exceção.
- Aceite físico no MSFS antes de mesclar a v0.8.6 em `main`.
