<div align="center">
  <br>
  <h1>⚡ AI-Powered Automotive & Insurance Market Intelligence Platform</h1>
  <p><strong>A Next-Generation Market Radar & Opportunity Scorer for TEAMWILL</strong></p>
  <p>
    <i>Built by Ahmed (Final Year PFE Project)</i>
  </p>
</div>

<hr>

## 🚀 Overview

This modern, full-stack intelligence platform acts as an automated "radar" for **TEAMWILL** (an ERP/leasing systems vendor). By autonomously scraping, analyzing, and synthesizing public customer reviews and automotive articles, the system detects critical market vulnerabilities (e.g., negative complaint spikes in competing insurance companies) and automatically flags them as **Sales Opportunities** for specific Teamwill ERP software modules.

## ✨ Core Features

*   **🌐 Automated Data Ingestion Pipeline:** High-throughput scrapers collecting real-world data from **Trustpilot**, **AutoScout24**, and industry **RSS Feeds**.
*   **🧠 LLM-Powered NLP Enrichment:** Uses large language models (Anthropic, Groq) to deduplicate, extract schemas, analyze sentiment, and normalize raw HTML data into structured insights.
*   **🎯 Opportunity Scorer:** An advanced mathematical pipeline that aggregates metrics to calculate a "Signal Strength" (Score 0-100). It actively identifies targets needing *Claims Management* or *Fleet & Service* ERPs based on their customer complaint heat.
*   **🤖 Generative Data Analyst:** Synthesizes the entire market into a cohesive, conversational summary using natural language generation.
*   **✨ Gen-Z/Neo-Brutalist Dashboard:** A highly interactive, reactive, glassmorphic frontend built with React & Vite. It surfaces priority targets using a striking, trend-forward aesthetic.

---

## 🛠️ Technology Stack

**Backend (API & Data Engineering):**
*   **Python 3.11** Core
*   **FastAPI** & **Uvicorn** for the REST API interface
*   **PostgreSQL 14** + **SQLAlchemy (ORM)** & **Alembic** for schema migrations
*   **ReportLab** for automated PDF brief generation

**Frontend (Dashboard):**
*   **React** + **TypeScript**
*   **Vite** (Build Tool & Proxy)
*   **TailwindCSS** + Custom Vanilla CSS for brutalist & glassmorphic styling
*   **React Query** (Data synchronization)
*   **Lucide React** (Icons)

---

## 🏗️ Architecture & Control Flow

The platform runs decoupled continuous extraction jobs which feed into the central Postgres database. The data is normalized and scored asynchronously.

1.  **Scraping Phase (`scripts/run_scraping_tasks.py`)**: Gathers raw HTML objects.
2.  **Parsing Phase (`scripts/run_parser_pipeline.py`)**: Converts raw data to domain records.
3.  **NLP Pipeline (`scripts/run_nlp_pipeline.py`)**: Calculates sentiment and extracts entities.
4.  **Analytics / Aggregation (`scripts/run_analytics.py`)**: Runs mathematical aggregations.
5.  *Orchestrated continuously by the Master Scheduler (`scripts/scheduler.py`).*

---

## 💻 Getting Started

### 1. Prerequisites
*   Windows 11 Setup (Recommended)
*   Python 3.11 & Node v20
*   PostgreSQL running locally on Port 5432.

### 2. Startup Command
We have bundled a global startup script that spins up both the **Uvicorn Backend** and **Vite Frontend** concurrently in separate terminal environments.

Just double-click or run:
```bat
start_project.bat
```

### 3. Accessing the Platform

*   **Dashboard UI:** [http://localhost:5173/ui/](http://localhost:5173/ui/)
*   **OpenAPI Documentation (Swagger):** [http://localhost:8099/docs](http://localhost:8099/docs)

---

## 🔒 Security & Environment Variables

Make sure you copy `.env.example` to `.env` and fill out your keys.

> [!WARNING]
> Ensure your Anthropic (`ANTHROPIC_API_KEY`) and Groq (`GROQ_API_KEY`) API keys are strictly stored in `.env`. **Never commit them**; the `.gitignore` has been updated to protect them against GitHub's Push Protection rules.

---

## 🎨 Note on Aesthetics

The frontend design language utilizes a **Gen-Z / Neo-Brutalist** aesthetic combined with Glassmorphism. Deep indigo hues, fluorescent neon highlights, and custom CSS filter overlays create an intentionally immersive, slightly chaotic, yet highly professional and engaging operational environment.
