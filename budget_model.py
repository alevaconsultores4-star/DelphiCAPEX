"""
Modelo de datos y lógica de cálculo para presupuestos.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class AIUBaseRule(str, Enum):
    """Reglas para calcular la base de AIU."""
    DIRECT_COSTS_EXCL_VAT = "Costo directo (sin IVA)"
    DIRECT_COSTS_EXCL_CLIENT_PROVIDED = "Costo directo (sin IVA) excluyendo ítems 'Cliente compra'"
    ONLY_SERVICES_LABOR = "Solo servicios y mano de obra (excluye categorías de equipos)"


class PercentageBase(str, Enum):
    """Bases para calcular ítems porcentuales."""
    SUBTOTAL_BASE = "Subtotal base (sin IVA)"
    SUBTOTAL_TOTAL = "Subtotal total (con IVA)"
    BASE_AIU = "Base AIU"


class DeliveryPoint(str, Enum):
    """Puntos de entrega."""
    PUERTO = "Puesto en puerto"
    BODEGA = "Puesto en bodega"
    OBRA = "Puesto en obra"
    INSTALADO = "Instalado"


class Incoterm(str, Enum):
    """Términos de comercio internacional."""
    EXW = "EXW"
    FOB = "FOB"
    CIF = "CIF"
    DDP = "DDP"
    NA = "NA"


@dataclass
class Item:
    """Representa un ítem del presupuesto."""
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    item_code: Optional[str] = None
    category_id: str = ""
    name: str = ""
    description: str = ""  # Descripción / Especificación
    unit: str = "UND"
    qty: float = 0.0
    unit_price: float = 0.0
    price_includes_vat: bool = False
    vat_rate: float = 19.0
    aiu_applicable: bool = True
    client_provided: bool = False
    pass_through: bool = False
    notes: str = ""
    is_percentage_item: bool = False
    pct_rate: float = 0.0
    pct_base: str = PercentageBase.SUBTOTAL_BASE
    order: int = 0  # Para mantener orden de visualización
    # Campos de alcance/logística
    delivery_point: str = DeliveryPoint.OBRA
    incoterm: str = Incoterm.NA
    includes_transport_to_site: bool = False
    includes_installation: bool = False
    includes_commissioning: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el ítem a diccionario para serialización."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """Crea un ítem desde un diccionario."""
        return cls(**data)


@dataclass
class Category:
    """Representa una categoría de ítems."""
    category_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    is_equipment: bool = False  # Para regla "Only services/labor"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la categoría a diccionario."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """Crea una categoría desde un diccionario."""
        return cls(**data)


@dataclass
class Scenario:
    """Representa un escenario de presupuesto."""
    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    currency_input: str = "COP"
    prices_include_vat: bool = False
    default_vat_rate: float = 19.0
    aiu_enabled: bool = False
    aiu_admin_pct: float = 0.0
    aiu_imprevistos_pct: float = 0.0
    aiu_utility_pct: float = 0.0
    aiu_base_rule: str = AIUBaseRule.DIRECT_COSTS_EXCL_VAT
    # Módulos porcentuales (Transporte, Pólizas, Ingeniería)
    transport_pct: float = 0.0
    policies_pct: float = 0.0
    engineering_pct: float = 0.0
    pct_base_rule: str = PercentageBase.SUBTOTAL_BASE
    # Variables clave del proyecto
    potencia_total_kwac: float = 0.0
    energia_p50_mwh_anio: float = 0.0
    pnom_total_kwp: float = 0.0
    produccion_especifica_kwh_kwp_anio: float = 0.0
    categories: List[Category] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el escenario a diccionario para serialización."""
        data = asdict(self)
        data['categories'] = [cat.to_dict() for cat in self.categories]
        data['items'] = [item.to_dict() for item in self.items]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Scenario':
        """Crea un escenario desde un diccionario."""
        categories = [Category.from_dict(c) for c in data.get('categories', [])]
        items = [Item.from_dict(i) for i in data.get('items', [])]
        
        scenario = cls(
            scenario_id=data.get('scenario_id', str(uuid.uuid4())),
            name=data.get('name', ''),
            currency_input=data.get('currency_input', 'COP'),
            prices_include_vat=data.get('prices_include_vat', False),
            default_vat_rate=data.get('default_vat_rate', 19.0),
            aiu_enabled=data.get('aiu_enabled', False),
            aiu_admin_pct=data.get('aiu_admin_pct', 0.0),
            aiu_imprevistos_pct=data.get('aiu_imprevistos_pct', 0.0),
            aiu_utility_pct=data.get('aiu_utility_pct', 0.0),
            aiu_base_rule=data.get('aiu_base_rule', AIUBaseRule.DIRECT_COSTS_EXCL_VAT),
            transport_pct=data.get('transport_pct', 0.0),
            policies_pct=data.get('policies_pct', 0.0),
            engineering_pct=data.get('engineering_pct', 0.0),
            pct_base_rule=data.get('pct_base_rule', PercentageBase.SUBTOTAL_BASE),
            potencia_total_kwac=data.get('potencia_total_kwac', 0.0),
            energia_p50_mwh_anio=data.get('energia_p50_mwh_anio', 0.0),
            pnom_total_kwp=data.get('pnom_total_kwp', 0.0),
            produccion_especifica_kwh_kwp_anio=data.get('produccion_especifica_kwh_kwp_anio', 0.0),
            categories=categories,
            items=items
        )
        return scenario


