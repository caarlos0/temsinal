# Conectividade Brasil

Mapa e estatísticas de torres de telecomunicação de todo o Brasil.

Criado por [Carlos A Becker](https://caarlos0.dev) usando [GitHub Copilot](https://github.com/features/copilot).

## Fontes

- **[ANATEL](https://sistemas.anatel.gov.br)** — Dados de torres
- **[IBGE](https://www.ibge.gov.br)** — Dados de população

## Desenvolvimento

Os dados são coletados e processados por scripts Python no diretório `updater/`:

```bash
uv run updater/anatel.py         # Baixa dados de torres da ANATEL
uv run updater/municipalities.py  # Gera índice de municípios com dados do IBGE
uv run updater/tile.py            # Gera tiles espaciais para o mapa
```

Depois, abra `index.html` para ver o mapa.
