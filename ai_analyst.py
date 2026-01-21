"""
Módulo de análisis IA usando Gemini para comparación de escenarios CAPEX.
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from budget_model import Scenario, Item, aggregate_by_category
from formatting import format_cop, format_percentage


# Get the directory where this script is located
_BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = _BASE_DIR / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def normalize_name(name: str) -> str:
    """Normaliza un nombre para matching (lowercase, sin espacios extra)."""
    if not name:
        return ""
    return " ".join(name.lower().strip().split())


def match_items_by_code_and_name(items_a: List[Item], items_b: List[Item]) -> List[Tuple[Optional[Item], Optional[Item]]]:
    """
    Hace match de ítems entre dos escenarios.
    
    Prioridad:
    1. item_code exacto
    2. (categoría + nombre normalizado)
    
    Returns:
        Lista de tuplas (item_a, item_b) o (item_a, None) o (None, item_b)
    """
    matches = []
    used_b = set()
    
    # Primera pasada: match por item_code
    for item_a in items_a:
        if item_a.item_code:
            matched = False
            for item_b in items_b:
                if item_b.item_id in used_b:
                    continue
                if item_b.item_code and item_a.item_code == item_b.item_code:
                    matches.append((item_a, item_b))
                    used_b.add(item_b.item_id)
                    matched = True
                    break
            if not matched:
                matches.append((item_a, None))
    
    # Segunda pasada: match por categoría + nombre normalizado (solo ítems no matcheados)
    unmatched_a = [item_a for item_a, item_b in matches if item_b is None]
    unmatched_b = [item_b for item_b in items_b if item_b.item_id not in used_b]
    
    for item_a in unmatched_a:
        name_a_norm = normalize_name(item_a.name)
        category_a = item_a.category_id
        
        matched = False
        for item_b in unmatched_b:
            if item_b.item_id in used_b:
                continue
            name_b_norm = normalize_name(item_b.name)
            if (category_a == item_b.category_id and 
                name_a_norm == name_b_norm and 
                name_a_norm):  # Solo si hay nombre
                # Actualizar match
                for i, (ia, ib) in enumerate(matches):
                    if ia == item_a and ib is None:
                        matches[i] = (item_a, item_b)
                        used_b.add(item_b.item_id)
                        matched = True
                        break
                if matched:
                    break
        
        if not matched:
            # Ya está en matches como (item_a, None)
            pass
    
    # Agregar ítems de B que no fueron matcheados
    for item_b in items_b:
        if item_b.item_id not in used_b:
            matches.append((None, item_b))
    
    return matches


def detect_anomalies(scenario_a: Scenario, scenario_b: Scenario) -> List[Dict[str, str]]:
    """
    Detecta anomalías en los escenarios.
    
    Returns:
        Lista de dicts con {"type": str, "item": str, "issue": str}
    """
    anomalies = []
    
    for scenario, label in [(scenario_a, "A"), (scenario_b, "B")]:
        for item in scenario.items:
            # Incoterm NA
            if hasattr(item, 'incoterm') and item.incoterm == "NA" and item.unit_price > 0:
                anomalies.append({
                    "type": "incoterm_na",
                    "item": f"{item.name} (Escenario {label})",
                    "issue": "Incoterm marcado como 'NA' pero el ítem tiene precio"
                })
            
            # Delivery point vacío o no definido
            if hasattr(item, 'delivery_point') and not item.delivery_point:
                anomalies.append({
                    "type": "delivery_empty",
                    "item": f"{item.name} (Escenario {label})",
                    "issue": "Punto de entrega no definido"
                })
            
            # IVA raro
            if item.vat_rate < 0 or item.vat_rate > 25:
                anomalies.append({
                    "type": "vat_unusual",
                    "item": f"{item.name} (Escenario {label})",
                    "issue": f"IVA fuera de rango normal: {item.vat_rate}%"
                })
            
            # Precio cero pero cantidad > 0
            if item.unit_price == 0 and item.qty > 0:
                anomalies.append({
                    "type": "zero_price",
                    "item": f"{item.name} (Escenario {label})",
                    "issue": "Precio unitario es cero pero cantidad > 0"
                })
    
    return anomalies


def group_categories_by_name(cat_totals: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Agrupa categorías por nombre, sumando totales si hay múltiples category_ids con el mismo nombre.
    
    Args:
        cat_totals: Diccionario con estructura {category_id: {'name': str, 'base': float, 'vat': float, 'total': float}}
    
    Returns:
        Diccionario con estructura {category_name: {'base': float, 'vat': float, 'total': float}}
    """
    by_name = {}
    for cat_id, totals in cat_totals.items():
        cat_name = totals.get('name', 'Sin categoría')
        if cat_name not in by_name:
            by_name[cat_name] = {'base': 0.0, 'vat': 0.0, 'total': 0.0}
        by_name[cat_name]['base'] += totals.get('base', 0.0)
        by_name[cat_name]['vat'] += totals.get('vat', 0.0)
        by_name[cat_name]['total'] += totals.get('total', 0.0)
    return by_name


