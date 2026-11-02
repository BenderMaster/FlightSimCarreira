# Roadmap

## v0.1 Alpha — entregue para validação no Windows
- [x] Aplicativo Windows Tkinter, modo Demo sem simulador.
- [x] Integração opcional SimConnect somente leitura com 8 SimVars (7 essenciais exibidas, 1 para estado de solo; mais 2 opcionais: combustível/estol).
- [x] Detector de voo por estado do solo, com anti-bounce e estimativa de razão vertical no toque.
- [x] Diário local persistente SQLite, uma carreira independente.
- [x] Três contratos iniciais em Pernambuco e Paraíba, com validação de origem e destino e recompensa única.
- [x] Inspetor somente leitura que faz cópia de common.db e extrai apenas estrutura SQLite.
- [x] Testes independentes de MSFS e ação CI.
- [x] Demo e conexão SimConnect ao MSFS 2020 confirmadas pelo piloto no Windows.
- [ ] Inspeção do esquema real do NeoFly (aguarda localizar `common.db` ou `std.bin` no Windows do piloto).

## v0.1.1 — após teste físico
- Robustez de conexão e reconexão de SimConnect, frequência, dados nulos.
- Registro de múltiplos voos por sessão sem falso positivo em toques sucessivos.
- Atividade e logs de erro mais detalhados.
- Indicadores de combustível, aeronave, luzes, avisos de estol, arremetida.
- Refinamento de avaliação da aproximação e pouso para não incentivar comportamentos inseguros.

## v0.2 — fundação de carreira
- Importação opcional de campos de progresso do NeoFly após estudo de compatibilidade; nunca sobrescrever original.
- Cadastro de aeronaves, manutenção, abastecimento e seguro.
- Missões geradas a partir de catálogo licenciado de aeroportos, objetivos e regras realistas.
- Contratos diferenciados: turismo, carga, táxi aéreo.
- Progressão financeira, habilitações e reputação.

## v0.3+
- Histórias de voos e eventos narrativos originais.
- Companhia aérea, equipe, frota, empresas e contratos extensos.
- Pacote de instalação Windows em exe assinado, quando a arquitetura for estabilizada.
