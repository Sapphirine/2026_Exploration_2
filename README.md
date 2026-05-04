# EvoResearcher

EvoResearcher is an interactive deep-research proposal system with:

- Rich TUI with animated live phases
- LangGraph orchestration
- DeepSeek API as the model backend
- Dual memory plus an Evolution Memory Agent (EMA)
- Tree-search based ideation
- LaTeX report generation and direct PDF rendering

## Quick start

```bash
python -m evoresearcher.main --mode general
python -m evoresearcher.main --mode ml
python -m evoresearcher.main --mode general --goal "Investigate why social protection programs in South Asia often fail the ultra-poor as of September 2023."
```

Outputs are written under `outputs/<run-id>/`.

## Environment

Create `.env` with:

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
```
