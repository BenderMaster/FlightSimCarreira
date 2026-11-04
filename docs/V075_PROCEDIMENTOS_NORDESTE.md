# FlightSimCarreira v0.7.5 — Pontuação e limitações

## Fonte de evidência
O adaptador lê opcionalmente `ASSISTANCE_LANDING_ENABLED`, `ASSISTANCE_TAKEOFF_ENABLED`, `AI_CONTROLS`, `UNLIMITED_FUEL`, `ZULU_TIME`, `SIMULATION_RATE`, `GENERAL_ENG_COMBUSTION:1`, `LIGHT_BEACON`, `LIGHT_NAV`, `LIGHT_TAXI`, `LIGHT_LANDING`, `LIGHT_STROBE`, `G_FORCE` e leituras já existentes de solo/altitude/estol/VS.

Ausência de SimVar NÃO é resposta negativa. Nenhuma luz, controle ou opção de MSFS é alterada pelo addon.

## Realismo de despacho
- +3% sobre pagamento e XP se Zulu no MSFS estiver a no máximo 120 segundos do UTC real e sim rate for aproximadamente 1.0. Comprova proximidade do relógio, não a seleção do preset de tempo real.
- +3% se assistências específicas de decolagem/pouso, IA e combustível ilimitado forem lidas e estiverem todas desligadas. Não comprova assistências de navegação ou outras categorias não expostas.
- +0% clima ao vivo: o SimConnect externo não fornece preset meteorológico confiável. Comparar METAR é insuficiente; declaração manual não rende XP automático.
- Até +9% restante de revisão de rota/pista, combustível e peso. Checklist de rota e pista continua declaratório, sem afirmar validação automática. Teto nesta versão: +15%.

## XP de segurança no pouso
- +4 XP somente com razão de descida estimada no instante do toque **maior que -150 ft/min e menor que 0**, sem nenhuma arremetida detectada neste voo.
- +1 XP por beacon aceso durante táxi com motor, +1 XP por taxi light acesa durante táxi, +1 XP por landing light acesa em descida próxima ao solo.
- -3 XP por aviso de estol, máximo 2; -2 XP por força G extrema sustentada por mais de 1s longe do solo, máximo 2; -2 XP por suspeita confirmada de táxi >25 kt por pelo menos 8s, máximo 2 episódios.
- -2 XP por landing light desligada por 4s na aproximação **após** ser observada acesa; -1 XP por beacon desligado por 4s durante táxi **após** ser observado aceso.
- Total limitado a -15 ... +7 XP por voo, liquidado na transação de pouso; saldo anterior de XP nunca é subtraído.
- Arremetida: exige ter alcançado >=800 ft AGL e, durante descida entre 30 e 600 ft AGL, observar ganho posterior >=170 ft com VS positiva. Há falsos negativos em circuitos muito baixos; o bônus de toque suave será indevido se a arremetida não puder ser detectada.
- Toque-e-arremetida: contato no solo por menos de 2s, seguido de decolagem para ao menos 15 ft AGL sem pouso confirmado; mantém o voo aberto, sem pagamento intermediário.
- Táxi >25 kt: somente suspeita de episódio mantido por 8s com IAS inferior a 45 kt. Episódios nos 50s anteriores à decolagem são descartados para não classificar aceleração na pista como infração. **Táxi após o pouso ainda não é pontuado**, pois os resultados são liquidados ao confirmar o pouso.
- Equipamento ausente/telemetria indisponível não gera multa; penalizar luz desligada exige observação anterior da mesma luz acesa.

## Mercado
- Regional mantém raio próximo variável por nível.
- Freelancer pesquisa aeroportos brasileiros no recorte poligonal **aproximado** do Nordeste (não equivale ao limite oficial dos 9 estados), com autonomia teórica do avião contratante reduzida em 30% para reserva. Não gera voos que exijam teleportar para origem remota.
- Renovação diária e invalidar cache no primeiro uso da v0.7.5 (marcador `nordeste-v1`). A existência do aeroporto no catálogo não prova compatibilidade com instalação atual do MSFS.

## Homologação e segurança
Testar no Windows com MSFS 2020 real: saída do C152, lâmpadas e assistências reconhecidas, mudanças de hora, pouso suave, arremetida, táxi e modelo freelancer. CI não comprova sensores físicos. Fazer backup do SQLite antes de instalar.
