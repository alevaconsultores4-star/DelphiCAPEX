"""
Data Access Layer (DAL) for CAPEX Builder with migration support.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import uuid

from models import (
    Client, Project, Scenario, ScenarioItem,
    LibraryCategory, LibraryItem, UploadMetadata
)


# Base directory setup
_BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = _BASE_DIR / "data"
CLIENTS_DIR = DATA_DIR / "clients"
PROJECTS_DIR = DATA_DIR / "projects"
SCENARIOS_DIR = DATA_DIR / "scenarios"
UPLOADS_BASE_DIR = DATA_DIR / "uploads"
LIBRARY_DIR = DATA_DIR

# Index files
CLIENTS_INDEX_FILE = DATA_DIR / "clients_index.json"
LIBRARY_CATEGORIES_FILE = LIBRARY_DIR / "library_categories.json"
LIBRARY_ITEMS_FILE = LIBRARY_DIR / "library_items.json"

# Legacy files (for migration)
LEGACY_PROJECTS_INDEX = DATA_DIR / "projects_index.json"
LEGACY_PROJECTS_DIR = DATA_DIR  # Old projects stored as {project_id}.json in data/


def ensure_directories():
    """Ensure all required directories exist."""
    DATA_DIR.mkdir(exist_ok=True)
    CLIENTS_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    SCENARIOS_DIR.mkdir(exist_ok=True)
    UPLOADS_BASE_DIR.mkdir(exist_ok=True)


# ============================================================================
# CLIENT OPERATIONS
# ============================================================================

def load_clients_index() -> Dict:
    """Load clients index."""
    ensure_directories()
    if not CLIENTS_INDEX_FILE.exists():
        return {"clients": []}
    try:
        with open(CLIENTS_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"clients": []}


def save_clients_index(index: Dict):
    """Save clients index."""
    ensure_directories()
    with open(CLIENTS_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def create_client(name: str) -> Client:
    """Create a new client."""
    client = Client(
        client_id=str(uuid.uuid4()),
        name=name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    save_client(client)
    return client


def save_client(client: Client):
    """Save a client."""
    ensure_directories()
    client.updated_at = datetime.now().isoformat()
    
    # Save client file
    client_file = CLIENTS_DIR / f"{client.client_id}.json"
    with open(client_file, 'w', encoding='utf-8') as f:
        json.dump(client.to_dict(), f, indent=2, ensure_ascii=False)
    
    # Update index
    index = load_clients_index()
    clients = index.get("clients", [])
    
    # Find and update or append
    found = False
    for i, c in enumerate(clients):
        if c.get("client_id") == client.client_id:
            clients[i] = {
                "client_id": client.client_id,
                "name": client.name,
                "created_at": client.created_at,
                "updated_at": client.updated_at
            }
            found = True
            break
    
    if not found:
        clients.append({
            "client_id": client.client_id,
            "name": client.name,
            "created_at": client.created_at,
            "updated_at": client.updated_at
        })
    
    index["clients"] = clients
    save_clients_index(index)


def load_client(client_id: str) -> Optional[Client]:
    """Load a client by ID."""
    ensure_directories()
    client_file = CLIENTS_DIR / f"{client_id}.json"
    if not client_file.exists():
        return None
    try:
        with open(client_file, 'r', encoding='utf-8') as f:
            return Client.from_dict(json.load(f))
    except (json.JSONDecodeError, IOError):
        return None


def get_all_clients() -> List[Dict]:
    """Get all clients from index."""
    index = load_clients_index()
    return index.get("clients", [])


def delete_client(client_id: str):
    """Delete a client and all associated projects/scenarios."""
    ensure_directories()
    
    # Delete client file
    client_file = CLIENTS_DIR / f"{client_id}.json"
    if client_file.exists():
        client_file.unlink()
    
    # Delete all projects for this client
    projects = get_projects_by_client(client_id)
    for project in projects:
        delete_project(project['project_id'])
    
    # Update index
    index = load_clients_index()
    index["clients"] = [c for c in index.get("clients", []) if c.get("client_id") != client_id]
    save_clients_index(index)


# ============================================================================
# PROJECT OPERATIONS
# ============================================================================

def create_project(client_id: str, name: str) -> Project:
    """Create a new project."""
    project = Project(
        project_id=str(uuid.uuid4()),
        client_id=client_id,
        name=name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    save_project(project)
    return project


def save_project(project: Project):
    """Save a project."""
    ensure_directories()
    project.updated_at = datetime.now().isoformat()
    
    # Save project file
    project_file = PROJECTS_DIR / f"{project.project_id}.json"
    with open(project_file, 'w', encoding='utf-8') as f:
        json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)
    
    # Update client's project list (stored in client file)
    client = load_client(project.client_id)
    if client:
        # We'll store project references in the client file for quick access
        # But projects are stored separately
        pass


def load_project(project_id: str) -> Optional[Project]:
    """Load a project by ID."""
    ensure_directories()
    project_file = PROJECTS_DIR / f"{project_id}.json"
    if not project_file.exists():
        return None
    try:
        with open(project_file, 'r', encoding='utf-8') as f:
            return Project.from_dict(json.load(f))
    except (json.JSONDecodeError, IOError):
        return None


def get_projects_by_client(client_id: str) -> List[Dict]:
    """Get all projects for a client."""
    ensure_directories()
    projects = []
    if PROJECTS_DIR.exists():
        for project_file in PROJECTS_DIR.glob("*.json"):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                    if project_data.get("client_id") == client_id:
                        projects.append({
                            "project_id": project_data.get("project_id"),
                            "name": project_data.get("name"),
                            "created_at": project_data.get("created_at"),
                            "updated_at": project_data.get("updated_at")
                        })
            except (json.JSONDecodeError, IOError):
                continue
    return projects


def delete_project(project_id: str):
    """Delete a project and all associated scenarios."""
    ensure_directories()
    
    # Delete all scenarios for this project
    scenarios = get_scenarios_by_project(project_id)
    for scenario in scenarios:
        delete_scenario(scenario['scenario_id'])
    
    # Delete project file
    project_file = PROJECTS_DIR / f"{project_id}.json"
    if project_file.exists():
        project_file.unlink()


def duplicate_project(project_id: str, new_name: str) -> Project:
    """Duplicate a project with all scenarios."""
    source_project = load_project(project_id)
    if not source_project:
        raise ValueError(f"Project {project_id} not found")
    
    # Create new project
    new_project = create_project(source_project.client_id, new_name)
    
    # Duplicate all scenarios
    scenarios = get_scenarios_by_project(project_id)
    for scenario_data in scenarios:
        scenario = load_scenario(scenario_data['scenario_id'])
        if scenario:
            new_scenario = duplicate_scenario(scenario.scenario_id, f"{scenario.name} (copia)")
            new_scenario.project_id = new_project.project_id
            save_scenario(new_scenario)
    
    return new_project


# ============================================================================
# SCENARIO OPERATIONS
# ============================================================================

def create_scenario(project_id: str, name: str) -> Scenario:
    """Create a new scenario."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        project_id=project_id,
        name=name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    save_scenario(scenario)
    return scenario


