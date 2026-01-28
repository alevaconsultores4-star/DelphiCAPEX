"""
Scenario comparison service.
"""

from typing import Dict, List, Tuple, Optional, Any
from models import Scenario
from capex_engine import calculate_scenario_totals, aggregate_by_category, calculate_normalization_metrics


def match_items_by_code(scenario_a: Scenario, scenario_b: Scenario) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """
    Match items between scenarios by item_code.
    Returns: {item_code: (item_id_a, item_id_b)}
    """
    matches = {}
    
    # Index items by code (case-insensitive)
    items_a = {item.item_code.lower(): item.item_id for item in scenario_a.items if item.item_code}
    items_b = {item.item_code.lower(): item.item_id for item in scenario_b.items if item.item_code}
    
    # Find all unique codes
    all_codes = set(items_a.keys()) | set(items_b.keys())
    
    for code in all_codes:
        matches[code] = (items_a.get(code), items_b.get(code))
    
    return matches


def match_items_by_name(scenario_a: Scenario, scenario_b: Scenario) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """
    Match items by name (fallback when code doesn't match).
    Returns: {name: (item_id_a, item_id_b)}
    """
    matches = {}
    
    # Index items by name (case-insensitive)
    items_a = {item.name.lower(): item.item_id for item in scenario_a.items}
    items_b = {item.name.lower(): item.item_id for item in scenario_b.items}
    
    # Find all unique names
    all_names = set(items_a.keys()) | set(items_b.keys())
    
    for name in all_names:
        matches[name] = (items_a.get(name), items_b.get(name))
    
    return matches


def compare_scenarios(scenario_a: Scenario, scenario_b: Scenario) -> Dict[str, Any]:
    """
    Compare two scenarios and return deltas.
    """
    totals_a = calculate_scenario_totals(scenario_a)
    totals_b = calculate_scenario_totals(scenario_b)
    
    # Match items by code first, then by name
    matches_by_code = match_items_by_code(scenario_a, scenario_b)
    
    # Item-level comparison
    item_comparison = []
    for code, (item_id_a, item_id_b) in matches_by_code.items():
        item_a = next((item for item in scenario_a.items if item.item_id == item_id_a), None) if item_id_a else None
        item_b = next((item for item in scenario_b.items if item.item_id == item_id_b), None) if item_id_b else None
        
        total_a = totals_a['item_totals'].get(item_id_a, {'total': 0.0})['total'] if item_id_a else 0.0
        total_b = totals_b['item_totals'].get(item_id_b, {'total': 0.0})['total'] if item_id_b else 0.0
        
        delta = total_b - total_a
        delta_pct = (delta / total_a * 100) if total_a > 0 else (100 if total_b > 0 else 0)
        
        item_comparison.append({
            'code': code,
            'name_a': item_a.name if item_a else '',
            'name_b': item_b.name if item_b else '',
            'total_a': total_a,
            'total_b': total_b,
            'delta': delta,
            'delta_pct': delta_pct
        })
    
    # Category-level comparison
    cat_totals_a = aggregate_by_category(scenario_a, totals_a)
    cat_totals_b = aggregate_by_category(scenario_b, totals_b)
    
    category_comparison = []
    all_categories = set(cat_totals_a.keys()) | set(cat_totals_b.keys())
    
    for cat_code in all_categories:
        cat_a = cat_totals_a.get(cat_code, {'total': 0.0, 'name': ''})
        cat_b = cat_totals_b.get(cat_code, {'total': 0.0, 'name': ''})
        
        total_a = cat_a['total']
        total_b = cat_b['total']
        delta = total_b - total_a
        delta_pct = (delta / total_a * 100) if total_a > 0 else (100 if total_b > 0 else 0)
        
        category_comparison.append({
            'category_code': cat_code,
            'category_name': cat_b.get('name', cat_a.get('name', cat_code)),
            'total_a': total_a,
            'total_b': total_b,
            'delta': delta,
            'delta_pct': delta_pct
        })
    
    # Overall comparison
    overall = {
        'epc_total_a': totals_a['epc_total'],
        'epc_total_b': totals_b['epc_total'],
        'epc_delta': totals_b['epc_total'] - totals_a['epc_total'],
        'epc_delta_pct': ((totals_b['epc_total'] - totals_a['epc_total']) / totals_a['epc_total'] * 100) if totals_a['epc_total'] > 0 else 0,
        'project_total_a': totals_a['project_total'],
        'project_total_b': totals_b['project_total'],
        'project_delta': totals_b['project_total'] - totals_a['project_total'],
        'project_delta_pct': ((totals_b['project_total'] - totals_a['project_total']) / totals_a['project_total'] * 100) if totals_a['project_total'] > 0 else 0
    }
    
    return {
        'overall': overall,
        'by_category': category_comparison,
        'by_item': item_comparison
    }


