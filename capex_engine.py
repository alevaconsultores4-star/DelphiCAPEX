"""
CAPEX calculation engine with AIU, VAT, and totals.
"""

from typing import Dict, List, Optional
from models import Scenario, ScenarioItem, PricingMode


def calculate_item_total(item: ScenarioItem, scenario_kwp: float) -> Dict[str, float]:
    """
    Calculate item totals based on pricing mode and whether price includes VAT.
    Returns: {'base': float, 'vat': float, 'total': float}
    """
    # Calculate total based on pricing mode
    if item.pricing_mode == PricingMode.PER_KWP:
        total = scenario_kwp * item.price
    else:  # UNIT mode
        total = item.qty * item.price
    
    # Calculate base and VAT based on whether price includes VAT
    if item.price_includes_vat:
        # Price includes VAT: extract base and VAT from total
        # total = base * (1 + vat_rate/100)
        # base = total / (1 + vat_rate/100)
        if item.vat_rate > 0:
            base_total = total / (1 + item.vat_rate / 100.0)
            vat_total = total - base_total
        else:
            base_total = total
            vat_total = 0.0
    else:
        # Price does not include VAT: add VAT on top
        base_total = total
        vat_total = base_total * (item.vat_rate / 100.0)
        total = base_total + vat_total
    
    return {
        'base': base_total,
        'vat': vat_total,
        'total': total
    }


def calculate_implied_unit_price(item: ScenarioItem, scenario_kwp: float) -> float:
    """Calculate implied unit price for PER_KWP mode."""
    if item.pricing_mode == PricingMode.PER_KWP:
        return item.price if scenario_kwp > 0 else 0.0
    return item.price


def calculate_scenario_totals(scenario: Scenario) -> Dict[str, float]:
    """
    Calculate all totals for a scenario.
    Returns comprehensive totals dictionary.
    """
    scenario_kwp = scenario.variables.dc_power_mwp * 1000.0  # Convert MWp to kWp
    
    # Calculate item totals
    item_totals = {}
    for item in scenario.items:
        item_totals[item.item_id] = calculate_item_total(item, scenario_kwp)
    
    # Separate EPC items (not client_pays) from client-paid items
    epc_items = [item for item in scenario.items if not item.client_pays]
    client_items = [item for item in scenario.items if item.client_pays]
    
    # Direct EPC costs
    direct_epc_base = sum(item_totals[item.item_id]['base'] for item in epc_items)
    direct_epc_vat = sum(item_totals[item.item_id]['vat'] for item in epc_items)
    direct_epc_total = sum(item_totals[item.item_id]['total'] for item in epc_items)
    
    # Client-paid costs
    client_base = sum(item_totals[item.item_id]['base'] for item in client_items)
    client_vat = sum(item_totals[item.item_id]['vat'] for item in client_items)
    client_total = sum(item_totals[item.item_id]['total'] for item in client_items)
    
    # Calculate AIU directly as percentage of Total Direct Cost (Inc VAT)
    # Ignore per-item scaling factors - use direct_epc_total as base
    aiu_admin = 0.0
    aiu_imprev = 0.0
    aiu_util = 0.0
    
    if scenario.aiu_config.enabled:
        # Use direct_epc_total (inc VAT) as base, excluding client_pays items
        # direct_epc_total already excludes client_pays items
        aiu_base = direct_epc_total
        
        aiu_admin = aiu_base * (scenario.aiu_config.admin_pct / 100.0)
        aiu_imprev = aiu_base * (scenario.aiu_config.imprev_pct / 100.0)
        aiu_util = aiu_base * (scenario.aiu_config.util_pct / 100.0)
    
    aiu_total = aiu_admin + aiu_imprev + aiu_util
    
    # For backward compatibility, set base_a, base_i, base_u to direct_epc_total
    # (these are no longer used in calculation but may be referenced elsewhere)
    base_a = direct_epc_total if scenario.aiu_config.enabled else 0.0
    base_i = direct_epc_total if scenario.aiu_config.enabled else 0.0
    base_u = direct_epc_total if scenario.aiu_config.enabled else 0.0
    
    # VAT on Utilidad
    vat_on_utilidad = 0.0
    if scenario.vat_config.vat_on_utilidad_enabled:
        vat_on_utilidad = aiu_util * (scenario.vat_config.vat_rate_utilidad / 100.0)
    
    # EPC totals
    epc_base = direct_epc_base + aiu_total
    epc_vat = direct_epc_vat + vat_on_utilidad
    epc_total = epc_base + epc_vat
    
    # Project totals (EPC + client-paid)
    project_base = epc_base + client_base
    project_vat = epc_vat + client_vat
    project_total = project_base + project_vat
    
    return {
        'item_totals': item_totals,
        'direct_epc_base': direct_epc_base,
        'direct_epc_vat': direct_epc_vat,
        'direct_epc_total': direct_epc_total,
        'client_base': client_base,
        'client_vat': client_vat,
        'client_total': client_total,
        'aiu_base_a': base_a,
        'aiu_base_i': base_i,
        'aiu_base_u': base_u,
        'aiu_admin': aiu_admin,
        'aiu_imprev': aiu_imprev,
        'aiu_util': aiu_util,
        'aiu_total': aiu_total,
        'vat_on_utilidad': vat_on_utilidad,
        'epc_base': epc_base,
        'epc_vat': epc_vat,
        'epc_total': epc_total,
        'project_base': project_base,
        'project_vat': project_vat,
        'project_total': project_total
    }