def save_scenario(scenario: Scenario):
    """Save a scenario."""
    ensure_directories()
    scenario.updated_at = datetime.now().isoformat()
    
    # Save scenario file
    scenario_file = SCENARIOS_DIR / f"{scenario.scenario_id}.json"
    with open(scenario_file, 'w', encoding='utf-8') as f:
        json.dump(scenario.to_dict(), f, indent=2, ensure_ascii=False)


def load_scenario(scenario_id: str) -> Optional[Scenario]:
    """Load a scenario by ID."""
    ensure_directories()
    scenario_file = SCENARIOS_DIR / f"{scenario_id}.json"
    if not scenario_file.exists():
        return None
    try:
        with open(scenario_file, 'r', encoding='utf-8') as f:
            return Scenario.from_dict(json.load(f))
    except (json.JSONDecodeError, IOError):
        return None


def get_scenarios_by_project(project_id: str) -> List[Dict]:
    """Get all scenarios for a project."""
    ensure_directories()
    scenarios = []
    if SCENARIOS_DIR.exists():
        for scenario_file in SCENARIOS_DIR.glob("*.json"):
            try:
                with open(scenario_file, 'r', encoding='utf-8') as f:
                    scenario_data = json.load(f)
                    if scenario_data.get("project_id") == project_id:
                        scenarios.append({
                            "scenario_id": scenario_data.get("scenario_id"),
                            "name": scenario_data.get("name"),
                            "created_at": scenario_data.get("created_at"),
                            "updated_at": scenario_data.get("updated_at")
                        })
            except (json.JSONDecodeError, IOError):
                continue
    return scenarios