def compare_three_scenarios(scenario_a: Scenario, scenario_b: Scenario, scenario_c: Scenario) -> Dict[str, Any]:
    """
    Compare three scenarios and return metrics for A, B, C.
    Returns structure with overall metrics and category comparison.
    """
    # Calculate totals for each scenario
    totals_a = calculate_scenario_totals(scenario_a)
    totals_b = calculate_scenario_totals(scenario_b)
    totals_c = calculate_scenario_totals(scenario_c)
    
    # Calculate normalization metrics for COP/kWp
    metrics_a = calculate_normalization_metrics(totals_a['project_total'], scenario_a)
    metrics_b = calculate_normalization_metrics(totals_b['project_total'], scenario_b)
    metrics_c = calculate_normalization_metrics(totals_c['project_total'], scenario_c)
    
    # Category-level comparison
    cat_totals_a = aggregate_by_category(scenario_a, totals_a)
    cat_totals_b = aggregate_by_category(scenario_b, totals_b)
    cat_totals_c = aggregate_by_category(scenario_c, totals_c)
    
    category_comparison = []
    all_categories = set(cat_totals_a.keys()) | set(cat_totals_b.keys()) | set(cat_totals_c.keys())
    
    for cat_code in all_categories:
        cat_a = cat_totals_a.get(cat_code, {'total': 0.0, 'name': ''})
        cat_b = cat_totals_b.get(cat_code, {'total': 0.0, 'name': ''})
        cat_c = cat_totals_c.get(cat_code, {'total': 0.0, 'name': ''})
        
        # Use the name from any scenario that has it
        cat_name = cat_c.get('name') or cat_b.get('name') or cat_a.get('name') or cat_code
        
        category_comparison.append({
            'category_code': cat_code,
            'category_name': cat_name,
            'total_a': cat_a['total'],
            'total_b': cat_b['total'],
            'total_c': cat_c['total']
        })
    
    # Add AIU and Total Proyecto as special categories
    category_comparison.append({
        'category_code': 'AIU',
        'category_name': 'AIU',
        'total_a': totals_a['aiu_total'],
        'total_b': totals_b['aiu_total'],
        'total_c': totals_c['aiu_total']
    })
    
    category_comparison.append({
        'category_code': 'TOTAL_PROJECT',
        'category_name': 'Total Proyecto',
        'total_a': totals_a['project_total'],
        'total_b': totals_b['project_total'],
        'total_c': totals_c['project_total']
    })
    
    # Overall comparison metrics
    overall = {
        'project_total_a': totals_a['project_total'],
        'project_total_b': totals_b['project_total'],
        'project_total_c': totals_c['project_total'],
        'client_total_a': totals_a['client_total'],
        'client_total_b': totals_b['client_total'],
        'client_total_c': totals_c['client_total'],
        'epc_total_a': totals_a['epc_total'],
        'epc_total_b': totals_b['epc_total'],
        'epc_total_c': totals_c['epc_total'],
        'cop_per_kwp_a': metrics_a.get('cop_per_kwp') or 0.0,
        'cop_per_kwp_b': metrics_b.get('cop_per_kwp') or 0.0,
        'cop_per_kwp_c': metrics_c.get('cop_per_kwp') or 0.0
    }
    
    return {
        'overall': overall,
        'by_category': category_comparison
    }


