# FlightSimCarreira 0.8.3 — Pilot Career / Midnight Ops

## Estado
Implementação em `feature/v0.8.3-pilot-career` (PR #17, rascunho). Não mesclar à `main` até homologação visual/funcional do piloto no MSFS 2020. A v0.8.2 aprovada já está na `main`.

## Primeiro acesso e proteção do piloto oficial
- Feche a versão anterior e faça cópia de `%APPDATA%\AeroCarreira-Lab\carreira.db` antes de instalar a versão experimental.
- A carreira oficial continua no caminho original. Na primeira inicialização, `profiles.py` cria `pilot_profiles.json` e um backup consistente e não substituível chamado `carreira.pre_profiles.backup.db`.
- Perfis novos têm bases distintas: `%APPDATA%\AeroCarreira-Lab\profiles\<id>\carreira.db`. Avatar, frota, planilha `.PLN`, dinheiro, contratos, eventos e XP são por perfil.
- Só altere de perfil desconectado e em solo. A troca salva o checkpoint, encerra o aplicativo e abre uma nova instância com o SQLite escolhido.

## Como criar o laboratório Teste/Admin
1. Abra **Meu Piloto** e **Gerenciar perfis**.
2. Em **Criar novo perfil**, mantenha **Nome: Teste**, **Indicativo: TESTE**, **Base ICAO: SBRF**, e marque **Criar como Teste / Admin**.
3. Clique **Criar perfil**. Selecione **Teste** na lista e **Trocar perfil** com MSFS desconectado.
4. No perfil Teste, abra **Admin / Showcase**. Defina nível/XP visual/reputação, escolha o distintivo, conceda ou bloqueie qualquer licença e medalha, escolha presets de progressão e teste as animações de ganho/perda/promoção.
5. Clique **Aplicar prévia**. As condições visuais de Admin não gravam XP em `pilot_xp_ledger` nem manipulam dinheiro ou missões. Experimente **Equipar na foto** na aba Conquistas.
6. **Reiniciar perfil Teste** pede confirmação e cria backup do banco de teste antes de recomeçar; não altera o perfil oficial.
7. Para voltar à carreira oficial, use **Gerenciar perfis** e selecione **Carreira principal**, após desconectar o MSFS.

## Design e conquista variável
- Patentes inspiradas em insígnias aeronáuticas, 18 categorias/faixas entre níveis 1 e 100, sempre exibidas no cabeçalho e perfil.
- Treze conquistas especiais, em arte vetorial original, com status bloqueado, disponível ou conquistado; medalha conquistada pode ser equipada na foto e é replicada no cabeçalho/Dashboard.
- Reputação 70/90 são conquistas **condicionais**. Quando reputação fica abaixo do limiar, perde o status ativo e dispara animação sutil de medalha se partindo. Ao recuperar, uma nova conquista é registrada e animada. A linha do tempo guarda perdas e recuperação; não apaga o primeiro desbloqueio.
- Conquistas permanentes preservam a conquista quando há posterior mudança de desempenho.
- Galeria de licenças PPA/PCA/IFR/MLTE/PLA, gráficos de pousos (taxa vertical), contratos por mês e horas por aeronave, linha do tempo persistente. A concessão oficial de licença só acontece pelo motor da carreira.
- Preferência de movimento reduzido remove animações decorativas automaticamente.

## Flight Operations — adições
- Clique **direito** ou **Shift+clique** no mapa, ou toque prolongado (~800 ms) e confirme o ponto com coordenadas e nome sugerido FSC01, FSC02 etc. O mapa único MapLibre e o SVG offline suportam o gesto.
- **Limpar plano** pede confirmação e apaga só o rascunho/checklist; contrato existente mantém origem/destino, não é cancelado nem muda saldo/XP/histórico.
- **Bônus automático**: marcações manuais de pista/rota/checklist não pontuam. Relógio, assistências, combustível e MTOW só pontuam com SimVars atuais e verificadas; penalidades e eventos de estol, táxi, G e arremetida são auditáveis conforme cobertura da telemetria, sem assumir ausência de eventos quando a leitura está indisponível.
- Sem retorno de bônus por clima real. Não há navegação IFR avançada nesta versão.

## Regresso e aceite
CI Python 3.11/3.13 Windows/Linux, Playwright com visualização/gestos/animações, smoke do executável Windows. Testes de perfis isolados, migração, backup, medalhas condicionais, concessões e bônus por dados verificados. A `main` permanece estável até a aprovação do piloto.

## Revisão de design — Alpha.2 (aprovação pendente)
- As janelas de evento **não fecham automaticamente**: as animações de ganho, quebra, reconquista e promoção terminam, mas a janela permanece aberta até botão Fechar, ESC ou clique externo do piloto.
- A patente usa novo desenho esguio, com motivo interno preservado; o distintivo legado do topo foi retirado. A medalha equipável da foto permanece.
- As 13 conquistas têm **desenhos vetoriais locais exclusivos por significado**, não apenas estrelas coloridas: First Plane inclui avião pousado/1º, Frota mostra três aeronaves/um hangar; Reputação 70/90 contém certificação e valor, com materiais hierarquizados.
- Os cinco certificados têm acabamento crescente e tipografia técnica, selos personalizados, identidade FlightSimCarreira e estados visuais já suportados (bloqueada/disponível/obtida).
- Gráficos: escalas e valores explícitos, unidades, legenda explicativa, média de pousos, detalhamento de meses e modelos. Um mês apenas usa uma barra de largura limitada.
- Linha do tempo, idempotência de conquistas, estado da carreira, perfil Teste e transações não foram reestruturados.
- Testes reforçados em `scripts/verify_dashboard.py` e `tests/test_midnight.py`; usar pacote Windows **v0.8.3 Alpha.2** em uma pasta separada para homologação antes de integrar na main.