def delete_scenario(scenario_id: str):
    """Delete a scenario."""
    ensure_directories()
    scenario_file = SCENARIOS_DIR / f"{scenario_id}.json"
    if scenario_file.exists():
        scenario_file.unlink()


def duplicate_scenario(scenario_id: str, new_name: str) -> Scenario:
    """Duplicate a scenario within the same project."""
    source_scenario = load_scenario(scenario_id)
    if not source_scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    
    # Create new scenario with copied data
    new_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        project_id=source_scenario.project_id,
        name=new_name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        variables=source_scenario.variables,
        aiu_config=source_scenario.aiu_config,
        vat_config=source_scenario.vat_config,
        items=[ScenarioItem.from_dict(item.to_dict()) for item in source_scenario.items]
    )
    
    # Generate new IDs for items
    for item in new_scenario.items:
        item.item_id = str(uuid.uuid4())
    
    save_scenario(new_scenario)
    return new_scenario


def copy_scenario_to_project(scenario_id: str, target_project_id: str, new_name: str) -> Scenario:
    """Copy a scenario to another project."""
    source_scenario = load_scenario(scenario_id)
    if not source_scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    
    new_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        project_id=target_project_id,
        name=new_name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        variables=source_scenario.variables,
        aiu_config=source_scenario.aiu_config,
        vat_config=source_scenario.vat_config,
        items=[ScenarioItem.from_dict(item.to_dict()) for item in source_scenario.items]
    )
    
    # Generate new IDs for items
    for item in new_scenario.items:
        item.item_id = str(uuid.uuid4())
    
    save_scenario(new_scenario)
    return new_scenario


def clone_scenario_as_template(scenario_id: str, new_name: str) -> Scenario:
    """Clone scenario as template (prices set to 0)."""
    source_scenario = load_scenario(scenario_id)
    if not source_scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    
    new_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        project_id=source_scenario.project_id,
        name=new_name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        variables=source_scenario.variables,
        aiu_config=source_scenario.aiu_config,
        vat_config=source_scenario.vat_config,
        items=[ScenarioItem.from_dict(item.to_dict()) for item in source_scenario.items]
    )
    
    # Set all prices to 0
    for item in new_scenario.items:
        item.item_id = str(uuid.uuid4())
        item.price = 0.0
    
    save_scenario(new_scenario)
    return new_scenario


# ============================================================================
# MIGRATION
# ============================================================================

def migrate_legacy_data() -> bool:
    """
    Migrate legacy data to new structure.
    Creates "Default" client and moves all existing projects to it.
    Returns True if migration was performed, False if already migrated.
    """
    ensure_directories()
    
    # Check if migration already done (check for "Default" client)
    clients = get_all_clients()
    default_client = next((c for c in clients if c.get("name") == "Default"), None)
    
    if default_client:
        # Already migrated
        return False
    
    # Check if legacy data exists
    if not LEGACY_PROJECTS_INDEX.exists():
        # No legacy data to migrate
        return False
    
    try:
        # Load legacy projects index
        with open(LEGACY_PROJECTS_INDEX, 'r', encoding='utf-8') as f:
            legacy_index = json.load(f)
        
        legacy_projects = legacy_index.get("projects", [])
        if not legacy_projects:
            return False
        
        # Create "Default" client
        default_client = create_client("Default")
        
        # Migrate each legacy project
        # Try to import legacy models, fallback if not available
        try:
            from budget_model import Project as LegacyProject, Scenario as LegacyScenario
        except ImportError:
            # If legacy models not available, skip migration
            return False
        
        for legacy_project_data in legacy_projects:
            legacy_project_id = legacy_project_data.get("project_id")
            legacy_project_name = legacy_project_data.get("name", "Proyecto sin nombre")
            
            # Load legacy project file
            legacy_project_file = LEGACY_PROJECTS_DIR / f"{legacy_project_id}.json"
            if not legacy_project_file.exists():
                continue
            
            try:
                with open(legacy_project_file, 'r', encoding='utf-8') as f:
                    legacy_project_dict = json.load(f)
                
                legacy_project = LegacyProject.from_dict(legacy_project_dict)
                
                # Create new project
                new_project = create_project(default_client.client_id, legacy_project.name)
                
                # Migrate scenarios
                for legacy_scenario in legacy_project.scenarios:
                    # Convert legacy scenario to new format
                    new_scenario = convert_legacy_scenario(legacy_scenario, new_project.project_id)
                    save_scenario(new_scenario)
                
            except Exception as e:
                print(f"Error migrating project {legacy_project_id}: {e}")
                continue
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False