@dataclass
class Project:
    """Representa un proyecto con múltiples escenarios."""
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    scenarios: List[Scenario] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el proyecto a diccionario para serialización."""
        data = asdict(self)
        data['scenarios'] = [scenario.to_dict() for scenario in self.scenarios]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Crea un proyecto desde un diccionario."""
        scenarios = [Scenario.from_dict(s) for s in data.get('scenarios', [])]
        
        project = cls(
            project_id=data.get('project_id', str(uuid.uuid4())),
            name=data.get('name', ''),
            created_at=data.get('created_at', datetime.now().isoformat()),
            updated_at=data.get('updated_at', datetime.now().isoformat()),
            scenarios=scenarios
        )
        return project


# Funciones de cálculo

def calculate_item_totals(item: Item, scenario: Scenario) -> Dict[str, float]:
    """
    Calcula los totales de un ítem (base, IVA, total).
    
    Args:
        item: El ítem a calcular
        scenario: El escenario que contiene los defaults
    
    Returns:
        Dict con: base_unit, vat_unit, total_unit, base_line, vat_line, total_line
    """
    # Si es ítem porcentual, el cálculo se hace después de calcular subtotales
    if item.is_percentage_item:
        return {
            'base_unit': 0.0,
            'vat_unit': 0.0,
            'total_unit': 0.0,
            'base_line': 0.0,
            'vat_line': 0.0,
            'total_line': 0.0
        }
    
    # Usar defaults del escenario si no están definidos en el ítem
    price_includes_vat = item.price_includes_vat if hasattr(item, 'price_includes_vat') else scenario.prices_include_vat
    vat_rate = item.vat_rate if item.vat_rate > 0 else scenario.default_vat_rate
    
    unit_price = item.unit_price
    qty = item.qty
    
    if price_includes_vat:
        # Precio incluye IVA: calcular base
        # total = base * (1 + vat_rate/100)
        # base = total / (1 + vat_rate/100)
        base_unit = unit_price / (1 + vat_rate / 100.0)
        vat_unit = unit_price - base_unit
        total_unit = unit_price
    else:
        # Precio no incluye IVA: calcular IVA
        base_unit = unit_price
        vat_unit = base_unit * (vat_rate / 100.0)
        total_unit = base_unit + vat_unit
    
    # Totales de línea
    base_line = base_unit * qty
    vat_line = vat_unit * qty
    total_line = total_unit * qty
    
    return {
        'base_unit': base_unit,
        'vat_unit': vat_unit,
        'total_unit': total_unit,
        'base_line': base_line,
        'vat_line': vat_line,
        'total_line': total_line
    }


def calculate_percentage_item_value(item: Item, base_value: float) -> Dict[str, float]:
    """
    Calcula el valor monetario de un ítem porcentual.
    
    Args:
        item: El ítem porcentual
        base_value: El valor base sobre el cual calcular el porcentaje
    
    Returns:
        Dict con: base_line, vat_line, total_line
    """
    if not item.is_percentage_item:
        return {'base_line': 0.0, 'vat_line': 0.0, 'total_line': 0.0}
    
    # Calcular valor base del porcentaje
    percentage_value = base_value * (item.pct_rate / 100.0)
    
    # Aplicar IVA al valor porcentual
    vat_rate = item.vat_rate if item.vat_rate > 0 else 19.0
    price_includes_vat = item.price_includes_vat if hasattr(item, 'price_includes_vat') else False
    
    if price_includes_vat:
        base_line = percentage_value / (1 + vat_rate / 100.0)
        vat_line = percentage_value - base_line
        total_line = percentage_value
    else:
        base_line = percentage_value
        vat_line = base_line * (vat_rate / 100.0)
        total_line = base_line + vat_line
    
    return {
        'base_line': base_line,
        'vat_line': vat_line,
        'total_line': total_line
    }


