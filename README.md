# Tem Sinal?

Mapa e estatísticas de torres de telecomunicação de todo o Brasil.

Criado por [Carlos A Becker](https://caarlos0.dev) usando [GitHub Copilot](https://github.com/features/copilot).

## Fontes

- **[ANATEL](https://sistemas.anatel.gov.br)** — Dados de torres
- **[IBGE](https://www.ibge.gov.br)** — Dados de população

## Cobertura

Apenas as três grandes operadoras são incluídas: **Vivo**, **Claro** e **TIM**.
A Oi Móvel não é incluída pois sua rede está sendo desativada e transferida
para as demais operadoras desde 2022.

Somente torres de acesso ao usuário final são exibidas (2G, 3G, 4G e 5G).
Torres de backhaul, backbone, enlaces ponto-a-ponto e outras tecnologias de
infraestrutura são excluídas.

O mapa mostra apenas a localização das torres — não é possível estimar o raio
de cobertura pois a ANATEL não disponibiliza dados de potência de transmissão,
altura da antena ou ganho.

## Desenvolvimento

Os dados são coletados e processados por scripts Python no diretório `updater/`:

```bash
uv run updater/anatel.py         # Baixa dados de torres da ANATEL
uv run updater/municipalities.py  # Gera índice de municípios com dados do IBGE
uv run updater/tile.py            # Gera tiles espaciais para o mapa
```

Depois, abra `index.html` para ver o mapa.