def convert_legacy_scenario(legacy_scenario, project_id: str) -> Scenario:
    """Convert legacy Scenario to new Scenario format."""
    from models import ScenarioVariables, AIUConfig, VATConfig, ScenarioItem, PricingMode, AIUFactors
    
    # Convert variables
    variables = ScenarioVariables(
        p50_mwh_per_year=getattr(legacy_scenario, 'energia_p50_mwh_anio', 0.0),
        p90_mwh_per_year=0.0,  # Not in legacy
        ac_power_mw=getattr(legacy_scenario, 'potencia_total_kwac', 0.0) / 1000.0,  # Convert kW to MW
        dc_power_mwp=getattr(legacy_scenario, 'pnom_total_kwp', 0.0) / 1000.0,  # Convert kWp to MWp
        currency="COP",
        fx_rate=1.0
    )
    
    # Convert AIU config
    aiu_config = AIUConfig(
        enabled=getattr(legacy_scenario, 'aiu_enabled', False),
        admin_pct=getattr(legacy_scenario, 'aiu_admin_pct', 0.0),
        imprev_pct=getattr(legacy_scenario, 'aiu_imprevistos_pct', 0.0),
        util_pct=getattr(legacy_scenario, 'aiu_utility_pct', 0.0)
    )
    
    # Convert VAT config
    vat_config = VATConfig(
        vat_recoverable=True,  # Default
        vat_on_utilidad_enabled=False,  # Not in legacy
        vat_rate_utilidad=19.0
    )
    
    # Convert items
    new_items = []
    for legacy_item in legacy_scenario.items:
        # Determine AIU factors (default 100% unless client_provided)
        aiu_factors = AIUFactors(
            admin_factor=0.0 if getattr(legacy_item, 'client_provided', False) else 100.0,
            imprev_factor=0.0 if getattr(legacy_item, 'client_provided', False) else 100.0,
            util_factor=0.0 if getattr(legacy_item, 'client_provided', False) else 100.0
        )
        
        new_item = ScenarioItem(
            item_id=str(uuid.uuid4()),
            item_code=getattr(legacy_item, 'item_code', '') or '',
            name=getattr(legacy_item, 'name', ''),
            category_code='',  # Will need to be mapped from category_id
            description=getattr(legacy_item, 'description', ''),
            qty=getattr(legacy_item, 'qty', 0.0),
            unit=getattr(legacy_item, 'unit', 'UND'),
            pricing_mode=PricingMode.UNIT,
            price=getattr(legacy_item, 'unit_price', 0.0),
            vat_rate=getattr(legacy_item, 'vat_rate', 19.0),
            client_pays=getattr(legacy_item, 'client_provided', False),
            aiu_factors=aiu_factors,
            incoterm=getattr(legacy_item, 'incoterm', 'NA'),
            includes_installation=getattr(legacy_item, 'includes_installation', False),
            includes_transport=getattr(legacy_item, 'includes_transport_to_site', False),
            includes_commissioning=getattr(legacy_item, 'includes_commissioning', False),
            delivery_point=getattr(legacy_item, 'delivery_point', 'Puesto en obra'),
            notes=getattr(legacy_item, 'notes', ''),
            order=getattr(legacy_item, 'order', 0)
        )
        new_items.append(new_item)
    
    # Create new scenario
    new_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        project_id=project_id,
        name=legacy_scenario.name,
        created_at=getattr(legacy_scenario, 'created_at', datetime.now().isoformat()),
        updated_at=datetime.now().isoformat(),
        variables=variables,
        aiu_config=aiu_config,
        vat_config=vat_config,
        items=new_items
    )
    
    return new_scenario