def calculate_percentage_module_value(pct_rate: float, base_value: float, vat_rate: float = 19.0) -> Dict[str, float]:
    """
    Calcula el valor de un módulo porcentual (Transporte, Pólizas, Ingeniería).
    
    Args:
        pct_rate: Porcentaje a aplicar
        base_value: Valor base
        vat_rate: Tasa de IVA
    
    Returns:
        Dict con base_line, vat_line, total_line
    """
    if pct_rate == 0.0:
        return {'base_line': 0.0, 'vat_line': 0.0, 'total_line': 0.0}
    
    # Calcular valor base del porcentaje
    percentage_value = base_value * (pct_rate / 100.0)
    
    # Aplicar IVA (asumimos que no incluye IVA)
    base_line = percentage_value
    vat_line = base_line * (vat_rate / 100.0)
    total_line = base_line + vat_line
    
    return {
        'base_line': base_line,
        'vat_line': vat_line,
        'total_line': total_line
    }


def calculate_scenario_summary(scenario: Scenario) -> Dict[str, float]:
    """
    Calcula el resumen financiero completo del escenario.
    
    Args:
        scenario: El escenario a calcular
    
    Returns:
        Dict con todos los totales y desgloses
    """
    # Calcular todos los ítems NO porcentuales (costo directo)
    items_totals = {}
    direct_cost_base = 0.0
    direct_cost_vat = 0.0
    direct_cost_total = 0.0
    
    # Calcular total contrato EPC (excluyendo client_provided) y CAPEX Cliente
    epc_base = 0.0
    epc_vat = 0.0
    epc_total = 0.0
    
    # Calcular CAPEX Cliente (solo ítems client_provided)
    client_capex_base = 0.0
    client_capex_vat = 0.0
    client_capex_total = 0.0
    
    for item in scenario.items:
        if item.is_percentage_item:
            continue
        
        totals = calculate_item_totals(item, scenario)
        items_totals[item.item_id] = totals
        
        direct_cost_base += totals['base_line']
        direct_cost_vat += totals['vat_line']
        direct_cost_total += totals['total_line']
        
        # Para EPC, excluir client_provided
        if not item.client_provided:
            epc_base += totals['base_line']
            epc_vat += totals['vat_line']
            epc_total += totals['total_line']
        
        # Para CAPEX Cliente, incluir solo client_provided
        if item.client_provided:
            client_capex_base += totals['base_line']
            client_capex_vat += totals['vat_line']
            client_capex_total += totals['total_line']
    
    # Calcular módulos porcentuales (Transporte, Pólizas, Ingeniería) PRIMERO
    # Determinar base según pct_base_rule
    if scenario.pct_base_rule == PercentageBase.SUBTOTAL_BASE:
        pct_base_value = direct_cost_base
    elif scenario.pct_base_rule == PercentageBase.SUBTOTAL_TOTAL:
        pct_base_value = direct_cost_total
    elif scenario.pct_base_rule == PercentageBase.BASE_AIU:
        # Si la regla es BASE_AIU, necesitamos calcular una base AIU preliminar
        # pero esto crea dependencia circular. Por ahora, usar direct_cost_base como fallback
        # TODO: Revisar si esta regla tiene sentido con el nuevo cálculo
        pct_base_value = direct_cost_base
    else:
        pct_base_value = direct_cost_base
    
    transport_totals = calculate_percentage_module_value(
        scenario.transport_pct, pct_base_value, scenario.default_vat_rate
    )
    policies_totals = calculate_percentage_module_value(
        scenario.policies_pct, pct_base_value, scenario.default_vat_rate
    )
    engineering_totals = calculate_percentage_module_value(
        scenario.engineering_pct, pct_base_value, scenario.default_vat_rate
    )
    
    # Sumar módulos porcentuales al costo directo
    total_base = direct_cost_base + transport_totals['base_line'] + policies_totals['base_line'] + engineering_totals['base_line']
    total_vat = direct_cost_vat + transport_totals['vat_line'] + policies_totals['vat_line'] + engineering_totals['vat_line']
    total_direct = direct_cost_total + transport_totals['total_line'] + policies_totals['total_line'] + engineering_totals['total_line']
    
    # Calcular base AIU sobre el total (directo + indirectos) CON IVA incluido
    # Aplicando las reglas de exclusión proporcionalmente
    aiu_base = calculate_aiu_base_from_total_with_vat(scenario, total_direct, items_totals)
    
    # Calcular componentes AIU
    aiu_admin = 0.0
    aiu_imprevistos = 0.0
    aiu_utility = 0.0
    aiu_total = 0.0
    
    if scenario.aiu_enabled and aiu_base > 0:
        aiu_admin = aiu_base * (scenario.aiu_admin_pct / 100.0)
        aiu_imprevistos = aiu_base * (scenario.aiu_imprevistos_pct / 100.0)
        aiu_utility = aiu_base * (scenario.aiu_utility_pct / 100.0)
        aiu_total = aiu_admin + aiu_imprevistos + aiu_utility
    
    # Agregar módulos porcentuales y AIU al Total Contrato EPC Base
    # EPC incluye: ítems NO client_provided + módulos porcentuales + AIU
    epc_base = epc_base + transport_totals['base_line'] + policies_totals['base_line'] + engineering_totals['base_line']
    epc_vat = epc_vat + transport_totals['vat_line'] + policies_totals['vat_line'] + engineering_totals['vat_line']
    epc_total = epc_total + transport_totals['total_line'] + policies_totals['total_line'] + engineering_totals['total_line']
    # AIU no tiene IVA, solo se suma al total
    epc_total = epc_total + aiu_total
    
    # Total general = total directo + AIU (AIU no lleva IVA)
    grand_total = total_direct + aiu_total
    
    return {
        'direct_cost_base': direct_cost_base,
        'direct_cost_vat': direct_cost_vat,
        'direct_cost_total': direct_cost_total,
        'total_base': total_base,
        'total_vat': total_vat,
        'total_direct': total_direct,
        'transport_base': transport_totals['base_line'],
        'transport_vat': transport_totals['vat_line'],
        'transport_total': transport_totals['total_line'],
        'policies_base': policies_totals['base_line'],
        'policies_vat': policies_totals['vat_line'],
        'policies_total': policies_totals['total_line'],
        'engineering_base': engineering_totals['base_line'],
        'engineering_vat': engineering_totals['vat_line'],
        'engineering_total': engineering_totals['total_line'],
        'aiu_base': aiu_base,
        'aiu_admin': aiu_admin,
        'aiu_imprevistos': aiu_imprevistos,
        'aiu_utility': aiu_utility,
        'aiu_total': aiu_total,
        'grand_total': grand_total,
        'epc_base': epc_base,
        'epc_vat': epc_vat,
        'epc_total': epc_total,
        'client_capex_base': client_capex_base,
        'client_capex_vat': client_capex_vat,
        'client_capex_total': client_capex_total,
        'items_totals': items_totals
    }


