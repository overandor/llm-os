# LLM OS — Autonomous Operating System for LLM-Driven Economics

The LLM OS is an autonomous operating system built on top of [membra-core](../membra-core/) that enables LLMs to:

1. **Create other LLMs** — Spawn, train, and manage model instances using LLMGPT
2. **Build software systems** — Autonomously develop deployable applications, APIs, trading bots
3. **Generate real income** — Marketplace builds, compute rental, model licensing, policy-gated trading
4. **Track economics** — Cost accounting, profit calculation, budget allocation, runway analysis
5. **Stay safe** — Governance gates, emergency halt, audit trails, human approval flows

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LLM OS KERNEL                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ │
│  │  SENSE  │ │ DECIDE  │ │  PLAN   │ │ EXECUTE │ │VERIFY│ │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └──┬───┘ │
│       └───────────┴───────────┴───────────┴──────────┘      │
│                         ↓                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                     LEARN & ACCOUNT                  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  ECONOMIC     │    │   SYSTEM      │    │   LLM         │
│  ENGINE       │    │   BUILDER     │    │   FACTORY     │
│               │    │               │    │               │
│ • Marketplace │    │ • Web apps    │    │ • Create specs│
│ • Trading     │    │ • APIs        │    │ • Train models│
│ • Compute rent│    │ • Trading bots│    │ • Evaluate    │
│ • Model license│    │ • Dashboards  │    │ • Export C++  │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │    TREASURY     │
                    │  (accounting)   │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │   GOVERNANCE    │
                    │  (safety gates) │
                    └─────────────────┘
```

## Quick Start

```bash
# Show OS status
python -m llm_os status

# Run one autonomous cycle
python -m llm_os start --once

# Start continuous autonomous loop
python -m llm_os start

# Scan for economic opportunities
python -m llm_os scan

# Build a system
python -m llm_os build api_service

# Train an LLM
python -m llm_os train my_model

# Check treasury
python -m llm_os treasury
```

## Python API

```python
from llm_os import Kernel

# Initialize with conservative policy
kernel = Kernel(starting_balance_usd=100.0)

# Run one cycle
kernel.start(autonomous=False)

# Or run continuous loop
kernel.start(autonomous=True, max_loops=10)

# Check status
print(kernel.get_status())
```

## Subsystems

### Economic Engine
Scans for and executes revenue-generating opportunities:
- **Marketplace builds** — Claim jobs from membra marketplace, build artifacts, earn bounties
- **Trading** — Policy-gated Gate.io futures market making (wraps existing systems)
- **Compute rental** — Rent idle worker capacity for inference/validation
- **Model licensing** — License trained model checkpoints

All opportunities are evaluated for expected ROI before execution.

### System Builder
Autonomous software development:
- Analyze job requirements
- Generate code (web apps, APIs, trading bots, dashboards, pipelines, LLM training)
- Run syntax checks and tests
- Finalize proof bundles with hashes

### LLM Factory
Creates and trains LLM instances:
- Spawn model specs (configurable layers, dimensions, heads)
- Train on custom corpora using LLMGPT Python/PyTorch
- Evaluate model quality
- Export trained weights to C++ for inference
- Maintain model registry with hashes and metrics

### Treasury
Central accounting:
- Track all costs and revenue per subsystem
- Calculate P&L and ROI
- Budget allocation based on historical performance
- Runway calculation (days until funds exhausted)

### Governance
Safety and policy enforcement:
- Action classification (SAFE, STANDARD, RISKY, CRITICAL, SELF_MODIFYING)
- Cost limits (daily and per-action)
- Human approval for critical actions
- Emergency halt with audit trail
- Simulation mode by default (no real money moves)

## Safety

**By default, the OS runs in SIMULATION mode.**
- No real payments are made
- No real trading positions are opened
- No production deployments occur
- All costs are estimated/simulated

To enable production features:
```bash
export MEMBRA_MODE=production
export STRIPE_SECRET_KEY=sk_...
export GATE_API_KEY=...
export GATE_API_SECRET=...
```

**Critical actions require human approval** even in production:
- Money movement
- Production deployment
- Model training over $50
- Self-modification of OS code

## License

MIT — Autonomous research prototype. No guaranteed income. See membra-core SECURITY.md before handling keys.
