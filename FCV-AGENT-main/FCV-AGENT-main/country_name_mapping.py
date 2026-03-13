"""
Mapping between World Bank CNTRY_SHORT_NAME values and country_ids.json keys.
This handles cases where country names differ slightly between the two sources.
"""

# Maps World Bank CNTRY_SHORT_NAME -> country_ids.json key
COUNTRY_NAME_MAPPING = {
    # Exact matches (included for completeness)
    "Afghanistan": "Afghanistan",
    "Albania": "Albania",
    "Algeria": "Algeria",
    "Angola": "Angola",
    "Argentina": "Argentina",
    "Armenia": "Armenia",
    "Azerbaijan": "Azerbaijan",
    "Bahrain": "Bahrain",
    "Bangladesh": "Bangladesh",
    "Benin": "Benin",
    "Bolivia": "Bolivia",
    "Burundi": "Burundi",
    "Cambodia": "Cambodia",
    "Cameroon": "Cameroon",
    "Chad": "Chad",
    "Chile": "Chile",
    "China": "China",
    "Colombia": "Colombia",
    "Djibouti": "Djibouti",
    "Ecuador": "Ecuador",
    "Eritrea": "Eritrea",
    "Eswatini": "Eswatini",
    "Ethiopia": "Ethiopia",
    "Fiji": "Fiji",
    "Gabon": "Gabon",
    "Georgia": "Georgia",
    "Ghana": "Ghana",
    "Guatemala": "Guatemala",
    "Guinea": "Guinea",
    "Guyana": "Guyana",
    "Haiti": "Haiti",
    "Honduras": "Honduras",
    "India": "India",
    "Indonesia": "Indonesia",
    "Jamaica": "Jamaica",
    "Jordan": "Jordan",
    "Kazakhstan": "Kazakhstan",
    "Kenya": "Kenya",
    "Kosovo": "Kosovo",
    "Kyrgyz Republic": "Kyrgyzstan",
    "Lebanon": "Lebanon",
    "Lesotho": "Lesotho",
    "Liberia": "Liberia",
    "Libya": "Libya",
    "Madagascar": "Madagascar",
    "Malawi": "Malawi",
    "Malaysia": "Malaysia",
    "Maldives": "Maldives",
    "Mali": "Mali",
    "Mauritania": "Mauritania",
    "Mexico": "Mexico",
    "Moldova": "Moldova",
    "Mongolia": "Mongolia",
    "Montenegro": "Montenegro",
    "Morocco": "Morocco",
    "Mozambique": "Mozambique",
    "Myanmar": "Myanmar",
    "Nepal": "Nepal",
    "Nicaragua": "Nicaragua",
    "Niger": "Niger",
    "Nigeria": "Nigeria",
    "Pakistan": "Pakistan",
    "Papua New Guinea": "Papua New Guinea",
    "Paraguay": "Paraguay",
    "Peru": "Peru",
    "Philippines": "Philippines",
    "Rwanda": "Rwanda",
    "Senegal": "Senegal",
    "Serbia": "Serbia",
    "Solomon Islands": "Solomon Islands",
    "South Sudan": "South Sudan",
    "Sri Lanka": "Sri Lanka",
    "Sudan": "Sudan",
    "Tajikistan": "Tajikistan",
    "Tanzania": "Tanzania",
    "Thailand": "Thailand",
    "Timor-Leste": "Timor-Leste",
    "Togo": "Togo",
    "Tonga": "Tonga",
    "Tunisia": "Tunisia",
    "Turkmenistan": "Turkmenistan",
    "Uganda": "Uganda",
    "Ukraine": "Ukraine",
    "Uzbekistan": "Uzbekistan",
    "Vanuatu": "Vanuatu",
    "Zambia": "Zambia",
    "Zimbabwe": "Zimbabwe",
    
    # Name variations requiring mapping
    "Bosnia and Herzegovina": "Bosnia And Herzegovina",
    "Central African Republic": "Central African Republic",
    "Congo, Democratic Republic of": "Democratic Republic of Congo",
    "Congo, Republic of": "Republic of Congo",
    "Cote d'Ivoire": "Côte d'Ivoire",
    "Dominican Republic": "Dominican Republic",
    "Egypt, Arab Republic of": "Egypt",
    "El Salvador": "El Salvador",
    "Gambia, The": "Gambia",
    "Guinea-Bissau": "Guinea-Bissau",
    "Iran, Islamic Republic of": "Iran",
    "Iraq": "Iraq",
    "Lao People's Democratic Republic": None,  # Not in country_ids
    "North Macedonia": "North Macedonia",
    "Sao Tome and Principe": "Sao Tome and Principe",
    "Sierra Leone": "Sierra Leone",
    "Somalia, Federal Republic of": "Somalia",
    "South Africa": "South Africa",
    "Syrian Arab Republic": "Syria",
    "Trinidad and Tobago": "Trinidad and Tobago",
    "Turkiye": "Türkiye",
    "West Bank and Gaza": "Israel/Palestine",
    "Yemen, Republic of": "Yemen",
    
    # Countries in CNTRY_SHORT_NAME not in country_ids (mapped to None)
    "Marshall Islands": None,
    "Kiribati": None,
    "Brazil": "Brazil",
    "St Maarten": None,
    "Seychelles": None,
    "Dominica": None,
    "Micronesia, Federated States of": None,
    "Samoa": None,
    "Cabo Verde": None,
    "Bhutan": None,
    "Burkina Faso": "Burkina Faso",
    "Namibia": None,
    "Comoros": "Comoros Islands",
    "Costa Rica": None,
    "Belize": None,
    "Botswana": None,
    "Grenada": None,
    "Mauritius": None,
    "Barbados": None,
    "Belarus": "Belarus",
    "Bulgaria": None,
    "Poland": None,
    "Estonia": None,
    "Malta": None,
    "Slovak Republic": None,
    "Italy": None,
    "Saudi Arabia": "Saudi Arabia",
    "Oman": "Oman",
    "Kuwait": "Kuwait",
    "Qatar": "Qatar",
    "United Arab Emirates": None,
    "Croatia": "Croatia",
    "Romania": None,
    "St. Vincent and the Grenadines": None,
    "St. Lucia": None,
    "Suriname": None,
    "Uruguay": None,
    "Panama": None,
    "Viet Nam": None,
    "Russian Federation": None,
    
    # Regional groupings (not individual countries)
    "Eastern and Southern Africa": None,
    "Western and Central Africa": None,
    "East Asia and Pacific": None,
    "Horn of Africa": None,
    "Caribbean": None,
    "Southern Africa": None,
    "World": None,
    "South Asia": None,
    "Central Asia": None,
    "Latin America and Caribbean": None,
    "DRC - Angola": None,
    "Western Balkans": None,
    "Pacific 2": None,
    "Middle East and North Africa": None,
    "Multi-Regional": None,
    "Europe and Central Asia": None,
    "Mashreq": None,
    "Pacific 1": None,
    "Central Africa": None,
    "Southwest Indian Ocean": None,
    "Maghreb": None,
    "Central America": None,
    "Africa": None,
    "Maldives, Nepal, Sri Lanka": None,
    "West Africa I": None,
    "Gulf Cooperation Council": None,
    "East Africa II": None,
    "Caucasus": None,
    "Southern Cone": None,
    "West Africa II": None,
    "Bangladesh and Bhutan": None,
    "EU Accession Countries": None,
    "OECS Countries": None,
}


