# FlightSim v0.9.3 InGame Alpha.2 — aeroportos, mapa e turnaround

**Base:** main v0.9.2 homologada; branch \`feature/v0.9.3-airport-services-gate-turnaround-map\`.  
**Estado:** build de testes, não aprovada nem mesclada. Nunca copiar fonte SDK como se fosse pacote compilado.

## Recursos implementados

### Mercado de contratos e aeroportos do MSFS
Na página Mercado Regional e Freelancer, cada oferta exibe os dados efetivamente coletados para o aeroporto **de destino**: presença de ILS, PAPI, luzes da pista, iluminação de aproximação e posição de combustível. Filtro opcional exige um campo confirmado positivo. Quando o simulador não entrega a instalação, a resposta é **Não verificado**, e não “Não”.

A origem de códigos aeroportuários continua sendo **somente o catálogo completo de aeroportos SimConnect da sessão atual**, jamais sites externos ou dados de um MSFS anterior. O FlightSim pede detalhes gradualmente (um aeroporto a cada aproximadamente 0,8 segundos, máximo 50 aeroportos por sessão). O SimConnect 2020 expõe Runway, Taxi Parking e VASI por FacilityData; o novo parser valida IDs e os tipos de dados. **Estas mensagens nativas exigem validação física com o SDK/MSFS 2020 — o CI simula os pacotes.**

O tipo FUEL significa que o SDK encontrou uma **vaga/posição de combustível**, não que exista reabastecimento operacional com preço ou caminhão disponível. Para este último, a API de instalação não traz confirmação.

### Aceite estritamente estacionado
O motor exige: \`SIM ON GROUND\` verdadeiro, \`ON ANY RUNWAY\` falso, \`PLANE IN PARKING STATE\` ou \`ATC ON PARKING SPOT\` verdadeiro, \`GROUND VELOCITY\` real abaixo de 1,5 kt e \`BRAKE PARKING POSITION\` acionado. Sem telemetria verificável, o aceite fica bloqueado e o painel indica o que faltou. Pode aceitar com motor ligado, desde que imobilizado e estacionado.

### Conclusão e pagamento somente após shutdown
O toque/pouso em aeroporto de destino inicia uma condição pendente. Táxi até portão/rampa/estacionamento → parada total → freio acionado → **todos os motores apagados** → confirmação ininterrupta de 6 segundos → confirmação do motor → gravação do voo e pagamento uma única vez no SQLite. Assim a decolagem e o pouso continuam sendo detectados como antes, mas não encerram automaticamente o contrato. O cálculo do toque é mantido com a razão vertical do pouso real; a duração do voo inclui táxi até estacionamento.

O estado pendente é persistido em checkpoint; no reinício, o temporizador de segurança começa de zero. Troca de aeronave ou estacionamento noutro aeroporto bloqueia o crédito. Em caso de sensor não reportado, o sistema não inventa confirmação. Uma futura fase poderá fornecer alternativa configurável de estacionamento via geometria do aeroporto, mas **não há fallback inseguro nesta Alpha**.

### MapLibre/OpenFreeMap no tablet
Na página Mapa, opções Mapa OpenFreeMap e Satélite EOX usam biblioteca MapLibre local já distribuída junto do Windows. Renderiza avião e rota com zoom/arraste. Caso falte WebGL ou o navegador Coherent não consiga acessar as tiles, o SVG original permanece disponível como fallback legível, com posição e proa reais. **O mapa VFR nativo do MSFS 2020 não é embutido no iframe**: não há integração pública oficial garantida.

## Instalação

Para quem já tem a toolbar da v0.9.2 na pasta Community, **não é preciso recompilar**: o wrapper SDK continua o mesmo e o tablet recebe tudo de \`http://127.0.0.1:8769\` do companion Windows. Feche \`FlightSim.exe\`, extraia a nova build Windows inteira numa pasta separada, execute a nova versão e abra FlightSim pela toolbar no MSFS. O aplicativo usa Windows GUI, sem CMD.

A distribuição SDK fornecida no Actions contém **fonte**, para reinstalação do zero via Developer Mode/Project Editor; copiar a fonte diretamente para Community não compila o pacote.

## Teste físico obrigatório — MSFS 2020 Steam

- [ ] O contrato na pista fica indisponível; tela exibe causa de bloqueio.
- [ ] Em estacionamento, freio acionado, velocidade zero e motor ligado, é possível aceitar contrato.
- [ ] Mercado mostra ILS/PAPI/luzes/ponto combustível conhecidos sem converter desconhecido em ausente; comparar SBRF e campos menores.
- [ ] O caractere quebrado entre ICAOs foi substituído por seta SVG e renderiza corretamente no Coherent.
- [ ] MapLibre abre ao entrar em Mapa; caso falhe, volta sozinho ao SVG, sem derrubar o tablet.
- [ ] No destino, tocar a pista, frear e sair da pista NÃO paga o contrato.
- [ ] Táxi até portão com motor funcionando continua pendente.
- [ ] Parar e aplicar o freio ainda não paga se o motor estiver ligado.
- [ ] Desligar todos os motores por 6 segundos no pátio valida e paga **uma vez**; não exige desligar a bateria.
- [ ] Penalidade de táxi e bônus reais permanecem após conclusão.
- [ ] Reiniciar o companion com pós-voo pendente não credita dinheiro antes da conclusão; só completa após restaurar estado e motor desligado no estacionamento.
- [ ] Em uma aeronave de dois motores, apenas um desligado não finaliza.
- [ ] Ao reconectar ou mudar de avião, não gera pagamento duplicado.
- [ ] Compare saldo/XP/Logbook entre tablet e Windows.

Usar **perfil de testes ou backup antes de voar**. O addon persiste os mesmos arquivos SQLite da v0.9.2.

## Limitações e riscos assumidos

- O protocolo SimConnect para instalações aeroportuárias pode variar com SDK e cenário instalado; na falta de resposta, mostrar “Não verificado” e registrar erro.
- Não presumir que posição \`FUEL\` oferece serviço de abastecimento real.
- Disponibilidade da base de mapa vetorial depende da rede e de WebGL compatível com o Coherent do MSFS 2020.
- O símbolo de seta é um elemento SVG, dispensando fontes do sistema.
- Qualquer remuneração continua autoritativa no Python/SQLite. Os novos filtros e layouts não alteram o pagamento do backend.

### Código de referência
\`aerocarreira/airport_facilities.py\`, \`sim_facilities.py\`, \`sim_adapter.py\`,
\`turnaround.py\`, \`app.py\`, \`domain.py\`, \`ingame_bridge.py\`,
\`in_game/flightcare_panel.html\`, \`in_game/ingame-map.js\`,
\`tests/test_v093_turnaround_airports.py\` e \`scripts/verify_ingame.py\`.


## Diagnóstico da Alpha.2 (após testes físicos da Alpha.1)

Se o tablet ainda bloquear o contrato no portão, abra **Mercado > Diagnóstico da posição de estacionamento**. O relatório mostra, separadamente, os valores de ON ANY RUNWAY, PLANE IN PARKING STATE, ATC ON PARKING SPOT, BRAKE PARKING POSITION e estado de motores. Um campo "Indisponível" indica ausência da variável na biblioteca/SDK, não que a aeronave esteja na pista. O backend continua sem permitir aceite enquanto não comprovar que a aeronave saiu da pista.

No Mercado Windows, a área "Instalações no destino" foi acrescentada a esta versão. A v0.9.3 Alpha.1 exibia dados somente no InGame. Dados não retornados em 18 segundos são anotados no log, e **Atualizar ofertas** tenta consultar novamente.

A API FacilityData do MSFS 2020 **não fornece EDGE_LIGHTS nem CENTER_LIGHTS para RUNWAY** (essas definições foram retiradas). "Luzes de cabeceira" corresponde a campos `HAS_END_LIGHTS`, `HAS_REIL_LIGHTS` ou `HAS_TOUCHDOWN_LIGHTS` do tipo APPROACHLIGHTS, quando confirmados. Não deve ser confundido com iluminação contínua da pista. Para "iluminação de pista", o estado permanece "Não verificado" até uma fonte verificável específica.
