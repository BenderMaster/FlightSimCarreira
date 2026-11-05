# Mercado de Aeronaves — v0.8.1

## Experiência
Menu **Mercado de Aeronaves**, independente do menu **Mercado** de contratos e de **Frota / Hangar**. Página HTML Midnight com abas para modelos novos, ofertas usadas locais, aluguel e revenda. Coluna de cards, modelo em foco e resumo da cotação. Operação só ocorre após confirmar diálogo. O campo `aircraft_market.notice` do snapshot sinaliza sucesso/falha da operação executada pela thread Tk, distinguindo resposta enfileirada de transação financeira efetivada.

## Backend e validação
`aerocarreira/aircraft_marketplace.py` apresenta catálogo com preços de `AIRCRAFT_ECONOMY`, `used_market()` e `rental_fee()` do domínio. O usuário escolhe dados de catálogo; o backend recompõe cotações sem confiar no payload do cliente. Não existe operação de compra de modelo desconhecido, ICAO fornecido via HTML ou quantia monetária arbitrária.

Para transacionar no MSFS: piloto cadastrado, conexão ativa, catálogo de aeródromos oficial desta sessão carregado, amostra de solo com timestamp recente, distância em até 6 NM do aeródromo confirmado e nenhuma missão ativa ou fase aérea. Modalidade Demo usa somente catálogo de demonstração. Se MSFS ainda não estiver pronto, os modelos podem ser vistos, mas a compra/aluguel/venda ficam bloqueados.

A compra cria unidade `unit:` na Frota; usada contém estado e horas da oferta e só pode ser vendida uma vez na semana. O aluguel gera `rent:` temporário por 24/48/72/168 h, não aparecendo na Frota própria. A revenda requer `unit:` no aeródromo local e credita o saldo, removendo a foto do banco. A aeronave starter e os bens `legacy:` não são revendidos pela nova loja.

O pedido inclui UUID opaco. `FleetManager` grava-o com `PRIMARY KEY` em `fleet_market_requests` no mesmo `with conn` que a movimentação e a mutação da aeronave. Tentativa repetida não desconta novamente. Falhas por falta de dinheiro revertem também o UUID, liberando tentativa legítima posterior.

**Nota SDK:** transações são inteiramente virtuais; o addon não compra licenças, instala aeronaves nem muda o avião carregado no MSFS. Antes de voar o piloto deve escolher o modelo correto no simulador.

## Reconexão
O worker continua a tentar. `ReconnectWarningFilter` não exibe de novo `Conexão interrompida:...` enquanto permanece desconectado e é resetado no evento de conexão confirmada. Os avisos de combustível, plano, carga e sensores não são suprimidos.

## Homologação
- Abrir aplicativo antes do MSFS e observar apenas uma entrada de falha, mesmo após várias tentativas.
- Iniciar MSFS em solo e confirmar restabelecimento do estado de conexão/catálogo.
- Abrir quatro abas, conferir preço, saldo e aeroporto do mercado. Comprar um modelo e conferir nova unidade na Frota e ledger.
- Tentar comprar a mesma usada duas vezes; segunda tentativa deve ser rejeitada.
- Alugar modelo 24 h, verificar rental em Aluguéis ativos, não na Frota própria.
- Vender unidade adquirida no aeroporto local; confirmar saldo, remoção da Frota e da foto no banco.
- Testar saldo insuficiente, voo em andamento, aeródromo remoto e contrato ativo: transação deve ser bloqueada.
- Fechar e reabrir: dinheiro, unidades e aluguéis persistem.

Backup obrigatório do `carreira.db` com aplicativo fechado, e instalar em pasta nova.

## Atualização Alpha.2

- C172, G58, King Air e CJ4 recebem **ilustrações conceituais SVG originais** locais. Não são fotografias nem pinturas oficiais; o C152 permanece com a foto licenciada e crédito.
- Aba Novas e catálogo usam uma etiqueta NEW. A ficha da aeronave tem rolagem própria e o rodapé não repete instruções.
- O catálogo econômico mantém os cinco modelos atuais; os requisitos de aeronaves de contratos freelancer não se confundem com regras novas de aquisição.
- Geração de contratos computa preços com distância, modalidade, nível e reputação. O valor é persistido antes do aceite, e não sobe retroativamente para missões aceitas.