def generate_diff_pack(
    scenario_a: Scenario,
    scenario_b: Scenario,
    summary_a: Dict[str, float],
    summary_b: Dict[str, float]
) -> Dict[str, Any]:
    """
    Genera un DIFF_PACK estructurado con diferencias entre escenarios.
    
    Returns:
        Dict con estructura completa de diferencias
    """
    # Totales
    modules_base_a = (summary_a.get('transport_base', 0) + 
                     summary_a.get('policies_base', 0) + 
                     summary_a.get('engineering_base', 0))
    modules_base_b = (summary_b.get('transport_base', 0) + 
                     summary_b.get('policies_base', 0) + 
                     summary_b.get('engineering_base', 0))
    modules_total_a = (summary_a.get('transport_total', 0) + 
                      summary_a.get('policies_total', 0) + 
                      summary_a.get('engineering_total', 0))
    modules_total_b = (summary_b.get('transport_total', 0) + 
                      summary_b.get('policies_total', 0) + 
                      summary_b.get('engineering_total', 0))
    
    # CAPEX total (incluyendo client_provided)
    capex_total_a = summary_a['grand_total']
    capex_total_b = summary_b['grand_total']
    
    def calc_delta_pct(a: float, b: float) -> float:
        if a == 0:
            return 0.0 if b == 0 else 100.0
        return ((b - a) / a) * 100.0
    
    totals = {
        "direct_cost_base": {
            "a": summary_a['direct_cost_base'],
            "b": summary_b['direct_cost_base'],
            "delta": summary_b['direct_cost_base'] - summary_a['direct_cost_base'],
            "delta_pct": calc_delta_pct(summary_a['direct_cost_base'], summary_b['direct_cost_base'])
        },
        "direct_cost_vat": {
            "a": summary_a['direct_cost_vat'],
            "b": summary_b['direct_cost_vat'],
            "delta": summary_b['direct_cost_vat'] - summary_a['direct_cost_vat'],
            "delta_pct": calc_delta_pct(summary_a['direct_cost_vat'], summary_b['direct_cost_vat'])
        },
        "direct_cost_total": {
            "a": summary_a['direct_cost_total'],
            "b": summary_b['direct_cost_total'],
            "delta": summary_b['direct_cost_total'] - summary_a['direct_cost_total'],
            "delta_pct": calc_delta_pct(summary_a['direct_cost_total'], summary_b['direct_cost_total'])
        },
        "modules_base": {
            "a": modules_base_a,
            "b": modules_base_b,
            "delta": modules_base_b - modules_base_a,
            "delta_pct": calc_delta_pct(modules_base_a, modules_base_b)
        },
        "modules_total": {
            "a": modules_total_a,
            "b": modules_total_b,
            "delta": modules_total_b - modules_total_a,
            "delta_pct": calc_delta_pct(modules_total_a, modules_total_b)
        },
        "aiu_total": {
            "a": summary_a['aiu_total'],
            "b": summary_b['aiu_total'],
            "delta": summary_b['aiu_total'] - summary_a['aiu_total'],
            "delta_pct": calc_delta_pct(summary_a['aiu_total'], summary_b['aiu_total'])
        },
        "epc_total": {
            "a": summary_a['epc_total'],
            "b": summary_b['epc_total'],
            "delta": summary_b['epc_total'] - summary_a['epc_total'],
            "delta_pct": calc_delta_pct(summary_a['epc_total'], summary_b['epc_total'])
        },
        "capex_total": {
            "a": capex_total_a,
            "b": capex_total_b,
            "delta": capex_total_b - capex_total_a,
            "delta_pct": calc_delta_pct(capex_total_a, capex_total_b)
        }
    }
    
    # Por categoría - agrupar por nombre en lugar de category_id
    cat_totals_a = aggregate_by_category(scenario_a, summary_a)
    cat_totals_b = aggregate_by_category(scenario_b, summary_b)
    
    # Agrupar por nombre de categoría
    cat_by_name_a = group_categories_by_name(cat_totals_a)
    cat_by_name_b = group_categories_by_name(cat_totals_b)
    
    # Obtener todos los nombres únicos de categorías
    all_category_names = set(cat_by_name_a.keys()) | set(cat_by_name_b.keys())
    
    by_category = []
    for cat_name in sorted(all_category_names):  # Ordenar para consistencia
        cat_a = cat_by_name_a.get(cat_name, {'base': 0.0, 'vat': 0.0, 'total': 0.0})
        cat_b = cat_by_name_b.get(cat_name, {'base': 0.0, 'vat': 0.0, 'total': 0.0})
        
        base_a = cat_a['base']
        base_b = cat_b['base']
        delta = base_b - base_a
        delta_pct = calc_delta_pct(base_a, base_b)
        
        by_category.append({
            "category": cat_name,
            "base_a": base_a,
            "base_b": base_b,
            "delta": delta,
            "delta_pct": delta_pct,
            "vat_a": cat_a['vat'],
            "vat_b": cat_b['vat'],
            "total_a": cat_a['total'],
            "total_b": cat_b['total']
        })
    
    # Top ítems por diferencia absoluta
    matches = match_items_by_code_and_name(scenario_a.items, scenario_b.items)
    
    # Obtener totales por ítem
    items_totals_a = summary_a.get('items_totals', {})
    items_totals_b = summary_b.get('items_totals', {})
    
    top_items = []
    for item_a, item_b in matches:
        if item_a is None:
            # Solo en B
            totals_b = items_totals_b.get(item_b.item_id, {})
            delta = totals_b.get('base_line', 0.0)
            top_items.append({
                "item_code": item_b.item_code or "",
                "name": item_b.name,
                "category": "Solo en B",
                "qty_a": 0.0,
                "qty_b": item_b.qty,
                "price_a": 0.0,
                "price_b": item_b.unit_price,
                "base_a": 0.0,
                "base_b": totals_b.get('base_line', 0.0),
                "delta": delta,
                "changes": {
                    "qty": True,
                    "price": True,
                    "vat_rate": False,
                    "incoterm": False,
                    "delivery_point": False,
                    "transport": False,
                    "installation": False
                }
            })
        elif item_b is None:
            # Solo en A
            totals_a = items_totals_a.get(item_a.item_id, {})
            delta = -totals_a.get('base_line', 0.0)
            top_items.append({
                "item_code": item_a.item_code or "",
                "name": item_a.name,
                "category": "Solo en A",
                "qty_a": item_a.qty,
                "qty_b": 0.0,
                "price_a": item_a.unit_price,
                "price_b": 0.0,
                "base_a": totals_a.get('base_line', 0.0),
                "base_b": 0.0,
                "delta": delta,
                "changes": {
                    "qty": True,
                    "price": True,
                    "vat_rate": False,
                    "incoterm": False,
                    "delivery_point": False,
                    "transport": False,
                    "installation": False
                }
            })
        else:
            # Ambos existen, comparar
            totals_a = items_totals_a.get(item_a.item_id, {})
            totals_b = items_totals_b.get(item_b.item_id, {})
            
            base_a = totals_a.get('base_line', 0.0)
            base_b = totals_b.get('base_line', 0.0)
            delta = base_b - base_a
            
            # Detectar cambios
            changes = {
                "qty": abs(item_a.qty - item_b.qty) > 0.001,
                "price": abs(item_a.unit_price - item_b.unit_price) > 0.01,
                "vat_rate": abs(item_a.vat_rate - item_b.vat_rate) > 0.1,
                "incoterm": getattr(item_a, 'incoterm', 'NA') != getattr(item_b, 'incoterm', 'NA'),
                "delivery_point": getattr(item_a, 'delivery_point', '') != getattr(item_b, 'delivery_point', ''),
                "transport": getattr(item_a, 'includes_transport_to_site', False) != getattr(item_b, 'includes_transport_to_site', False),
                "installation": getattr(item_a, 'includes_installation', False) != getattr(item_b, 'includes_installation', False)
            }
            
            # Obtener nombre de categoría
            category_name = "Sin categoría"
            for cat in scenario_a.categories:
                if cat.category_id == item_a.category_id:
                    category_name = cat.label
                    break
            
            top_items.append({
                "item_code": item_a.item_code or item_b.item_code or "",
                "name": item_a.name,
                "category": category_name,
                "qty_a": item_a.qty,
                "qty_b": item_b.qty,
                "price_a": item_a.unit_price,
                "price_b": item_b.unit_price,
                "base_a": base_a,
                "base_b": base_b,
                "delta": delta,
                "changes": changes
            })
    
    # Ordenar por |delta| y tomar top 30
    top_items.sort(key=lambda x: abs(x['delta']), reverse=True)
    top_items = top_items[:30]
    
    # Anomalías
    anomalies = detect_anomalies(scenario_a, scenario_b)
    
    diff_pack = {
        "totals": totals,
        "by_category": by_category,
        "top_items": top_items,
        "anomalies": anomalies
    }
    
    return diff_pack