def calculate_aiu_base(
    scenario: Scenario,
    subtotal_base: float,
    subtotal_vat: float,
    subtotal_total: float,
    items_totals: Dict[str, Dict[str, float]]
) -> float:
    """
    Calcula la base para AIU según la regla configurada.
    
    Args:
        scenario: El escenario
        subtotal_base: Subtotal base sin IVA
        subtotal_vat: Subtotal IVA
        subtotal_total: Subtotal con IVA
        items_totals: Diccionario con totales por ítem
    
    Returns:
        float: Base AIU calculada
    """
    if not scenario.aiu_enabled:
        return 0.0
    
    rule = scenario.aiu_base_rule
    
    if rule == AIUBaseRule.DIRECT_COSTS_EXCL_VAT or rule == "Costo directo (sin IVA)":
        # Todos los costos directos sin IVA, excluyendo los que no aplican
        base = 0.0
        for item in scenario.items:
            if item.aiu_applicable and not item.client_provided and not item.pass_through and not item.is_percentage_item:
                if item.item_id in items_totals:
                    base += items_totals[item.item_id]['base_line']
        return base
    
    elif rule == AIUBaseRule.DIRECT_COSTS_EXCL_CLIENT_PROVIDED or rule == "Costo directo (sin IVA) excluyendo ítems 'Cliente compra'":
        # Costos directos sin IVA, excluyendo client_provided
        base = 0.0
        for item in scenario.items:
            if not item.client_provided and not item.pass_through and not item.is_percentage_item:
                if item.item_id in items_totals:
                    base += items_totals[item.item_id]['base_line']
        return base
    
    elif rule == AIUBaseRule.ONLY_SERVICES_LABOR or rule == "Solo servicios y mano de obra (excluye categorías de equipos)":
        # Solo servicios/labor, excluyendo categorías de equipos
        base = 0.0
        # Obtener IDs de categorías de equipos
        equipment_category_ids = {
            cat.category_id for cat in scenario.categories if cat.is_equipment
        }
        
        for item in scenario.items:
            if (item.aiu_applicable and 
                not item.client_provided and 
                not item.pass_through and
                not item.is_percentage_item and
                item.category_id not in equipment_category_ids):
                if item.item_id in items_totals:
                    base += items_totals[item.item_id]['base_line']
        return base
    
    else:
        # Default: direct costs excl VAT
        base = 0.0
        for item in scenario.items:
            if item.aiu_applicable and not item.client_provided and not item.pass_through and not item.is_percentage_item:
                if item.item_id in items_totals:
                    base += items_totals[item.item_id]['base_line']
        return base


