EasyRAG Release v0.3.1
======================

Platform: linux-amd64
Date: 2026-04-16
Size: 23 MB

CONTENTS
--------
This release bundle contains:
- backend/          Python FastAPI backend with all dependencies
- frontend/         Prebuilt Next.js standalone application
- .env.example      Configuration template
- start.sh          Start all services
- stop.sh           Stop all services
- doctor.sh         Diagnose issues
- uninstall.sh      Remove EasyRAG

INSTALL
-------
Run the one-line installer:
    curl -fsSL https://raw.githubusercontent.com/saadiqhorton/ER/main/install.sh | bash

Or manually extract and run:
    mkdir -p ~/.easyrag
    tar xzf easyrag-0.3.1-linux-amd64.tar.gz -C ~/.easyrag
    bash ~/.easyrag/start.sh

REQUIREMENTS
------------
- Python 3.11+
- curl

SERVICES
--------
- Frontend: http://localhost:3000
- API:      http://localhost:8000
- Qdrant:   http://localhost:6333

SUPPORT
-------
See README.md and INSTALL.md for detailed documentation.
