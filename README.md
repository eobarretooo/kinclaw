HEAD
# 🤖 KinClaw — Autonomous Self-Improving AI Agent

KinClaw is a 24/7 autonomous AI agent that analyzes its own code, proposes improvements, and implements them once you approve — all from your Telegram or Discord.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## Features

- **🔍 Self-analysis**: Reads and measures its own codebase continuously
- **🤖 AI proposals**: Uses Claude to generate concrete improvement proposals
- **📱 Multi-channel**: Telegram, Discord notifications
- **✅ Safe execution**: Guardrails prevent touching critical files or exceeding budgets
- **📋 Full audit log**: Every action logged for transparency
- **🌐 Web dashboard**: Real-time overview at `localhost:8000`

## Quick Start

```bash
# Clone the repo
git clone https://github.com/eobarretooo/kinclaw
cd kinclaw

# Configure
cp .env.example .env
# Edit .env with your tokens (ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, etc.)

# Install
pip install -r requirements.txt

# Run
python -m kinclaw run
```

## CLI Commands

```bash
python -m kinclaw run          # Start agent + dashboard
python -m kinclaw status       # Check agent status
python -m kinclaw proposals    # List pending proposals
```

## Approval Keywords

Reply to KinClaw in any channel with:

| Action  | Keywords                                    |
|---------|---------------------------------------------|
| Approve | `aprova`, `approve`, `yes`, `sim`, `ok`     |
| Reject  | `nega`, `reject`, `no`, `não`, `cancel`     |

## Docker

```bash
cp .env.example .env
# Edit .env
docker-compose up -d
```

## Architecture

```
Owner (Telegram/Discord)
        │ aprova/nega
        ▼
ChannelRouter ──→ MessageBus ──→ KinClawAgent
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                  SelfAnalyzer            ApprovalQueue
                  ClawComparator          ApprovalParser
                  ProposalGenerator       ApprovalExecutor
                         │                         │
                         └────────────┬────────────┘
                                      │
                              Guardrails (Safety + Limits)
                                      │
                              Git → GitHub PR
```

## Configuration

Key `.env` variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | required |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | optional |
| `GITHUB_TOKEN` | GitHub PAT for PRs | required |
| `SLEEP_BETWEEN_ANALYSES` | Seconds between cycles | 3600 |
| `MAX_PROPOSALS_PER_DAY` | Daily proposal limit | 3 |
| `MONTHLY_BUDGET_USD` | Max API spend/month | 100 |

## Security

- Guardrails prevent modification of `kinclaw/guardrails/` and `kinclaw/approval/`
- Daily commit/post rate limits enforced
- Monthly budget cap
- Full audit log of all actions
- All changes require explicit human approval

## License

MIT
=======
# kinclaw
fc20bf06dcef9a5c89747bf2f23da56f959c0f63
