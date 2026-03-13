# FCV Analytics Platform

This integrated platform now contains two powerful WBG FCV analysis tools:

## 🎯 Tools Available

### 1. FCV Project Screener (Original)
**Route:** `/` (homepage)

A tool for screening WBG project documents (PCNs, PADs) for FCV dynamics. Provides:
- Four-stage analysis process
- FCV risk extraction and dimension screening  
- Gap identification and mitigation recommendations
- Final recommendations note generation

### 2. FCV Portfolio Briefing Generator (NEW!)
**Route:** `/briefing`

Comprehensive FCV portfolio briefings using country risk analysis, PAD assessments, and implementation status. Provides:
- Country-level FCV risk intelligence from ICG/CrisisWatch + web search
- PAD susceptibility assessments
- Implementation risk extraction from ISRs and Aide Memoires
- Risk-aligned, sector-aligned, or custom category briefings

## 🚀 Getting Started

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Running the Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

## 📁 Project Structure

```
FCV-AGENT-main/
├── app.py                          # Flask application with both tools
├── index.html                      # FCV Project Screener UI
├── briefing.html                   # Portfolio Briefing Generator UI
├── static/
│   ├── briefing_styles.css        # Briefing generator styles
│   └── briefing.js                # Briefing generator JavaScript
├── background_docs.py              # FCV Guide documentation
├── prompts.json                    # Screener prompts (customizable)
│
# Briefing Generator Modules (prefixed with briefing_)
├── briefing_config.py             # Configuration and models
├── briefing_prompts.py            # System prompts for briefing generation
├── briefing_setup.py              # LLM client setup
├── main_briefing_generator.py     # Main briefing orchestration
├── generate_briefing.py           # Briefing generation logic
├── get_country_briefing.py        # Country risk extraction
├── get_briefing_risks.py          # Risk item extraction
├── get_pad_risks.py               # PAD stress testing
├── get_implementation_docs_risks.py  # Implementation risk extraction
├── get_icg_text.py                # ICG data fetching
├── preprocess_pads.py             # PAD preprocessing
├── country_name_mapping.py        # Country name normalization
├── document_utils.py              # PDF text extraction
│
# Data Files
├── country_ids.json               # Country ID mappings
├── public_documents_filtered.csv  # Document metadata (external)
├── joined_df_filtered.csv         # Document metadata (internal)
│
# Cache & Outputs
├── intermediary_outputs/          # Cached briefing data
└── preprocessed_pads/             # Cached PAD extractions
```

## 🎨 Design System

Both tools share the WBG design system:

- **Color Palette:** WBG Navy (#002244), WBG Blue (#009FDA), WBG Cyan (#47C4EB)
- **Typography:** Source Sans 3 (sans-serif), Source Serif 4 (serif)
- **Style:** Professional, institutional, accessible

## 🔧 Configuration

### Briefing Generator Configuration

Edit `briefing_config.py` to customize:

- **Models:** Choose between Anthropic Claude and Azure OpenAI
- **Internal/External Mode:** Toggle between internal WBG data and public data
- **Context Limits:** Adjust maximum input sizes
- **API Keys:** Set your API credentials

```python
# In briefing_config.py
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_COUNTRY_RISK_MODEL = "claude-sonnet-4-6"  # Complex tasks
ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5"  # Fast tasks
```

## 📊 API Endpoints

### FCV Project Screener
- `GET /` - Main screener interface
- `POST /chat` - Streaming analysis endpoint
- `GET /static/<path>` - Static assets

### Portfolio Briefing Generator  
- `GET /briefing` - Briefing generator interface
- `GET /api/briefing/countries` - List available countries
- `GET /api/briefing/last-scan/<country>` - Check last scan date
- `POST /api/briefing/generate` - Generate briefing (streaming)

## 🔒 Security Notes

**IMPORTANT:**
- Do not upload classified or confidential documents to either tool
- Both tools use external AI processing (Anthropic Claude)
- Review all AI-generated outputs before operational use
- Outputs may contain errors, omissions, or outdated information

## 📝 Caching Strategy (Briefing Generator)

The briefing generator uses intelligent caching:

| Data Type | Cache Level | Regenerates When |
|-----------|-------------|------------------|
| **Preprocessed PADs** | Document | Never (unless doc changes) |
| **Implementation Risks** | Document (by country) | Never (unless doc changes) |
| **Country Risks** | Country | User clicks "Regenerate with fresh news" |
| **PAD Stress Tests** | Country | Country risks regenerate |
| **Risk Mappings** | Country | Implementation/country risks change |
| **Final Briefing** | Country + params | Any input changes |

**First generation:** ~10-15 minutes  
**Subsequent generations:** ~2-3 minutes (cached data)  
**Fresh news update:** ~10 minutes (regenerates country risks only)

## 🤝 Contributing

When adding features:
1. Maintain the WBG design system consistency
2. Follow the existing code structure
3. Update this README with any new functionality
4. Test both tools to ensure no conflicts

## 📄 License

Internal World Bank Group tool. Not for public distribution.

---

**Last Updated:** March 9, 2026  
**Maintained by:** WBG FCV Analytics Unit
