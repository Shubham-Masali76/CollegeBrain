# 🧠 CollegeBrain

**The Ultimate 100% Accurate Admission Analyzer.**

CollegeBrain is an enterprise-grade admission intelligence engine built to help engineering students make data-driven decisions. Unlike traditional admission portals that rely on static data and outdated UI, CollegeBrain leverages an autonomous LLM-powered web scraper, dynamic fee calculations based on categories (OBC, SC, ST, etc.), and mathematical ROI rankings to find the perfect college.

---

## 🚀 God-Mode Features

- **Autonomous Agentic Web Scraper:** A background Python engine (`live_scraper.py`) that uses DuckDuckGo and Groq (Llama-3) / Gemini to silently crawl the internet, extracting live median placements, hostel fees, and infrastructure ratings.
- **Dynamic Category-Wise Fees:** Instantly calculates your exact tuition fees (e.g., slashing fees by 50% for OBC, or to 0% for SC/ST).
- **Mathematical ROI Algorithm:** Ranks colleges not by abstract government scores, but by the highest Median LPA relative to your budget and City PG costs.
- **Spot Round Predictor:** Intelligently calculates your probability of landing a seat via Institutional Quota / Spot Rounds even if you narrowly miss the CAP cutoff.
- **AI Ranking Justification:** Every college recommendation is accompanied by an AI-generated explanation detailing exactly *why* it was chosen for you.

---

## 🏗️ Architecture

### 1. Frontend (React + Vite + Tailwind CSS)
A stunning, dark-mode-first React application featuring framer-motion drag-and-drop preference lists.
- `App.jsx` handles all state, UI, and API integration.

### 2. Backend (FastAPI + SQLite + Python)
An insanely fast Python backend powered by FastAPI.
- `main.py`: The API and ROI mathematical engine.
- `database.py`: The relational SQLite schema.

### 3. Ingestion Engine (AI Scraping)
- `ingestion_engine.py`: Seed data injector for historical benchmarks.
- `live_scraper.py`: The live web crawler using `ddgs` and `groq` to parse messy HTML into strict JSON.

---

## ⚙️ Quick Start

### Prerequisites
- `Node.js` (for Frontend)
- `uv` (Fast Python Package Manager)

### Setup & Run
1. **Clone & Install Dependencies**
   ```bash
   cd CollegeBrain
   npm install
   cd backend
   uv sync
   ```

2. **Setup API Keys**
   Inside the `backend/` directory, create a `.env` file:
   ```env
   GROQ_API_KEY=your_groq_key
   GEMINI_API_KEY=your_gemini_key
   ```

3. **Initialize the Database**
   ```bash
   cd backend
   uv run python database.py
   uv run python ingestion_engine.py
   ```

4. **Start the API Server**
   ```bash
   cd backend
   uv run python main.py
   # Runs on http://localhost:8000
   ```

5. **Start the React UI**
   ```bash
   # From the root directory
   npm run dev
   # Runs on http://localhost:5173
   ```

---

## 👑 Royalty & Credits
**Architected and engineered by Shubham Masali.**

This system was designed from the ground up to solve the immense data fragmentation problem in Indian engineering admissions. All rights reserved.

---

## 🛡️ License
Built for precision. Built for students.  
