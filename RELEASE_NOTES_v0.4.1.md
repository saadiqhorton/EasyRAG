## What's New

**No Python prerequisite**  
EasyRAG now bundles its own Python runtime. Users no longer need to install Python first.

**Windows Support via WSL2**  
EasyRAG now runs on Windows 10/11 through WSL2 + Ubuntu. Install Ubuntu, run the install command, then access EasyRAG from your Windows browser at http://localhost:3000.

## Platform Support

| Platform | Status | Method |
|----------|--------|--------|
| Linux AMD64 | ✅ Supported | No-Docker install |
| Windows 10/11 | ✅ Supported | WSL2 + Ubuntu |
| macOS | ⏳ Coming soon | Use Docker for now |
| Docker | ✅ Supported | All platforms |

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/saadiqhorton/EasyRAG/main/install.sh | bash
bash ~/.easyrag/start.sh
Asset
easyrag-0.4.1-linux-amd64-packaged.tar.gz — Linux AMD64 bundle with prepackaged Python runtime and dependencies
