import os
import json
import pandas as pd
import ast
from flask import Flask, request, jsonify, send_from_directory

# ── Setup ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

is_individual_country = None
try:
    from country_name_mapping import is_individual_country
except Exception as e:
    print(f"Warning: Could not import is_individual_country: {e}")
    is_individual_country = None

app = Flask(__name__, static_folder='static')

# ── Helper Functions ────────────────────────────────────────────────────────

def convert_nan_to_none(obj):
    """Recursively convert NaN and infinity values to None for JSON serialization"""
    if isinstance(obj, dict):
        return {k: convert_nan_to_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_nan_to_none(item) for item in obj]
    elif isinstance(obj, float):
        if pd.isna(obj):
            return None
        if obj == float('inf') or obj == float('-inf'):
            return None
        return obj
    return obj

# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(os.path.dirname(__file__), 'briefing_shareable.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/how-it-works')
def how_it_works():
    return send_from_directory(os.path.dirname(__file__), 'briefing_how_it_works.html')

@app.route('/api/briefing/countries')
def get_countries():
    """Get list of available countries with briefings"""
    try:
        document_df_path = os.path.join(BASE_DIR, 'public_documents_filtered.csv')
        if not os.path.exists(document_df_path):
            print("Error: public_documents_filtered.csv not found")
            return jsonify([])

        document_df = pd.read_csv(document_df_path)
        all_countries = document_df['CNTRY_SHORT_NAME'].unique()
        
        # Filter to individual countries if function available
        individual_countries = []
        if is_individual_country:
            for c in all_countries:
                try:
                    if is_individual_country(c):
                        individual_countries.append(c)
                except Exception:
                    # If filtering fails for a country, include it anyway
                    individual_countries.append(c)
        else:
            individual_countries = list(all_countries)
        
        return jsonify(sorted(individual_countries))
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Error in get_countries: {error_msg}")
        return jsonify([])

@app.route('/api/briefing/content/<country>')
def get_briefing_content(country):
    """Get the most recent briefing for a country"""
    try:
        import glob
        save_folder = "intermediary_outputs"
        
        # Find the most recent briefing file for this country
        pattern = f"{save_folder}/final_{country}_*_briefing_*.md"
        files = glob.glob(pattern)
        
        if not files:
            return jsonify({'text': None, 'generated': None}), 200
        
        latest_file = max(files, key=os.path.getctime)
        file_mtime = os.path.getmtime(latest_file)
        from datetime import datetime
        generated = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        return jsonify({'text': text, 'generated': generated})
    except Exception as e:
        import traceback
        return jsonify({'error': f"{str(e)}\n{traceback.format_exc()}"}), 500

@app.route('/api/briefing/project-names/<country>')
def get_project_names(country):
    """Get project names for a country from preprocessed PADs"""
    try:
        project_names = {}
        preprocessed_dir = "preprocessed_pads"
        country_dir = os.path.join(preprocessed_dir, country)
        
        if os.path.exists(country_dir):
            for filename in os.listdir(country_dir):
                if filename.endswith('_preprocessed.json'):
                    file_path = os.path.join(country_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            proj_id = data.get('metadata', {}).get('PROJ_ID_IB')
                            proj_name = data.get('structured_content', {}).get('project_overview', {}).get('project_name')
                            if proj_id and proj_name:
                                project_names[proj_id] = proj_name
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
        
        return jsonify(project_names)
    except Exception as e:
        import traceback
        print(f"Error in get_project_names: {traceback.format_exc()}")
        return jsonify({})

@app.route('/api/briefing/risks/<country>')
def get_briefing_risks(country):
    """Get all risk data for a country"""
    try:
        save_folder = "intermediary_outputs"
        
        def safe_parse_list(value):
            """Safely parse string representations of lists"""
            if pd.isna(value) or value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    parsed = ast.literal_eval(value)
                    return parsed if isinstance(parsed, list) else []
                except:
                    return []
            return []
        
        # Load country risks
        country_risks_path = f"{save_folder}/{country}_briefing_risks.csv"
        country_risks = []
        if os.path.exists(country_risks_path):
            try:
                df = pd.read_csv(country_risks_path)
                for _, row in df.iterrows():
                    risk_dict = row.to_dict()
                    for field in ['themes', 'keywords', 'locations']:
                        if field in risk_dict:
                            risk_dict[field] = safe_parse_list(risk_dict[field])
                    country_risks.append(convert_nan_to_none(risk_dict))
            except pd.errors.EmptyDataError:
                pass
        
        # Load PAD risks
        pad_risks_path = f"{save_folder}/{country}_pad_risks.csv"
        pad_risks = []
        if os.path.exists(pad_risks_path):
            try:
                df = pd.read_csv(pad_risks_path)
                pad_risks = [convert_nan_to_none(record) for record in df.to_dict('records')]
            except pd.errors.EmptyDataError:
                pass
        
        # Load implementation risks
        impl_risks_path = f"{save_folder}/{country}_implementation_realized_risks.csv"
        impl_risks = []
        if os.path.exists(impl_risks_path):
            try:
                df = pd.read_csv(impl_risks_path)
                impl_risks = [convert_nan_to_none(record) for record in df.to_dict('records')]
            except pd.errors.EmptyDataError:
                pass
        
        # Load risk mappings
        mappings_path = f"{save_folder}/{country}_implementation_realized_risks_mapped.csv"
        mappings = []
        if os.path.exists(mappings_path):
            try:
                df = pd.read_csv(mappings_path)
                mappings = [convert_nan_to_none(record) for record in df.to_dict('records')]
            except pd.errors.EmptyDataError:
                pass
        
        return jsonify({
            'country_risks': country_risks,
            'pad_risks': pad_risks,
            'impl_risks': impl_risks,
            'mappings': mappings
        })
    except Exception as e:
        import traceback
        return jsonify({'error': f"{str(e)}\n{traceback.format_exc()}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
