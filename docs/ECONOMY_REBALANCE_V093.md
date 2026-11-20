# FlightSim v0.9.3 InGame Alpha.3 — rebalanceamento econômico

## Objetivo

Tornar o emprego em companhias uma escolha financeiramente atraente sem eliminar a viabilidade do mercado autônomo.

## Salários semanais-base

| Companhia | Antes | Alpha.3 |
|---|---:|---:|
| AeroNordeste | R$ 9.000 | R$ 36.000 |
| LATAM | R$ 17.000 | R$ 68.000 |
| GOL | R$ 23.000 | R$ 92.000 |
| Azul | R$ 30.000 | R$ 120.000 |

Os salários-base foram quadruplicados. Os multiplicadores existentes de nível, reputação e patente continuam valendo. Os compromissos opcionais de 10% e 20% continuam concedendo bônus quando a meta escolhida é cumprida e aplicando o desconto previsto quando apenas a meta básica é alcançada.

## Mercado autônomo

Os contratos do mercado Regional e Freelancer passam a pagar 90% do valor anterior (redução de 10%), com arredondamento para R$ 10. O ajuste é aplicado apenas às novas ofertas autônomas.

Não são alterados:
- pagamento dos contratos de funcionário (que continua concentrado na folha semanal);
- receita e custos das rotas da companhia própria;
- contratos já aceitos, que preservam o valor contratado;
- XP, metas semanais, requisitos de contratação ou custos operacionais.

## Migração de saves

Na primeira abertura da Alpha.3:
1. Salários congelados de semanas ainda não pagas são multiplicados por quatro.
2. Folhas que já possuem registro em `airline_payroll` permanecem intactas.
3. O cache de ofertas não aceitas é limpo para que o mercado gere os novos valores.
4. Contratos ativos persistidos no checkpoint e pagamentos já registrados não são reescritos.

A migração é protegida por uma chave persistente e não se repete nas próximas inicializações.

## Verificações automatizadas

- Hierarquia e valores semanais exibidos nas vagas e calculados pela folha.
- Desconto de 10% em ofertas Regional e Freelancer.
- Migração única de salários pendentes, preservação de folha liquidada e invalidação do cache antigo.
- Regressões existentes de XP, metas, pagamento semanal e idempotência.

A CI não substitui a homologação do companion no MSFS 2020 Steam. A PR #25 permanece em rascunho até a validação física.
