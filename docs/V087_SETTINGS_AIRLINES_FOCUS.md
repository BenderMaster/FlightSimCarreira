# FlightSim v0.8.7 Alpha.1 — Configurações, companhias e conquistas

Status: branch de homologação (PR #22 em rascunho). A versão estável em main não foi alterada.

## Configurações Midnight Ops — última tela

A nova tela integrada possui seis seções:

1. Simulador: status/telemetria SimConnect, modelos e aeroportos detectados, conectar/desconectar, conexão no início e reconexão automática; Demo identificada separadamente.
2. Carreira: combustível (desligar causa penalidade de 30% sobre R$ e XP), imposto virtual de 4%, preparação para falhas simuladas. Alterações de regras durante voo são bloqueadas. A opção de falhas ainda NÃO injeta falhas no simulador.
3. Interface: escala 80–150%, redução de animações, satélite inicial e notificações; mantém Midnight Ops.
4. Dados e backups: todos os perfis SQLite, fotos, arquivo de preferências em ZIP por backup consistente com WAL; restaura como NOVOS perfis, sem substituir carreira existente.
5. Diagnóstico: leitura apenas de aircraft.cfg (Official/Community), log exportável com proteção opcional de caminhos e coordenadas, ferramentas legadas de análise.
6. Sobre: versão, tecnologias, créditos de mapa/foto e endereço do repositório.

Preferências gerais persistem no arquivo settings-v087.json; preferências de realismo de cada carreira no SQLite do perfil ativo. Comandos autenticados por token e Origin no servidor loopback. ZIP de restauração com validação de manifesto, integridade SQLite, formato de nomes e tamanho. Nenhum arquivo do MSFS é alterado.

## Companhias e aeronaves

| Empresa | Modelos autorizados |
|---|---|
| Azul | A320neo, A321neo, A321P2F, A330-200, A330-900neo, E195-E1, E195-E2, ATR 72-600, C208B, C408 |
| GOL | B737-700, B737-800, B737 MAX 8, A330-900neo, A320neo |
| LATAM | A319-100, A320-200, A320neo, A321-200, A321neo, A321XLR, B767-300ER, B777-300ER, B787-8, B787-9 |
| AeroNordeste | C152, C172, Baron G58, King Air, Citation CJ4 e tipos avançados habilitados |

São regras do jogo, não declarações de frota comercial real.

Salário-base de um ciclo de sete dias reais: AeroNordeste R$ 9 mil, LATAM R$ 17 mil, GOL R$ 23 mil, Azul R$ 30 mil. Permanecem os ajustes de nível/reputação/cargo e o compromisso semanal 0/10/20%, sem alteração da remuneração dos voos particulares.

Habilitação individual de modelo é distinta de PPA/PCA/IFR/MLTE/PLA: são necessários **dois voos MSFS reais de ao menos dez minutos cada**, com estol zero e razão de pouso de -650 a -30 ft/min, registrada. O segundo voo válido produz a licença de tipo e a persiste no SQLite. Treinamento em aeronave disponível no MSFS não exige compra virtual. Voos Demo nunca geram habilitação. Registros idempotentes evitam duplicações de progressos e licenças.

Para candidatar-se a Azul/GOL/LATAM é necessária habilitação de ao menos um dos modelos autorizados, além dos requisitos normais. Contratos da companhia só usam modelos da frota com habilitação individual e confirmação de disponibilidade no MSFS. Backend revalida na contratação/aceite e o fluxo existente confere a aeronave do SimConnect na decolagem e no pouso. C152 nunca entra em contrato da GOL. O mercado Freelancer preserva cinco modelos clássicos para evitar preços fictícios de widebodies.

Limitações: varredura da pasta MSFS é somente leitura e pode não enxergar aeronaves protegidas do Marketplace. Arquivo aircraft.cfg encontrado não comprova licença. O addon não troca a aeronave no MSFS automaticamente.

## Desbloqueios de conquistas ao voltar ao foco

O prêmio e o evento são persistidos assim que o voo é registrado no SQLite. A lista de eventos novos fica pendente, em ordem, se o navegador está oculto ou sem foco; a interface só exibe cada animação se document.visibilityState está visível e document.hasFocus() é verdadeiro. Cada diálogo é confirmado no SQLite depois de fechado; reiniciar antes de fechar não perde a notificação. O piloto pode desligar as notificações sem abrir mão de conquistas. Eventos antigos anteriores à migração não geram popups retroativos.

## Checklist para teste físico no MSFS 2020 Steam

1. Instalar o ZIP completo em pasta nova. Fechar o addon e fazer cópia de segurança de %APPDATA%\AeroCarreira-Lab antes do primeiro teste.
2. Navegar nas seis seções; verificar conexão, autoconexão após reiniciar, reconexão, escala, satélite e avisos.
3. Fazer backup, importar e confirmar um novo perfil sem sobrescrever o piloto oficial; observar que fotos e dados financeiros continuam isolados.
4. Verificar Companhias → Treinamento. Escanear Official/Community, realizar dois voos MSFS válidos com modelo reconhecido e verificar habilitação; nenhum C152 na GOL.
5. Conquistar uma medalha voando com MSFS em primeiro plano e FlightSim minimizado/atrás. Verificar a animação apenas quando voltar ao FlightSim.
6. Verificar ausência de regressões em Logbook, relatórios, inventário, contratos Freelancer, combustível e finanças.

## Qualidade

CI: Python 3.11/3.13 em Windows/Linux, Playwright com teste visual de foco e seis seções, build Windows PyInstaller com assets offline e smoke WebView/SimConnect. O CI não substitui o teste em voo real. Nenhum modelo é instalado no simulador nem se injeta falhas reais nesta versão.
