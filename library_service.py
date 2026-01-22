"""
Library service for managing categories and items.
"""

import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from models import LibraryCategory, LibraryItem, ScenarioItem, PricingMode, AIUFactors
from storage_new import LIBRARY_CATEGORIES_FILE, LIBRARY_ITEMS_FILE, ensure_directories


# Alias mapping for search/suggestions (maps alternative names to canonical item codes)
ITEM_ALIAS_MAP = {
    "CIRCUITO CERRADO": "SEC-CCTV",
    "CCTV": "SEC-CCTV",
    "CERTIFICACIÓN RETIE": "ENG-RETIE",
    "CERTIFICACION RETIE": "ENG-RETIE",
    "ESTUDIO DE CONEXIÓN Y PROTECCIONES": "SUB-STUDY-INT",
    "ESTUDIO DE CONEXION Y PROTECCIONES": "SUB-STUDY-INT",
    "ESTUDIOS DE CONEXIÓN": "SUB-STUDY-INT",
    "ESTUDIOS DE CONEXION": "SUB-STUDY-INT",
    "ZANJAS PARA CABLEADO": "EBOS-TRNCH",
    "ZANJAS PARA CABLEADO Y DUCTOS": "EBOS-TRNCH",
    "INGENIERÍA DE DETALLE, DISEÑO Y PUESTA EN MARCHA": "ENG-DETAIL",
    "INGENIERIA DE DETALLE, DISEÑO Y PUESTA EN MARCHA": "ENG-DETAIL",
}


def resolve_item_code_alias(search_term: str) -> Optional[str]:
    """
    Resolve search term to canonical item code via alias mapping.
    
    Args:
        search_term: The search term (item name or code)
    
    Returns:
        Canonical item code if alias found, None otherwise
    """
    search_upper = search_term.upper().strip()
    return ITEM_ALIAS_MAP.get(search_upper)


