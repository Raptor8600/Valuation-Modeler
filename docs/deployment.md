# Deployment

## GitHub Pages: the documentation portal (not the app)

GitHub Pages serves static files only (HTML, CSS, JavaScript). It hosts `site/index.html`, the documentation and
verification portal (overview with headline results and live checks, verification report, worked example, formula
registry, assumptions register, methodology, provenance, limitations, known issues). It cannot run the interactive app:
the engine, the SEC/Yahoo data fetch, the workbook generator and Streamlit all need a Python server.

Turn it on once: repository **Settings → Pages → Source: GitHub Actions**. Every push to `main` then runs the tests and
verification, rebuilds `site/index.html` from the fresh report and publishes it. Optional: set a repository variable
`APP_URL` (Settings → Secrets and variables → Actions → Variables) to the Streamlit app's address so the portal links to it.
Build it locally with `python -m scripts.build_site` and open `site/index.html` in a browser.

## What needs a server

| Feature | Needs a Python server? | Needs internet egress? |
|---|---|---|
| Valuation engine, Logic, Assumptions, Checks pages | yes | no |
| Live ticker fetch (SEC EDGAR + Yahoo Finance) | yes | yes (sec.gov, data.sec.gov, query*.finance.yahoo.com) |
| Download .xlsx | yes | no |
| Replaying a saved snapshot | yes | no |
| Excel parity tests / verification report | yes, plus LibreOffice | no |

## Option 1: Streamlit Community Cloud (free)

1. Push this repository to GitHub (public, or private with Community Cloud access granted).
2. Go to https://share.streamlit.io → **Create app** → pick the repo, branch `main`, main file `app.py`.
3. No secrets are needed: each visitor types their own name and email for the SEC on the Live search page (it goes
   only to the SEC with their requests). Nothing secret is committed.
4. Deploy. Searches are kept in each visitor's browser session (My searches), not on the server; visitors download any they want to keep.

## Option 2: Docker on any host (Render, Fly.io, a VM)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```



## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