def calculate_normalization_metrics(
    capex_value: float,
    scenario: Scenario
) -> Dict[str, Optional[float]]:
    """
    Calculate normalization metrics (COP/kWp, COP/MWac, COP/MWh).
    Returns dict with metrics or None if denominator is zero.
    """
    dc_kwp = scenario.variables.dc_power_mwp * 1000.0
    ac_mw = scenario.variables.ac_power_mw
    p50_mwh = scenario.variables.p50_mwh_per_year
    p90_mwh = scenario.variables.p90_mwh_per_year
    
    cop_per_kwp = capex_value / dc_kwp if dc_kwp > 0 else None
    cop_per_mwac = capex_value / ac_mw if ac_mw > 0 else None
    cop_per_mwh_p50 = capex_value / p50_mwh if p50_mwh > 0 else None
    cop_per_mwh_p90 = capex_value / p90_mwh if p90_mwh > 0 else None
    
    return {
        'cop_per_kwp': cop_per_kwp,
        'cop_per_mwac': cop_per_mwac,
        'cop_per_mwh_p50': cop_per_mwh_p50,
        'cop_per_mwh_p90': cop_per_mwh_p90
    }


def calculate_item_cop_per_kwp(item_total: float, scenario_kwp: float) -> Optional[float]:
    """Calculate COP/kWp for a single item."""
    return item_total / scenario_kwp if scenario_kwp > 0 else None


def aggregate_by_category(scenario: Scenario, totals: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    """
    Aggregate totals by category.
    Returns: {category_code: {'base': float, 'vat': float, 'total': float, 'name': str}}
    """
    from library_service import get_category_by_code
    
    category_totals = {}
    item_totals = totals.get('item_totals', {})
    
    for item in scenario.items:
        category_code = item.category_code or 'UNCATEGORIZED'
        category = get_category_by_code(category_code)
        category_name = category.name_es if category else category_code
        
        if category_code not in category_totals:
            category_totals[category_code] = {
                'base': 0.0,
                'vat': 0.0,
                'total': 0.0,
                'name': category_name
            }
        
        item_total = item_totals.get(item.item_id, {'base': 0.0, 'vat': 0.0, 'total': 0.0})
        category_totals[category_code]['base'] += item_total['base']
        category_totals[category_code]['vat'] += item_total['vat']
        category_totals[category_code]['total'] += item_total['total']
    
    return category_totals