def get_diff_pack_hash(diff_pack: Dict) -> str:
    """Calcula hash MD5 del DIFF_PACK para usar como clave de cache."""
    diff_str = json.dumps(diff_pack, sort_keys=True, default=str)
    return hashlib.md5(diff_str.encode('utf-8')).hexdigest()


def get_cached_analysis(diff_hash: str) -> Optional[Dict]:
    """Obtiene análisis desde cache si existe."""
    cache_file = CACHE_DIR / f"{diff_hash}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                return cache_data.get('analysis')
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_cached_analysis(diff_hash: str, analysis: Dict):
    """Guarda análisis en cache."""
    cache_file = CACHE_DIR / f"{diff_hash}.json"
    cache_data = {
        "hash": diff_hash,
        "timestamp": datetime.now().isoformat(),
        "analysis": analysis
    }
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except IOError:
        pass  # Si falla guardar cache, continuar sin error


def get_available_gemini_model(api_key: str) -> Optional[str]:
    """
    Obtiene un modelo Gemini disponible.
    
    Primero intenta listar modelos disponibles dinámicamente.
    Si eso falla, prueba una lista de modelos en orden de preferencia.
    
    Returns:
        Nombre del modelo disponible o None si no encuentra ninguno
    """
    genai.configure(api_key=api_key)
    
    # Intentar listar modelos disponibles
    try:
        available_models = genai.list_models()
        for model in available_models:
            if 'generateContent' in model.supported_generation_methods:
                # Extraer solo el nombre del modelo (sin el prefijo "models/")
                model_name = model.name
                if model_name.startswith('models/'):
                    model_name = model_name[7:]  # Remover prefijo "models/"
                return model_name
    except Exception:
        # Si listar modelos falla, usar lista de fallback
        pass
    
    # Lista de modelos a probar en orden de preferencia
    model_names = [
        'gemini-3.0-pro',
        'gemini-2.5-pro',
        'gemini-2.5-flash',
        'gemini-1.5-pro-002',
        'gemini-1.5-flash-002',
        'gemini-1.5-pro',
        'gemini-1.5-flash',
        'gemini-pro'
    ]
    
    # Probar cada modelo para ver si está disponible
    for model_name in model_names:
        try:
            # Intentar crear el modelo (esto verifica si está disponible)
            test_model = genai.GenerativeModel(model_name)
            # Si llegamos aquí, el modelo está disponible
            return model_name
        except Exception:
            # Este modelo no está disponible, probar el siguiente
            continue
    
    return None


