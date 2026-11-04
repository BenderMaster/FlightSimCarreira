# v0.7.2 — Janela nativa, mapas livres e meteorologia

## Correção do executável Windows

O piloto relatou RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize em _internal/pythonnet/runtime/Python.Runtime.dll.
Antes o CI testava somente --version; não inicializava o WinForms.
Agora o PyInstaller coleta pythonnet, clr_loader, cffi e clr, sem UPX. Dependências pythonnet e clr_loader têm versões fixadas.
O Windows CI executa FlightSimCarreira.exe --verify-native-webview e falha se o backend .NET não inicializar.
O Dashboard CONTINUA na janela WebView2 nativa; não usamos navegador externo como substituto.

Isso valida a importação do runtime nativo no GitHub Windows, mas não substitui a abertura gráfica do WebView2 no PC real.
Requisitos: Windows com .NET Framework 4.8 e Microsoft Edge WebView2 Runtime.

Para testar: feche a versão anterior; faça backup de %APPDATA%\AeroCarreira-Lab; extraia o ZIP inteiro numa pasta nova.
Não execute .exe dentro do ZIP ou separado de _internal. Não junte pastas de duas versões.
Se persistir bloqueio de DLL, confira nas Propriedades do ZIP baixado se o Windows sinaliza arquivo de origem da Internet.
Não desative antivírus nem altere políticas de segurança sem diagnóstico.

## Mapa sem cartão

- Base padrão OpenFreeMap Dark e MapLibre GL JS 5.24.0 (BSD-3-Clause), instalado nos assets do pacote.
- Imagem opcional: EOxCloudless Sentinel-2 2016 (CC BY 4.0), via WMTS, sem API key.
- Crédito visível ao lado do mapa ao ativar Satélite: EOxCloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016 & 2017).
- Controles: scroll para zoom, clicar/arrastar, botões +/-, reenquadrar, ícone ciano da aeronave e linha da missão.
- No modo offline ou sem WebGL: mapa de coordenadas com rota, zoom e arraste continua visível.
- Camada Sentinel-2 é histórica, não meteorologia atual nem carta aeronáutica.
Fontes: https://openfreemap.org/ ; https://maplibre.org/ ; https://cloudless.eox.at/documentation/faq

## MSFS na origem, NOAA no destino

Origem: perto do aeródromo, captura vento real simulado, temperatura, visibilidade e pressão reduzida (quando SimConnect fornecer).
Destino: o backend solicita via HTTPS https://aviationweather.gov/api/data/metar?ids=ICAO&format=json. Cache de 10 minutos, reconsulta com atraso após falhas, thread daemon.
Perto do destino (10 NM): apresenta também o clima do MSFS, para comparar com boletim NOAA.
Sem estação METAR, sem rede ou dados ausentes: aparece indisponível, nunca um valor inventado.
Leitura do MSFS é na posição da aeronave: não é METAR oficial e não comprova clima em tempo real habilitado.
Consulta NOAA pode ser limitada por rate limit, não depende de chave/cartão e não altera o voo.

## Validação

CI Windows/Linux: testes unitários e gráficos em cinco resoluções. Windows também empacota e executa o smoke nativo.
Teste pendente no PC do piloto: iniciar .exe em janela, verificar mapa satélite, dados NOAA, fuel control e pagamento em voo curto.
Somente após teste físico este patch deve ser homologado.