def compare_four_scenarios(scenario_a: Scenario, scenario_b: Scenario, scenario_c: Scenario, scenario_d: Scenario) -> Dict[str, Any]:
    """
    Compare four scenarios and return metrics for A, B, C, D.
    Returns structure with overall metrics and category comparison.
    """
    # Calculate totals for each scenario
    totals_a = calculate_scenario_totals(scenario_a)
    totals_b = calculate_scenario_totals(scenario_b)
    totals_c = calculate_scenario_totals(scenario_c)
    totals_d = calculate_scenario_totals(scenario_d)
    
    # Calculate normalization metrics for COP/kWp
    metrics_a = calculate_normalization_metrics(totals_a['project_total'], scenario_a)
    metrics_b = calculate_normalization_metrics(totals_b['project_total'], scenario_b)
    metrics_c = calculate_normalization_metrics(totals_c['project_total'], scenario_c)
    metrics_d = calculate_normalization_metrics(totals_d['project_total'], scenario_d)
    
    # Category-level comparison
    cat_totals_a = aggregate_by_category(scenario_a, totals_a)
    cat_totals_b = aggregate_by_category(scenario_b, totals_b)
    cat_totals_c = aggregate_by_category(scenario_c, totals_c)
    cat_totals_d = aggregate_by_category(scenario_d, totals_d)
    
    category_comparison = []
    all_categories = set(cat_totals_a.keys()) | set(cat_totals_b.keys()) | set(cat_totals_c.keys()) | set(cat_totals_d.keys())
    
    for cat_code in all_categories:
        cat_a = cat_totals_a.get(cat_code, {'total': 0.0, 'name': ''})
        cat_b = cat_totals_b.get(cat_code, {'total': 0.0, 'name': ''})
        cat_c = cat_totals_c.get(cat_code, {'total': 0.0, 'name': ''})
        cat_d = cat_totals_d.get(cat_code, {'total': 0.0, 'name': ''})
        
        # Use the name from any scenario that has it
        cat_name = cat_d.get('name') or cat_c.get('name') or cat_b.get('name') or cat_a.get('name') or cat_code
        
        category_comparison.append({
            'category_code': cat_code,
            'category_name': cat_name,
            'total_a': cat_a['total'],
            'total_b': cat_b['total'],
            'total_c': cat_c['total'],
            'total_d': cat_d['total']
        })
    
    # Add AIU and Total Proyecto as special categories
    category_comparison.append({
        'category_code': 'AIU',
        'category_name': 'AIU',
        'total_a': totals_a['aiu_total'],
        'total_b': totals_b['aiu_total'],
        'total_c': totals_c['aiu_total'],
        'total_d': totals_d['aiu_total']
    })
    
    category_comparison.append({
        'category_code': 'TOTAL_PROJECT',
        'category_name': 'Total Proyecto',
        'total_a': totals_a['project_total'],
        'total_b': totals_b['project_total'],
        'total_c': totals_c['project_total'],
        'total_d': totals_d['project_total']
    })
    
    # Overall comparison metrics
    overall = {
        'project_total_a': totals_a['project_total'],
        'project_total_b': totals_b['project_total'],
        'project_total_c': totals_c['project_total'],
        'project_total_d': totals_d['project_total'],
        'client_total_a': totals_a['client_total'],
        'client_total_b': totals_b['client_total'],
        'client_total_c': totals_c['client_total'],
        'client_total_d': totals_d['client_total'],
        'epc_total_a': totals_a['epc_total'],
        'epc_total_b': totals_b['epc_total'],
        'epc_total_c': totals_c['epc_total'],
        'epc_total_d': totals_d['epc_total'],
        'cop_per_kwp_a': metrics_a.get('cop_per_kwp') or 0.0,
        'cop_per_kwp_b': metrics_b.get('cop_per_kwp') or 0.0,
        'cop_per_kwp_c': metrics_c.get('cop_per_kwp') or 0.0,
        'cop_per_kwp_d': metrics_d.get('cop_per_kwp') or 0.0,
        'kwp_a': scenario_a.variables.dc_power_mwp,
        'kwp_b': scenario_b.variables.dc_power_mwp,
        'kwp_c': scenario_c.variables.dc_power_mwp,
        'kwp_d': scenario_d.variables.dc_power_mwp,
        'p50_mwh_a': scenario_a.variables.p50_mwh_per_year,
        'p50_mwh_b': scenario_b.variables.p50_mwh_per_year,
        'p50_mwh_c': scenario_c.variables.p50_mwh_per_year,
        'p50_mwh_d': scenario_d.variables.p50_mwh_per_year
    }
    
    return {
        'overall': overall,
        'by_category': category_comparison
    }
