"""
Country to Timezone Mapping Utility

Uses pytz to map country names to timezone names.
"""

import pytz
from typing import Optional
import pycountry
import logging

logger = logging.getLogger(__name__)

# Common country name variations and their standard names
COUNTRY_NAME_ALIASES = {
    # Africa
    "ghana": "Ghana",
    "nigeria": "Nigeria",
    "kenya": "Kenya",
    "south africa": "South Africa",
    "egypt": "Egypt",
    "morocco": "Morocco",
    "tanzania": "Tanzania",
    "uganda": "Uganda",
    "ethiopia": "Ethiopia",
    "rwanda": "Rwanda",
    "senegal": "Senegal",
    "cameroon": "Cameroon",
    "côte d'ivoire": "Côte d'Ivoire",
    "ivory coast": "Côte d'Ivoire",
    
    # Europe
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "england": "United Kingdom",
    "france": "France",
    "germany": "Germany",
    "spain": "Spain",
    "italy": "Italy",
    "netherlands": "Netherlands",
    "belgium": "Belgium",
    "portugal": "Portugal",
    "switzerland": "Switzerland",
    "austria": "Austria",
    "poland": "Poland",
    "ireland": "Ireland",
    
    # Americas
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "canada": "Canada",
    "mexico": "Mexico",
    "brazil": "Brazil",
    "argentina": "Argentina",
    "colombia": "Colombia",
    "chile": "Chile",
    "peru": "Peru",
    
    # Asia
    "india": "India",
    "china": "China",
    "japan": "Japan",
    "south korea": "South Korea",
    "singapore": "Singapore",
    "malaysia": "Malaysia",
    "indonesia": "Indonesia",
    "thailand": "Thailand",
    "vietnam": "Vietnam",
    "philippines": "Philippines",
    "pakistan": "Pakistan",
    "bangladesh": "Bangladesh",
    "sri lanka": "Sri Lanka",
    "uae": "United Arab Emirates",
    "saudi arabia": "Saudi Arabia",
    "israel": "Israel",
    "turkey": "Turkey",
    
    # Oceania
    "australia": "Australia",
    "new zealand": "New Zealand",
}

# Country to primary timezone mapping (most common/capital timezone)
COUNTRY_TO_TIMEZONE = {
    # Africa
    "Ghana": "Africa/Accra",
    "Nigeria": "Africa/Lagos",
    "Kenya": "Africa/Nairobi",
    "South Africa": "Africa/Johannesburg",
    "Egypt": "Africa/Cairo",
    "Morocco": "Africa/Casablanca",
    "Tanzania": "Africa/Dar_es_Salaam",
    "Uganda": "Africa/Kampala",
    "Ethiopia": "Africa/Addis_Ababa",
    "Rwanda": "Africa/Kigali",
    "Senegal": "Africa/Dakar",
    "Cameroon": "Africa/Douala",
    "Côte d'Ivoire": "Africa/Abidjan",
    "Algeria": "Africa/Algiers",
    "Tunisia": "Africa/Tunis",
    "Libya": "Africa/Tripoli",
    "Sudan": "Africa/Khartoum",
    "Zambia": "Africa/Lusaka",
    "Zimbabwe": "Africa/Harare",
    "Botswana": "Africa/Gaborone",
    "Namibia": "Africa/Windhoek",
    "Mozambique": "Africa/Maputo",
    "Angola": "Africa/Luanda",
    "Democratic Republic of the Congo": "Africa/Kinshasa",
    "Congo": "Africa/Brazzaville",
    "Gabon": "Africa/Libreville",
    "Mali": "Africa/Bamako",
    "Burkina Faso": "Africa/Ouagadougou",
    "Niger": "Africa/Niamey",
    "Chad": "Africa/Ndjamena",
    "Madagascar": "Indian/Antananarivo",
    "Mauritius": "Indian/Mauritius",
    
    # Europe
    "United Kingdom": "Europe/London",
    "France": "Europe/Paris",
    "Germany": "Europe/Berlin",
    "Spain": "Europe/Madrid",
    "Italy": "Europe/Rome",
    "Netherlands": "Europe/Amsterdam",
    "Belgium": "Europe/Brussels",
    "Portugal": "Europe/Lisbon",
    "Switzerland": "Europe/Zurich",
    "Austria": "Europe/Vienna",
    "Poland": "Europe/Warsaw",
    "Ireland": "Europe/Dublin",
    "Sweden": "Europe/Stockholm",
    "Norway": "Europe/Oslo",
    "Denmark": "Europe/Copenhagen",
    "Finland": "Europe/Helsinki",
    "Greece": "Europe/Athens",
    "Czech Republic": "Europe/Prague",
    "Hungary": "Europe/Budapest",
    "Romania": "Europe/Bucharest",
    "Ukraine": "Europe/Kiev",
    "Russia": "Europe/Moscow",
    
    # Americas
    "United States": "America/New_York",
    "Canada": "America/Toronto",
    "Mexico": "America/Mexico_City",
    "Brazil": "America/Sao_Paulo",
    "Argentina": "America/Argentina/Buenos_Aires",
    "Colombia": "America/Bogota",
    "Chile": "America/Santiago",
    "Peru": "America/Lima",
    "Venezuela": "America/Caracas",
    "Ecuador": "America/Guayaquil",
    "Bolivia": "America/La_Paz",
    "Paraguay": "America/Asuncion",
    "Uruguay": "America/Montevideo",
    "Jamaica": "America/Jamaica",
    "Trinidad and Tobago": "America/Port_of_Spain",
    "Costa Rica": "America/Costa_Rica",
    "Panama": "America/Panama",
    "Cuba": "America/Havana",
    "Dominican Republic": "America/Santo_Domingo",
    "Puerto Rico": "America/Puerto_Rico",
    "Guatemala": "America/Guatemala",
    "Honduras": "America/Tegucigalpa",
    "Nicaragua": "America/Managua",
    "El Salvador": "America/El_Salvador",
    
    # Asia
    "India": "Asia/Kolkata",
    "China": "Asia/Shanghai",
    "Japan": "Asia/Tokyo",
    "South Korea": "Asia/Seoul",
    "Singapore": "Asia/Singapore",
    "Malaysia": "Asia/Kuala_Lumpur",
    "Indonesia": "Asia/Jakarta",
    "Thailand": "Asia/Bangkok",
    "Vietnam": "Asia/Ho_Chi_Minh",
    "Philippines": "Asia/Manila",
    "Pakistan": "Asia/Karachi",
    "Bangladesh": "Asia/Dhaka",
    "Sri Lanka": "Asia/Colombo",
    "Nepal": "Asia/Kathmandu",
    "Myanmar": "Asia/Yangon",
    "Cambodia": "Asia/Phnom_Penh",
    "Laos": "Asia/Vientiane",
    "United Arab Emirates": "Asia/Dubai",
    "Saudi Arabia": "Asia/Riyadh",
    "Israel": "Asia/Jerusalem",
    "Turkey": "Europe/Istanbul",
    "Iraq": "Asia/Baghdad",
    "Iran": "Asia/Tehran",
    "Kuwait": "Asia/Kuwait",
    "Qatar": "Asia/Qatar",
    "Bahrain": "Asia/Bahrain",
    "Oman": "Asia/Muscat",
    "Jordan": "Asia/Amman",
    "Lebanon": "Asia/Beirut",
    "Hong Kong": "Asia/Hong_Kong",
    "Taiwan": "Asia/Taipei",
    "Mongolia": "Asia/Ulaanbaatar",
    "Kazakhstan": "Asia/Almaty",
    "Uzbekistan": "Asia/Tashkent",
    "Afghanistan": "Asia/Kabul",
    
    # Oceania
    "Australia": "Australia/Sydney",
    "New Zealand": "Pacific/Auckland",
    "Fiji": "Pacific/Fiji",
    "Papua New Guinea": "Pacific/Port_Moresby",
}