def call_gemini_analysis(diff_pack: Dict, api_key: str) -> Dict:
    """
    Llama a Gemini para obtener análisis estructurado.
    
    Returns:
        Dict con análisis estructurado según esquema requerido
    """
    if not GEMINI_AVAILABLE:
        raise ImportError("google-genai no está instalado. Ejecuta: pip install google-genai")
    
    # Configurar API key
    genai.configure(api_key=api_key)
    
    # Obtener modelo disponible
    model_name = get_available_gemini_model(api_key)
    if not model_name:
        raise Exception(
            "No se encontró ningún modelo Gemini disponible. "
            "Verifica tu API key y que tengas acceso a los modelos Gemini. "
            "Puedes verificar modelos disponibles ejecutando: "
            "import google.generativeai as genai; genai.configure(api_key='TU_KEY'); list(genai.list_models())"
        )
    
    # Crear modelo
    model = genai.GenerativeModel(model_name)
    
    # Construir prompt
    diff_pack_str = json.dumps(diff_pack, indent=2, default=str)
    
    prompt = f"""Eres un analista financiero experto en proyectos de energía solar. 
Analiza las siguientes diferencias CAPEX entre dos escenarios de presupuesto.

DATOS DE COMPARACIÓN:
{diff_pack_str}

Genera un análisis estructurado en JSON con este esquema exacto:
{{
  "executive_summary": ["punto 1", "punto 2", ...],
  "main_drivers": [
    {{"title": "...", "impact_cop": 0, "explanation": "..."}}
  ],
  "root_causes": [
    {{"cause": "price|quantity|scope|logistics|tax|aiu", "details": "..."}}
  ],
  "red_flags": [
    {{"severity": "high|med|low", "issue": "...", "why_it_matters": "..."}}
  ],
  "recommended_actions": [
    {{"action": "...", "expected_impact": "...", "who": "..."}}
  ],
  "questions_to_validate": ["...", "..."]
}}

IMPORTANTE: Retorna SOLO JSON válido, sin markdown, sin explicaciones adicionales. El JSON debe ser parseable directamente."""

    try:
        response = model.generate_content(prompt)
        
        # Extraer JSON de la respuesta
        response_text = response.text.strip()
        
        # Limpiar markdown si existe
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parsear JSON
        analysis = json.loads(response_text)
        
        # Validar estructura básica
        required_keys = ["executive_summary", "main_drivers", "root_causes", "red_flags", "recommended_actions", "questions_to_validate"]
        for key in required_keys:
            if key not in analysis:
                analysis[key] = []
        
        return analysis
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parseando respuesta de Gemini: {e}. Respuesta: {response_text[:500]}")
    except Exception as e:
        raise Exception(f"Error llamando a Gemini: {e}")


