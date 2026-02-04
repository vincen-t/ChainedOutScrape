# LinkedIn Network Scraper

This script logs into LinkedIn and exports your network connections with a best-effort guess at each person's current employer (parsed from the connection headline).

> **Note**: Use this responsibly and make sure it aligns with LinkedIn's terms and your local policies.

## Requirements

- Python 3.10+
- Playwright

Install dependencies:

```bash
pip install -r requirements.txt
python -m playwright install
```

## Usage

Set credentials via environment variables:

```bash
export LINKEDIN_USERNAME="you@example.com"
export LINKEDIN_PASSWORD="your_password"
```

Run the scraper:

```bash
python linkedin_network_scraper.py --output connections.json
```

Optional flags:

```bash
python linkedin_network_scraper.py --headless false --output connections.json
```

The output JSON includes:

- `name`
- `headline`
- `employer` (best-effort parsed)