def normalize_country_name(country: str) -> Optional[str]:
    """
    Normalize a country name to its standard form.
    
    Args:
        country: Country name in any case/format
        
    Returns:
        Standardized country name or None if not found
    """
    if not country:
        return None
    
    # Clean and lowercase the input
    country_lower = country.strip().lower()
    
    # Check aliases first
    if country_lower in COUNTRY_NAME_ALIASES:
        return COUNTRY_NAME_ALIASES[country_lower]
    
    # Check direct match (case-insensitive) in our mapping
    for standard_name in COUNTRY_TO_TIMEZONE.keys():
        if standard_name.lower() == country_lower:
            return standard_name
    
    # Try pycountry for additional lookups
    try:
        # Try by name
        country_obj = pycountry.countries.get(name=country)
        if country_obj:
            return country_obj.name
        
        # Try by common name
        country_obj = pycountry.countries.get(common_name=country)
        if country_obj:
            return country_obj.name
        
        # Try fuzzy search
        results = pycountry.countries.search_fuzzy(country)
        if results:
            return results[0].name
    except (LookupError, AttributeError):
        pass
    
    logger.warning(f"Could not normalize country name: {country}")
    return None


def get_timezone_for_country(country: str) -> Optional[str]:
    """
    Get the primary timezone for a given country.
    
    Args:
        country: Country name
        
    Returns:
        pytz timezone name or None if not found
    """
    if not country:
        logger.warning("No country provided for timezone lookup")
        return None
    
    # First, normalize the country name
    standard_name = normalize_country_name(country)
    
    if not standard_name:
        logger.warning(f"Could not normalize country: {country}")
        return None
    
    # Look up timezone
    if standard_name in COUNTRY_TO_TIMEZONE:
        tz_name = COUNTRY_TO_TIMEZONE[standard_name]
        # Verify it's a valid pytz timezone
        if tz_name in pytz.all_timezones:
            return tz_name
        else:
            logger.error(f"Invalid timezone in mapping: {tz_name}")
            return None
    
    logger.warning(f"No timezone mapping for country: {standard_name}")
    return None


def get_timezone_object(country: str) -> Optional[pytz.tzinfo.BaseTzInfo]:
    """
    Get a pytz timezone object for a country.
    
    Args:
        country: Country name
        
    Returns:
        pytz timezone object or None
    """
    tz_name = get_timezone_for_country(country)
    if tz_name:
        return pytz.timezone(tz_name)
    return None


# Example usage and testing
if __name__ == "__main__":
    test_countries = [
        "Ghana",
        "ghana",
        "GHANA",
        "Nigeria",
        "UK",
        "United States",
        "usa",
        "India",
        "Unknown Country",
        None,
        "",
    ]
    
    for country in test_countries:
        tz = get_timezone_for_country(country)
        print(f"{country!r} -> {tz}")
