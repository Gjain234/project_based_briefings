# FCV Portfolio Briefing Viewer (Shareable)

A read-only Flask application for viewing pre-generated FCV (Fragility, Conflict, and Violence) portfolio briefings, project risks, and implementation evidence.

## Features

- **Country Selection**: Browse briefings for all available countries
- **Portfolio Briefings**: View synthesized FCV risk assessments for country portfolios
- **Risk Details**: Explore country-level risks, project vulnerabilities (PAD), and implementation risks (ISR/Aide Memoires)
- **Risk Mappings**: See connections between implementation risks and source documents
- **Read-Only**: No generation or modification capabilities—perfect for sharing and viewing only

## Files

- `app_shareable.py`: Flask application with read-only endpoints
- `briefing_shareable.html`: Main UI with country selector and briefing viewer
- `briefing_how_it_works.html`: Tutorial and documentation
- `README_SHAREABLE.md`: This file

## Installation

### Requirements

- Python 3.8+
- Flask
- pandas

### Setup

1. Install dependencies:
   ```bash
   pip install flask pandas
   ```

2. Ensure the following data files exist in the parent directory:
   - `public_documents_filtered.csv` (for country list)
   - `intermediary_outputs/` folder with briefing files:
     - `{COUNTRY}_briefing_risks.csv`
     - `{COUNTRY}_pad_risks.csv`
     - `{COUNTRY}_implementation_realized_risks.csv`
     - `{COUNTRY}_implementation_realized_risks_mapped.csv`
     - `final_{COUNTRY}_*_briefing_*.md` (briefing markdown files)

3. (Optional) Add `country_name_mapping.py` to parent directory for country filtering

## Running the App

### Development Mode

```bash
python app_shareable.py
```

The app will start on `http://localhost:5000`

### Production Mode

Use a production WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 \
  -p app_shareable.py \
  --access-logfile - \
  --error-logfile -
```

Or with waitress:

```bash
pip install waitress
waitress-serve --host 0.0.0.0 --port 5000 app_shareable:app
```

## API Endpoints

All endpoints are read-only:

- `GET /` — Main briefing viewer UI
- `GET /how-it-works` — Tutorial and documentation
- `GET /health` — Health check
- `GET /api/briefing/countries` — List of available countries
- `GET /api/briefing/content/<country>` — Latest briefing markdown for country
- `GET /api/briefing/risks/<country>` — All risk data (country, PAD, implementation, mappings)

## Data Structure

### Country Risks

```json
{
  "risk_id": "DJI_R1",
  "description": "Political instability...",
  "themes": ["Political Stability", "Governance"],
  "keywords": ["Elections", "Uncertainty"]
}
```

### PAD Risks

```json
{
  "PROJ_ID_IB": "P123456",
  "risk_description": "Project exposed to...",
  "fcv_dimension": "Security and Rule of Law"
}
```

### Implementation Risks

```json
{
  "PROJ_ID_IB": "P123456",
  "risk_description": "Security incidents affecting...",
  "status": "Emerging"
}
```

### Risk Mappings

```json
{
  "PROJ_ID_IB": "P123456",
  "doc_type": "ISR",
  "risk_description": "Implementation challenges due to..."
}
```

## Customization

### Branding

Edit the header and footer in `briefing_shareable.html` to customize branding, logos, or disclaimers.

### Styling

CSS is embedded in the HTML files. To modify colors, fonts, or layout, edit the `<style>` sections.

### Data Paths

The app looks for data in:
- `intermediary_outputs/` — relative to the app or current working directory
- `public_documents_filtered.csv` — in parent directory

To change these paths, edit lines in `app_shareable.py`:

```python
document_df_path = os.path.join(...)
save_folder = "intermediary_outputs"
```

## Deployment

### Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY app_shareable.py briefing_shareable.html briefing_how_it_works.html ./

RUN pip install flask pandas

EXPOSE 5000

CMD ["python", "app_shareable.py"]
```

Build and run:

```bash
docker build -t fcv-briefing-viewer .
docker run -p 5000:5000 -v /path/to/data:/data fcv-briefing-viewer
```

### AWS / Azure / GCP

Deploy as:
- Cloud Run (GCP)
- App Service (Azure)
- Elastic Beanstalk (AWS)
- Any container or serverless platform that supports Python/Flask

## Security Considerations

- This app is read-only—no authentication required by default
- No API keys or credentials are exposed
- Data files should be managed separately from the app
- Consider restricting access via firewall, VPN, or reverse proxy in production

## Troubleshooting

### Countries dropdown is empty
- Check that `public_documents_filtered.csv` exists in the parent directory
- Verify `country_name_mapping.py` is available (optional, but needed for filtering)
- Check console for errors

### Briefing not loading
- Verify `intermediary_outputs/` folder exists and contains files for the selected country
- Check file naming: `final_{COUNTRY}_*_briefing_*.md`
- Look for error messages in browser console

### Risk tables are empty
- Ensure CSV files exist in `intermediary_outputs/`:
  - `{COUNTRY}_briefing_risks.csv`
  - `{COUNTRY}_pad_risks.csv`
  - `{COUNTRY}_implementation_realized_risks.csv`
  - `{COUNTRY}_implementation_realized_risks_mapped.csv`

## Support

For questions or issues:
1. Check the "How It Works" page for documentation
2. Review the API endpoints section above
3. Check browser console for JavaScript errors
4. Review Flask console output for backend errors

---

**Version**: 1.0  
**Last Updated**: March 2026  
**Status**: Read-only viewer for sharing briefings
