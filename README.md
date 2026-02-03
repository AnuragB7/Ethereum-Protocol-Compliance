# 🔍 LLM-Powered Ethereum Code Compliance Analysis Platform

<p align="center">
  <strong>Hybrid Property Graph RAG System with Automated PR Analysis</strong>
</p>

## 🎥 Demo Video

<p align="center">
  <a href="https://youtu.be/OZlg6TE-lNQ">
    <img src="https://img.youtube.com/vi/OZlg6TE-lNQ/maxresdefault.jpg" alt="Watch Demo" />
  </a>
</p>

<p align="center">
  <a href="https://youtu.be/OZlg6TE-lNQ">▶ Watch Full Demo on YouTube</a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#usage">Usage</a> •
  <a href="#ci-integration">CI Integration</a> •
  <a href="#api-reference">API</a>
</p>

---

## Overview

A comprehensive platform that automates Ethereum protocol compliance verification by combining **Property Graph databases** with **Large Language Models (LLMs)** and **Hybrid RAG** (Retrieval-Augmented Generation). The system analyzes codebases against Ethereum specifications (EIPs, ERCs) to identify compliance gaps, deviations, and potential security vulnerabilities.

### Problem Statement

As the Ethereum protocol evolves through EIPs and specification updates, ensuring that multiple client implementations (Geth, Nethermind, Besu, Reth, etc.) remain compliant becomes increasingly complex. This verification is traditionally manual, time-consuming, and error-prone.

### Solution

This platform provides:

- **Property Graph Construction** from codebases, capturing entities (functions, classes, interfaces) and their relationships
- **Hybrid Specification Search** using keyword + semantic search with Qdrant vector database
- **LLM-Powered Analysis** to identify compliance issues with detailed explanations
- **CI/CD Integration** via GitHub Actions for automated PR-level compliance checking

---

## Features

### Dual-Mode PR Analysis

| Mode | Speed | Description |
|------|-------|-------------|
| **Quick** | ~30 seconds | Diff-based analysis of changed files |
| **Deep** | ~2-5 minutes | Full Property Graph construction with relationship analysis |

### Multi-Language Support

- Go (Ethereum clients like Geth)
- Solidity (Smart contracts)
- Java (Besu client)
- TypeScript / JavaScript
- Python
- Vue / JSX / TSX

### Key Capabilities

- **Specification Management**: Index and manage Ethereum specifications (EIPs, ERCs, Yellow Paper)
- **Graph Visualization**: Interactive visualization of code entity relationships
- **Compliance Reports**: Detailed reports with severity levels (Critical, Warning, Info)
- **CI/CD Native**: GitHub Actions integration with automated PR comments
- **Multiple LLM Providers**: Support for OpenAI-compatible APIs and Anthropic Claude

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/ethereum-compliance-platform.git
cd ethereum-compliance-platform