def load_library_categories() -> List[LibraryCategory]:
    """Load all library categories. Creates fixture file if it doesn't exist."""
    ensure_directories()
    if not LIBRARY_CATEGORIES_FILE.exists():
        # Create default fixture file
        default_categories = [
            {"category_code":"PV-MOD","name_es":"Módulos","name_en":"Modules","ordering":10},
            {"category_code":"PV-INV","name_es":"Inversores","name_en":"Inverters","ordering":20},
            {"category_code":"PV-ESS","name_es":"Almacenamiento (BESS)","name_en":"Energy Storage (BESS)","ordering":30},
            {"category_code":"PV-SBOS","name_es":"SBOS (Estructuras / Trackers)","name_en":"SBOS (Structural / Trackers)","ordering":40},
            {"category_code":"PV-EBOS","name_es":"EBOS (Eléctrico)","name_en":"EBOS (Electrical BOS)","ordering":50},
            {"category_code":"PV-CIV","name_es":"Obra civil y preparación de sitio","name_en":"Civil Works & Site Prep","ordering":60},
            {"category_code":"PV-INST","name_es":"Instalación y construcción","name_en":"Installation & Construction","ordering":70},
            {"category_code":"PV-SUB","name_es":"Subestación e Interconexión","name_en":"Substation & Interconnection","ordering":80},
            {"category_code":"PV-SCADA","name_es":"SCADA / Comunicaciones / Seguridad","name_en":"SCADA / Comms / Security","ordering":90},
            {"category_code":"PV-ENG","name_es":"Ingeniería, permisos y estudios","name_en":"Engineering, Permits & Studies","ordering":100},
            {"category_code":"PV-DEV","name_es":"Desarrollo / Administración del proyecto","name_en":"Development / Project Management","ordering":110},
            {"category_code":"PV-OTH","name_es":"Otros / Contingencias","name_en":"Other / Contingencies","ordering":120},
            {"category_code":"LAND","name_es":"Tierra / Predios","name_en":"Land","ordering":130}
        ]
        with open(LIBRARY_CATEGORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_categories, f, indent=2, ensure_ascii=False)
        return [LibraryCategory.from_dict(item) for item in default_categories]
    try:
        with open(LIBRARY_CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [LibraryCategory.from_dict(item) for item in data]
    except (json.JSONDecodeError, IOError):
        return []


def save_library_categories(categories: List[LibraryCategory]):
    """Save library categories."""
    ensure_directories()
    data = [cat.to_dict() for cat in categories]
    with open(LIBRARY_CATEGORIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_library_items() -> List[LibraryItem]:
    """Load all library items."""
    ensure_directories()
    if not LIBRARY_ITEMS_FILE.exists():
        return []
    try:
        with open(LIBRARY_ITEMS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [LibraryItem.from_dict(item) for item in data]
    except (json.JSONDecodeError, IOError):
        return []


def save_library_items(items: List[LibraryItem]):
    """Save library items."""
    ensure_directories()
    data = [item.to_dict() for item in items]
    with open(LIBRARY_ITEMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_category_by_code(category_code: str) -> Optional[LibraryCategory]:
    """Get a category by its code."""
    categories = load_library_categories()
    return next((cat for cat in categories if cat.category_code == category_code), None)


def get_item_by_code(item_code: str) -> Optional[LibraryItem]:
    """
    Get an item by its code (case-insensitive).
    Also checks alias mapping for search terms.
    """
    items = load_library_items()
    item_code_lower = item_code.lower()
    
    # First check alias mapping
    alias_code = resolve_item_code_alias(item_code)
    if alias_code:
        item_code_lower = alias_code.lower()
    
    return next((item for item in items if item.item_code.lower() == item_code_lower), None)


def validate_item_code_unique(item_code: str, exclude_item_code: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate that an item code is unique (case-insensitive).
    Returns (is_valid, error_message).
    """
    items = load_library_items()
    item_code_lower = item_code.lower()
    
    for item in items:
        if item.item_code.lower() == item_code_lower:
            if exclude_item_code and item.item_code.lower() == exclude_item_code.lower():
                continue  # Skip the item being edited
            return False, f"El código '{item_code}' ya existe (case-insensitive). Código existente: '{item.item_code}'"
    
    return True, None


def create_library_category(category: LibraryCategory) -> LibraryCategory:
    """Create a new library category."""
    categories = load_library_categories()
    categories.append(category)
    save_library_categories(categories)
    return category


def update_library_category(category_code: str, updated_category: LibraryCategory):
    """Update a library category."""
    categories = load_library_categories()
    for i, cat in enumerate(categories):
        if cat.category_code == category_code:
            categories[i] = updated_category
            save_library_categories(categories)
            return
    raise ValueError(f"Category {category_code} not found")


def delete_library_category(category_code: str):
    """Delete a library category."""
    categories = load_library_categories()
    categories = [cat for cat in categories if cat.category_code != category_code]
    save_library_categories(categories)
    
    # Also remove items in this category
    items = load_library_items()
    items = [item for item in items if item.default_category_code != category_code]
    save_library_items(items)


def create_library_item(item: LibraryItem) -> LibraryItem:
    """Create a new library item with validation."""
    # Validate unique code
    is_valid, error_msg = validate_item_code_unique(item.item_code)
    if not is_valid:
        raise ValueError(error_msg)
    
    items = load_library_items()
    items.append(item)
    save_library_items(items)
    return item


def update_library_item(item_code: str, updated_item: LibraryItem):
    """Update a library item with validation."""
    # Validate unique code (excluding current item)
    is_valid, error_msg = validate_item_code_unique(updated_item.item_code, exclude_item_code=item_code)
    if not is_valid:
        raise ValueError(error_msg)
    
    items = load_library_items()
    item_code_lower = item_code.lower()
    for i, item in enumerate(items):
        if item.item_code.lower() == item_code_lower:
            items[i] = updated_item
            save_library_items(items)
            return
    raise ValueError(f"Item {item_code} not found")


def delete_library_item(item_code: str):
    """Delete a library item."""
    items = load_library_items()
    item_code_lower = item_code.lower()
    items = [item for item in items if item.item_code.lower() != item_code_lower]
    save_library_items(items)


def get_items_by_category(category_code: str) -> List[LibraryItem]:
    """Get all items for a category."""
    items = load_library_items()
    return [item for item in items if item.default_category_code == category_code]


def add_item_from_library(library_item_code: str, scenario) -> Optional[object]:
    """
    Add an item from library to a scenario.
    Returns the created ScenarioItem or None if library item not found.
    """
    library_item = get_item_by_code(library_item_code)
    if not library_item:
        return None
    
    # Create scenario item from library item
    scenario_item = ScenarioItem(
        item_id=str(uuid.uuid4()),
        item_code=library_item.item_code,
        name=library_item.name_es,  # Use Spanish name
        category_code=library_item.default_category_code,
        description=library_item.description,
        unit=library_item.default_unit,
        qty=0.0,
        pricing_mode=PricingMode.UNIT,
        price=0.0,
        vat_rate=library_item.default_vat_rate * 100.0,  # Convert to percentage
        client_pays=False,
        aiu_factors=AIUFactors(
            admin_factor=0.0 if not library_item.aiu_applicable else 100.0,
            imprev_factor=0.0 if not library_item.aiu_applicable else 100.0,
            util_factor=0.0 if not library_item.aiu_applicable else 100.0
        ),
        order=len(scenario.items)
    )
    
    return scenario_item


def save_item_to_library(scenario_item: ScenarioItem) -> LibraryItem:
    """
    Save a scenario item to the library.
    Returns the created LibraryItem.
    """
    # Check if code already exists
    existing = get_item_by_code(scenario_item.item_code)
    if existing:
        raise ValueError(f"El código '{scenario_item.item_code}' ya existe en la biblioteca")
    
    library_item = LibraryItem(
        item_code=scenario_item.item_code,
        name_es=scenario_item.name,
        name_en=scenario_item.name,  # Use same name for English
        description=scenario_item.description,
        default_unit=scenario_item.unit,
        default_vat_rate=scenario_item.vat_rate / 100.0,  # Convert from percentage
        aiu_applicable=scenario_item.aiu_factors.admin_factor > 0,
        is_equipment=False,  # Default
        imported_default=False,
        default_category_code=scenario_item.category_code
    )
    
    return create_library_item(library_item)