def calculate_aiu_base_from_total_with_vat(
    scenario: Scenario,
    total_direct: float,  # Costo directo + módulos porcentuales, CON IVA incluido
    items_totals: Dict[str, Dict[str, float]]
) -> float:
    """
    Calcula la base AIU sobre el total (directo + indirectos) con IVA incluido,
    aplicando las reglas de exclusión proporcionalmente.
    
    Args:
        scenario: El escenario
        total_direct: Total directo + módulos porcentuales, CON IVA incluido
        items_totals: Diccionario con totales por ítem
    
    Returns:
        float: Base AIU calculada sobre el total con IVA, aplicando reglas de exclusión
    """
    if not scenario.aiu_enabled:
        return 0.0
    
    if total_direct == 0.0:
        return 0.0
    
    rule = scenario.aiu_base_rule
    
    # Calcular qué parte del costo directo está incluida según las reglas
    included_direct_cost_total = 0.0
    total_direct_cost_total = 0.0
    
    for item in scenario.items:
        if item.is_percentage_item:
            continue
        
        if item.item_id in items_totals:
            total_direct_cost_total += items_totals[item.item_id]['total_line']
            
            # Aplicar reglas de inclusión según el tipo de regla
            include_item = False
            
            if rule == AIUBaseRule.DIRECT_COSTS_EXCL_VAT or rule == "Costo directo (sin IVA)":
                include_item = (item.aiu_applicable and 
                              not item.client_provided and 
                              not item.pass_through)
            elif rule == AIUBaseRule.DIRECT_COSTS_EXCL_CLIENT_PROVIDED or rule == "Costo directo (sin IVA) excluyendo ítems 'Cliente compra'":
                include_item = (not item.client_provided and 
                              not item.pass_through)
            elif rule == AIUBaseRule.ONLY_SERVICES_LABOR or rule == "Solo servicios y mano de obra (excluye categorías de equipos)":
                # Obtener IDs de categorías de equipos
                equipment_category_ids = {
                    cat.category_id for cat in scenario.categories if cat.is_equipment
                }
                include_item = (item.aiu_applicable and 
                              not item.client_provided and 
                              not item.pass_through and
                              item.category_id not in equipment_category_ids)
            else:
                # Default: direct costs excl VAT
                include_item = (item.aiu_applicable and 
                              not item.client_provided and 
                              not item.pass_through)
            
            if include_item:
                included_direct_cost_total += items_totals[item.item_id]['total_line']
    
    # Calcular el factor de inclusión (proporción del costo directo que está incluido)
    if total_direct_cost_total > 0:
        inclusion_factor = included_direct_cost_total / total_direct_cost_total
    else:
        inclusion_factor = 1.0
    
    # Aplicar el factor de inclusión al total_direct (que incluye módulos porcentuales con IVA)
    # Esto calcula qué parte del total (directo + indirectos) corresponde a los ítems incluidos
    aiu_base = total_direct * inclusion_factor
    
    return aiu_base


def aggregate_by_category(scenario: Scenario, summary: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    """
    Agrupa los totales por categoría.
    
    Args:
        scenario: El escenario
        summary: El resumen calculado con calculate_scenario_summary
    
    Returns:
        Dict con estructura: {category_id: {'base': float, 'vat': float, 'total': float}}
    """
    category_totals = {}
    items_totals = summary.get('items_totals', {})
    
    for item in scenario.items:
        category_id = item.category_id or 'uncategorized'
        category_name = 'Sin categoría'
        
        # Buscar nombre de categoría
        for cat in scenario.categories:
            if cat.category_id == category_id:
                category_name = cat.label
                break
        
        if category_id not in category_totals:
            category_totals[category_id] = {
                'name': category_name,
                'base': 0.0,
                'vat': 0.0,
                'total': 0.0
            }
        
        if item.item_id in items_totals:
            totals = items_totals[item.item_id]
            category_totals[category_id]['base'] += totals['base_line']
            category_totals[category_id]['vat'] += totals['vat_line']
            category_totals[category_id]['total'] += totals['total_line']
    
    return category_totals