def analyze_capex_diff(
    scenario_a: Scenario,
    scenario_b: Scenario,
    summary_a: Dict[str, float],
    summary_b: Dict[str, float],
    api_key: Optional[str],
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    Función principal que orquesta el análisis IA.
    
    Args:
        scenario_a: Escenario A
        scenario_b: Escenario B
        summary_a: Resumen calculado del escenario A
        summary_b: Resumen calculado del escenario B
        api_key: API key de Gemini (opcional)
        force_regenerate: Si es True, ignora el caché y fuerza una nueva generación
    
    Returns:
        Dict con análisis estructurado o error
    """
    if not api_key:
        return {
            "error": "API key no configurada",
            "message": "Configura GEMINI_API_KEY en el archivo .env"
        }
    
    # Generar DIFF_PACK
    diff_pack = generate_diff_pack(scenario_a, scenario_b, summary_a, summary_b)
    
    # Calcular hash
    diff_hash = get_diff_pack_hash(diff_pack)
    
    # Verificar cache (solo si no se fuerza regeneración)
    if not force_regenerate:
        cached_analysis = get_cached_analysis(diff_hash)
        if cached_analysis:
            return cached_analysis
    
    # Llamar a Gemini
    try:
        analysis = call_gemini_analysis(diff_pack, api_key)
        # Guardar en cache (sobrescribe si ya existía)
        save_cached_analysis(diff_hash, analysis)
        return analysis
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        return {
            "error": f"{type(e).__name__}: {str(e)}\n\nTraceback completo:\n{error_traceback}",
            "message": "Error al generar análisis IA"
        }
