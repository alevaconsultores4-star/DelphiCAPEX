"""
Módulo de persistencia para proyectos y escenarios en JSON.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import uuid

from budget_model import Project, Scenario


# Get the directory where this script is located
_BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = _BASE_DIR / "data"
PROJECTS_INDEX_FILE = DATA_DIR / "projects_index.json"


def ensure_data_dir():
    """Asegura que el directorio data existe."""
    DATA_DIR.mkdir(exist_ok=True)


def load_projects_index() -> Dict:
    """
    Carga el índice de proyectos desde JSON.
    
    Returns:
        Dict con estructura: {"projects": [{"project_id": str, "name": str, ...}]}
    """
    ensure_data_dir()
    
    if not PROJECTS_INDEX_FILE.exists():
        return {"projects": []}
    
    try:
        with open(PROJECTS_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # Si el archivo está corrupto, crear uno nuevo
        print(f"Error cargando índice: {e}. Creando índice nuevo.")
        return {"projects": []}


def save_projects_index(index: Dict):
    """
    Guarda el índice de proyectos en JSON.
    
    Args:
        index: Dict con estructura de índice
    """
    ensure_data_dir()
    
    try:
        with open(PROJECTS_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise Exception(f"Error guardando índice: {e}")


def load_project(project_id: str) -> Optional[Project]:
    """
    Carga un proyecto completo desde JSON.
    
    Args:
        project_id: ID del proyecto
    
    Returns:
        Project o None si no existe
    """
    ensure_data_dir()
    
    project_file = DATA_DIR / f"{project_id}.json"
    
    if not project_file.exists():
        return None
    
    try:
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return Project.from_dict(data)
    except (json.JSONDecodeError, IOError) as e:
        raise Exception(f"Error cargando proyecto {project_id}: {e}")


def save_project(project: Project):
    """
    Guarda un proyecto completo en JSON.
    
    Args:
        project: El proyecto a guardar
    """
    ensure_data_dir()
    
    # Actualizar timestamp
    project.updated_at = datetime.now().isoformat()
    
    # Guardar proyecto
    project_file = DATA_DIR / f"{project.project_id}.json"
    
    try:
        with open(project_file, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise Exception(f"Error guardando proyecto: {e}")
    
    # Actualizar índice
    index = load_projects_index()
    projects = index.get("projects", [])
    
    # Buscar si ya existe en el índice
    found = False
    for i, p in enumerate(projects):
        if p.get("project_id") == project.project_id:
            projects[i] = {
                "project_id": project.project_id,
                "name": project.name,
                "created_at": project.created_at,
                "updated_at": project.updated_at
            }
            found = True
            break
    
    if not found:
        projects.append({
            "project_id": project.project_id,
            "name": project.name,
            "created_at": project.created_at,
            "updated_at": project.updated_at
        })
    
    index["projects"] = projects
    save_projects_index(index)


def create_project(name: str) -> Project:
    """
    Crea un nuevo proyecto con ID único.
    
    Args:
        name: Nombre del proyecto
    
    Returns:
        Project creado
    """
    project = Project(
        project_id=str(uuid.uuid4()),
        name=name,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        scenarios=[]
    )
    
    save_project(project)
    return project


def delete_project(project_id: str):
    """
    Elimina un proyecto y su archivo.
    
    Args:
        project_id: ID del proyecto a eliminar
    """
    ensure_data_dir()
    
    # Eliminar archivo del proyecto
    project_file = DATA_DIR / f"{project_id}.json"
    if project_file.exists():
        try:
            project_file.unlink()
        except IOError as e:
            raise Exception(f"Error eliminando archivo del proyecto: {e}")
    
    # Actualizar índice
    index = load_projects_index()
    projects = index.get("projects", [])
    index["projects"] = [p for p in projects if p.get("project_id") != project_id]
    save_projects_index(index)


def duplicate_scenario(project_id: str, source_scenario_id: str, new_name: str) -> Optional[Scenario]:
    """
    Duplica un escenario dentro de un proyecto.
    
    Args:
        project_id: ID del proyecto
        source_scenario_id: ID del escenario a duplicar
        new_name: Nombre para el nuevo escenario
    
    Returns:
        Scenario duplicado o None si no se encontró el escenario fuente
    """
    project = load_project(project_id)
    if not project:
        return None
    
    # Buscar escenario fuente
    source_scenario = None
    for scenario in project.scenarios:
        if scenario.scenario_id == source_scenario_id:
            source_scenario = scenario
            break
    
    if not source_scenario:
        return None
    
    # Crear nuevo escenario duplicado
    new_scenario_data = source_scenario.to_dict()
    new_scenario_data['scenario_id'] = str(uuid.uuid4())
    new_scenario_data['name'] = new_name
    
    # Duplicar ítems y categorías con nuevos IDs
    new_scenario = Scenario.from_dict(new_scenario_data)
    
    # Duplicar categorías con nuevos IDs
    category_id_mapping = {}
    for cat in new_scenario.categories:
        old_id = cat.category_id
        cat.category_id = str(uuid.uuid4())
        category_id_mapping[old_id] = cat.category_id
    
    # Duplicar ítems con nuevos IDs y actualizar referencias de categoría
    new_items = []
    for item in new_scenario.items:
        item.item_id = str(uuid.uuid4())
        # Actualizar category_id si existe en el mapping
        if item.category_id in category_id_mapping:
            item.category_id = category_id_mapping[item.category_id]
        new_items.append(item)
    
    new_scenario.items = new_items
    
    # Agregar al proyecto
    project.scenarios.append(new_scenario)
    save_project(project)
    
    return new_scenario


def copy_scenario_to_project(
    source_project_id: str,
    source_scenario_id: str,
    target_project_id: str,
    new_scenario_name: str
) -> Optional[Scenario]:
    """
    Copia un escenario de un proyecto a otro proyecto.
    
    Args:
        source_project_id: ID del proyecto fuente
        source_scenario_id: ID del escenario a copiar
        target_project_id: ID del proyecto destino
        new_scenario_name: Nombre para el escenario copiado
    
    Returns:
        Scenario copiado o None si no se encontró el escenario fuente
    """
    # Cargar proyecto fuente
    source_project = load_project(source_project_id)
    if not source_project:
        return None
    
    # Buscar escenario fuente
    source_scenario = None
    for scenario in source_project.scenarios:
        if scenario.scenario_id == source_scenario_id:
            source_scenario = scenario
            break
    
    if not source_scenario:
        return None
    
    # Cargar proyecto destino
    target_project = load_project(target_project_id)
    if not target_project:
        return None
    
    # Crear nuevo escenario copiado
    new_scenario_data = source_scenario.to_dict()
    new_scenario_data['scenario_id'] = str(uuid.uuid4())
    new_scenario_data['name'] = new_scenario_name
    
    # Duplicar ítems y categorías con nuevos IDs
    new_scenario = Scenario.from_dict(new_scenario_data)
    
    # Duplicar categorías con nuevos IDs
    category_id_mapping = {}
    for cat in new_scenario.categories:
        old_id = cat.category_id
        cat.category_id = str(uuid.uuid4())
        category_id_mapping[old_id] = cat.category_id
    
    # Duplicar ítems con nuevos IDs y actualizar referencias de categoría
    new_items = []
    for item in new_scenario.items:
        item.item_id = str(uuid.uuid4())
        # Actualizar category_id si existe en el mapping
        if item.category_id in category_id_mapping:
            item.category_id = category_id_mapping[item.category_id]
        new_items.append(item)
    
    new_scenario.items = new_items
    
    # Agregar al proyecto destino
    target_project.scenarios.append(new_scenario)
    save_project(target_project)
    
    return new_scenario


def get_all_projects() -> List[Dict]:
    """
    Obtiene lista de todos los proyectos desde el índice.
    
    Returns:
        Lista de dicts con info de proyectos
    """
    index = load_projects_index()
    return index.get("projects", [])
