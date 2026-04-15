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


# Maps canonical country names to name variations used in ACLED data
# Covers the canonical form from country_ids.json (the right side of COUNTRY_NAME_MAPPING)
ACLED_NAME_VARIATIONS = {
    "Afghanistan": ["Afghanistan"],
    "Albania": ["Albania"],
    "Algeria": ["Algeria"],
    "Angola": ["Angola"],
    "Armenia": ["Armenia"],
    "Azerbaijan": ["Azerbaijan"],
    "Bahrain": ["Bahrain"],
    "Bangladesh": ["Bangladesh"],
    "Belarus": ["Belarus"],
    "Benin": ["Benin"],
    "Bosnia And Herzegovina": ["Bosnia and Herzegovina"],
    "Burundi": ["Burundi"],
    "Burkina Faso": ["Burkina Faso"],
    "Cameroon": ["Cameroon"],
    "Central African Republic": ["Central African Republic"],
    "Chad": ["Chad"],
    "Colombia": ["Colombia"],
    "Comoros Islands": ["Comoros"],
    "Croatia": ["Croatia"],
    "Democratic Republic of Congo": ["Democratic Republic of Congo", "Democratic Republic of the Congo"],
    "Djibouti": ["Djibouti"],
    "Egypt": ["Egypt"],
    "Eritrea": ["Eritrea"],
    "Eswatini": ["Eswatini", "Swaziland"],
    "Ethiopia": ["Ethiopia"],
    "Fiji": ["Fiji"],
    "Gabon": ["Gabon"],
    "Georgia": ["Georgia"],
    "Ghana": ["Ghana"],
    "Guinea": ["Guinea"],
    "Guinea-Bissau": ["Guinea-Bissau"],
    "Haiti": ["Haiti"],
    "Honduras": ["Honduras"],
    "Iran": ["Iran"],
    "Iraq": ["Iraq"],
    "Israel/Palestine": ["Israel", "Palestine"],
    "Jordan": ["Jordan"],
    "Kazakhstan": ["Kazakhstan"],
    "Kenya": ["Kenya"],
    "Kosovo": ["Kosovo"],
    "Kuwait": ["Kuwait"],
    "Kyrgyzstan": ["Kyrgyzstan"],
    "Lebanon": ["Lebanon"],
    "Lesotho": ["Lesotho"],
    "Liberia": ["Liberia"],
    "Libya": ["Libya"],
    "Madagascar": ["Madagascar"],
    "Malawi": ["Malawi"],
    "Mali": ["Mali"],
    "Mauritania": ["Mauritania"],
    "Moldova": ["Moldova"],
    "Mongolia": ["Mongolia"],
    "Montenegro": ["Montenegro"],
    "Morocco": ["Morocco"],
    "Mozambique": ["Mozambique"],
    "Myanmar": ["Myanmar"],
    "Nepal": ["Nepal"],
    "Niger": ["Niger"],
    "Nigeria": ["Nigeria"],
    "North Macedonia": ["North Macedonia"],
    "Oman": ["Oman"],
    "Pakistan": ["Pakistan"],
    "Qatar": ["Qatar"],
    "Republic of Congo": ["Republic of the Congo", "Congo"],
    "Rwanda": ["Rwanda"],
    "Saudi Arabia": ["Saudi Arabia"],
    "Senegal": ["Senegal"],
    "Serbia": ["Serbia"],
    "Sierra Leone": ["Sierra Leone"],
    "Somalia": ["Somalia", "Federal Republic of Somalia"],
    "South Africa": ["South Africa"],
    "South Sudan": ["South Sudan"],
    "Sudan": ["Sudan"],
    "Syria": ["Syria"],
    "Tajikistan": ["Tajikistan"],
    "Tanzania": ["Tanzania"],
    "Timor-Leste": ["Timor-Leste"],
    "Togo": ["Togo"],
    "Tunisia": ["Tunisia"],
    "Turkmenistan": ["Turkmenistan"],
    "Türkiye": ["Turkey", "Türkiye"],
    "Uganda": ["Uganda"],
    "Ukraine": ["Ukraine"],
    "Uzbekistan": ["Uzbekistan"],
    "Yemen": ["Yemen"],
    "Zambia": ["Zambia"],
    "Zimbabwe": ["Zimbabwe"],
}


def check_acled_country_match(acled_country_name, target_country_name):
    """
    Check if an ACLED country name matches a target country after normalization.
    Handles fuzzy matching through ACLED_NAME_VARIATIONS.
    
    Args:
        acled_country_name: Country name as it appears in ACLED data
        target_country_name: Target country name (from user selection or WB data)
        
    Returns:
        bool: True if the names refer to the same country
    """
    if not acled_country_name or not target_country_name:
        return False
    
    acled_lower = str(acled_country_name).lower().strip()
    target_lower = str(target_country_name).lower().strip()
    
    # Exact match first
    if acled_lower == target_lower:
        return True
    
    # Check canonical name from ACLED_NAME_VARIATIONS
    canonical_target = get_country_id_key(target_country_name) or target_country_name
    canonical_variations = ACLED_NAME_VARIATIONS.get(canonical_target, [])
    
    for variation in canonical_variations:
        if acled_lower == variation.lower():
            return True
    
    # Reverse lookup: if target_country_name is in ACLED_NAME_VARIATIONS as a value,
    # find its key and check other variations
    for canonical, variations in ACLED_NAME_VARIATIONS.items():
        if target_lower in [v.lower() for v in variations]:
            for variation in variations:
                if acled_lower == variation.lower():
                    return True
            break
    
    return False