def get_country_id_key(cntry_short_name):
    """
    Convert a World Bank CNTRY_SHORT_NAME to a country_ids.json key.
    
    Args:
        cntry_short_name: Country name from World Bank data
        
    Returns:
        str or None: Corresponding key from country_ids.json, or None if not mapped
    """
    return COUNTRY_NAME_MAPPING.get(cntry_short_name)


def is_individual_country(cntry_short_name):
    """
    Check if the CNTRY_SHORT_NAME represents an individual country (not a region).
    
    Args:
        cntry_short_name: Country name from World Bank data
        
    Returns:
        bool: True if it's an individual country with a mapping, False otherwise
    """
    mapped_name = COUNTRY_NAME_MAPPING.get(cntry_short_name)
    return mapped_name is not None


def get_possible_wb_country_names(country_ids_key):
    """ 
    Get all possible World Bank CNTRY_SHORT_NAME values that correspond to a country_ids.json key.
    This allows flexible filtering of the document dataframe.
    
    Args:
        country_ids_key: Country name from country_ids.json (e.g., "Somalia", "Kyrgyzstan")
        
    Returns:
        list: All possible CNTRY_SHORT_NAME values that map to this country
    """
    # Reverse lookup: find all CNTRY_SHORT_NAME keys that map to this country_ids key
    possible_names = [
        wb_name for wb_name, mapped_name in COUNTRY_NAME_MAPPING.items()
        if mapped_name == country_ids_key
    ]
    
    # Also include the country_ids_key itself in case it matches directly
    if country_ids_key not in possible_names:
        possible_names.append(country_ids_key)
    
    return possible_names
