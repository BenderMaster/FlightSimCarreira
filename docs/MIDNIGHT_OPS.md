# Midnight Ops — 0.7.0-midnight.alpha.1

Base funcional: `3048bb86ee498770b93862ef449fb4d2ff6e061f` (v0.6.1-alpha.1).
Esta linha foi reconstruída diretamente dessa base. Não incorpora silenciosamente a UI de v0.6.2/0.6.3 e não substitui a main.

## Execução e atualização

1. Feche a versão anterior e copie `%APPDATA%\AeroCarreira-Lab` como backup da carreira.
2. Extraia o pacote completo em uma pasta nova. Não misture os arquivos com outra versão.
3. Pacote Windows compilado: execute `FlightSimCarreira.exe`. O Microsoft Edge WebView2 Runtime deve estar instalado.
4. Pacote de código: instale Python 3.11 x64, execute `instalar_windows.bat` e depois `iniciar_windows.bat`.
5. Se a janela WebView não iniciar, será aberta a interface clássica preservada. Também existe `iniciar_classico_windows.bat`.
6. Cadastre/abra o piloto, selecione a aeronave no Hangar, conecte o MSFS em Configurações e confirme a leitura do combustível antes de voar.

O banco continua no diretório original. Não há migração de esquema adicional; somente a configuração `pilot_avatar_v1` pode ser gravada. A foto é normalizada para PNG local de 256×256, sem metadados EXIF, fora do repositório.

## Arquitetura

- `app.py`: dono da thread Tk, SQLite, motor de carreira, worker SimConnect e janelas existentes. A interface clássica permanece disponível como recuperação.
- `dashboard.py`: transforma dados reais em estado de apresentação; não implementa pagamento, XP, consumo ou concessão de habilitações.
- `midnight_server.py`: servidor em porta aleatória, exclusivamente `127.0.0.1`. GET de estado exige token por sessão; POST exige token, Origin exata e Host exato. Comandos têm allowlist, corpo limitado a 2 KB, fila limitada e nenhum parâmetro monetário arbitrário. Não há CORS nem acesso a caminhos livres.
- `dashboard_controller.py`: drena comandos na thread Tk, chama fluxos existentes, valida operações diretas e publica snapshots. Falhas de transporte não alteram as regras do motor.
- `webview_host.py`: processo separado de WebView2. Fechamento é encaminhado ao encerramento seguro da carreira; encerramento da janela também encerra o processo principal. Minimizar é uma capacidade nativa limitada.
- `midnight/`: HTML/CSS/JavaScript local, ícones vetoriais, fonte embarcada e ilustrações. Não depende de CDNs para abrir.

A interface web pode futuramente compartilhar componentes com a toolbar, mas esta entrega **não** implementa uma nova toolbar nem altera a ponte in-game experimental.

## Contratos de dados

Saldo é lido de `settings.balance`. XP utiliza `pilot_stats` e `level_progress`; a barra é relativa à faixa do nível atual. País vem do registro ICAO do catálogo, com fallback apenas para aeroportos brasileiros conhecidos; não se deduz país apenas pela primeira letra. Brasil tem bandeira vetorial; outros países exibem código ISO nesta alpha.

Mercado usa o gerador, cache diário, condições de elegibilidade e exclusão de ofertas concluídas. A aceitação passa novamente pelo fluxo da v0.6.1. Aeronaves de freelancer são identificadas como do contratante, sem apresentar condição pessoal como se fosse dessa aeronave.

Combustível usa inventário persistido e capacidade registrada. Controle ativo **não** é apresentado como prova de sincronização: a confirmação/erro continua no registro do motor. A telemetria não duplica combustível. A mudança do controle é bloqueada em voo. Bônus máximo de 18% e penalidade de 30% continuam no domínio original, congelados na decolagem.

Resultado operacional é soma em regime de caixa das receitas de contratos e bônus menos penalidades, taxas, combustível, abastecimento pré-pago, manutenção, seguro e aluguel. Exclui saldo inicial, empréstimos, parcelas de financiamento, fundação de companhia e compra/venda de ativos. Não é saldo disponível nem lucro contábil por competência. Reputação e METAR permanecem indisponíveis.

## Mapa e limitações visuais

O mapa desta alpha é uma projeção equiretangular local com correção de longitude pela latitude central. Usa coordenadas reais dos aeroportos e da telemetria, escala em NM, zoom e reenquadramento. Sem missão, mostra a posição recebida ou a base conhecida. Telemetria antiga é marcada como desatualizada. Não inventa relevo, litoral nem rota.

**Há camada online NASA GIBS Blue Marble**, um mosaico histórico de resolução limitada (até nível 7 geográfico), com crédito visível. Apenas tiles da área visível são solicitados; até 64 imagens são mantidas em memória. Sem rede, permanece a grade com coordenadas/rota. A imagem não representa clima atual, tráfego nem carta aeronáutica. O Cessna 152 possui fotografia licenciada (CC BY-SA 4.0), exibida somente para esse modelo, com crédito acessível no botão de informação. Demais modelos usam ilustração genérica identificada. O cenário decorativo da sidebar foi gerado por IA e não é fotografia documental. O mapa não é uma carta de navegação.

As janelas secundárias de frota, piloto, finanças, companhias e despacho continuam sendo as telas Tk da v0.6.1. O dashboard recebeu o novo estilo; a migração visual dessas janelas fica pendente. Pistas/Peso abrem o despacho existente, sem anunciar base de dados nova. Relatórios avançados ficam identificados como em desenvolvimento.

A referência aprovada usa enquadramento, fotografia, mapa de maior detalhe e tipografia que esta alpha ainda não reproduz exatamente. A entrega não é pixel a pixel idêntica e não atende integralmente o alvo visual final.

## Validação reproduzível

```powershell
py -3.11 -m unittest discover -s tests -v
py -3.11 -m pip install playwright pillow airportsdata
py -3.11 -m playwright install chromium
py -3.11 scripts/verify_dashboard.py
```

Linux: `xvfb-run -a python scripts/verify_dashboard.py`.

O teste gráfico inicia **Application real**, usa SQLite temporário e o modo Demo explicitamente identificado. Verifica dados, seis instrumentos sem combustível, rota, ofertas, aba meteorológica, zoom, comando de avanço, fechamento e persistência. Captura cinco resoluções com 100/125/150% equivalentes de área lógica, reservando 40 pixels para barra de tarefas. Isso não substitui ensaio físico de DPI/WebView2 no Windows.

A compilação Windows é feita pelo job `windows-package` com PyInstaller. Seu teste `--version` comprova a execução do binário e a importação inicial; não comprova conexão ao MSFS nem abertura física do WebView2.

Não foram executados voos reais no MSFS neste ambiente. A validação do SimConnect usa a suíte de regressão e seus adaptadores simulados.
