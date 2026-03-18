# Contributing to Ethereum Protocol Compliance

Thank you for your interest in contributing! This project uses LLM-powered Hybrid Property Graph RAG to analyze Ethereum client codebases for protocol compliance. We welcome contributions of all kinds.

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/AnuragB7/Ethereum-Protocol-Compliance/issues) to report bugs or request features
- Include steps to reproduce, expected vs actual behavior, and your environment details
- Check existing issues before creating a new one

### Submitting Changes

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create a branch** from the appropriate base branch:
   - `feature/backend` for backend changes
   - `feature/frontend` for frontend changes
   - `main` for documentation-only changes
4. **Make your changes** following the guidelines below
5. **Test** your changes locally
6. **Commit** with a clear, descriptive message (see commit conventions below)
7. **Push** to your fork and open a **Pull Request**

### Branch Structure

| Branch | Purpose |
|--------|---------|
| `main` | Documentation, README, architecture diagrams |
| `feature/backend` | FastAPI backend, LlamaIndex indexer, parsers, API routes |
| `feature/frontend` | Next.js frontend, React components, UI |

### Development Setup

#### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your OPENAI_API_KEY and QDRANT_URL

uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Code Guidelines

- **Python**: Follow PEP 8, use type hints where practical
- **TypeScript/React**: Use functional components, TypeScript interfaces for props
- **Naming**: Use descriptive variable and function names
- **Comments**: Add comments only where logic isn't self-evident

### Commit Message Convention

Use conventional commit format:

```
type: short description

Optional longer description
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Examples:
- `feat: add Merkle tree incremental ingestion`
- `fix: handle empty codebase upload gracefully`
- `docs: update API endpoint documentation`

### What We're Looking For

- Support for additional programming languages in the code parser
- Improved graph visualization and interaction
- Better compliance analysis prompts and strategies
- Performance optimizations for large codebases
- Test coverage improvements
- Documentation improvements

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
