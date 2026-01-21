"""
Plantilla inicial con datos de ejemplo para un presupuesto solar.
Categorías exactas según PDF.
"""

from budget_model import Scenario, Category, Item, AIUBaseRule, PercentageBase, DeliveryPoint, Incoterm


def get_seed_scenario() -> Scenario:
    """
    Retorna un escenario de ejemplo con categorías e ítems típicos de un proyecto solar.
    Categorías según PDF: A-N
    
    Returns:
        Scenario con datos iniciales
    """
    scenario = Scenario(
        name="Presupuesto Base",
        currency_input="COP",
        prices_include_vat=False,
        default_vat_rate=19.0,
        aiu_enabled=True,
        aiu_admin_pct=8.0,
        aiu_imprevistos_pct=5.0,
        aiu_utility_pct=10.0,
        aiu_base_rule=AIUBaseRule.DIRECT_COSTS_EXCL_CLIENT_PROVIDED,
        # Módulos porcentuales
        transport_pct=3.5,
        policies_pct=2.0,
        engineering_pct=5.0,
        pct_base_rule=PercentageBase.SUBTOTAL_BASE
    )
    
    # Crear categorías exactas del PDF
    categories = [
        # A) Paneles
        Category(category_id="cat_paneles", label="Paneles", is_equipment=True),
        # B) Inversores y comunicaciones
        Category(category_id="cat_inversores", label="Inversores y comunicaciones", is_equipment=True),
        # C) Estructuras
        Category(category_id="cat_estructuras", label="Estructuras", is_equipment=True),
        # D) Obra civil
        Category(category_id="cat_obra_civil", label="Obra civil", is_equipment=False),
        # E) Material DC / AC
        Category(category_id="cat_material_dc_ac", label="Material DC / AC", is_equipment=False),
        # F) Interconexión MT
        Category(category_id="cat_interconexion_mt", label="Interconexión MT", is_equipment=False),
        # G) Protecciones / Reconectador
        Category(category_id="cat_protecciones", label="Protecciones / Reconectador", is_equipment=True),
        # H) Estación / Transformador
        Category(category_id="cat_estacion", label="Estación / Transformador", is_equipment=True),
        # I) Alquiler de equipo (Montacarga)
        Category(category_id="cat_alquiler", label="Alquiler de equipo (Montacarga)", is_equipment=True),
        # J) Mano de obra
        Category(category_id="cat_mano_obra", label="Mano de obra", is_equipment=False),
        # K) Trámites / Regulación
        Category(category_id="cat_tramites", label="Trámites / Regulación", is_equipment=False),
        # L) Vigilancia / Seguridad
        Category(category_id="cat_vigilancia", label="Vigilancia / Seguridad", is_equipment=False),
    ]
    
    scenario.categories = categories
    
    # Crear ítems de ejemplo
    items = []
    order = 0
    
    # A) Paneles
    items.append(Item(
        item_id="item_paneles",
        item_code="PAN-001",
        category_id="cat_paneles",
        name="Paneles Solares",
        description="Panel solar 550Wp, monocristalino, 72 células",
        unit="kWp",
        qty=1000.0,
        unit_price=850000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # B) Inversores y comunicaciones
    items.append(Item(
        item_id="item_inversores",
        item_code="INV-001",
        category_id="cat_inversores",
        name="Inversores Centrales",
        description="Inversor central 1000kW, con sistema de comunicaciones",
        unit="kW",
        qty=800.0,
        unit_price=1200000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # C) Estructuras
    items.append(Item(
        item_id="item_estructura",
        item_code="EST-001",
        category_id="cat_estructuras",
        name="Estructura de Soporte",
        description="Estructura fija, acero galvanizado, incluye tornillería",
        unit="m2",
        qty=5000.0,
        unit_price=45000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # D) Obra civil
    items.append(Item(
        item_id="item_obra_civil",
        item_code="OC-001",
        category_id="cat_obra_civil",
        name="Obra Civil y Preparación de Terreno",
        description="Movimiento de tierras, nivelación, compactación, drenajes",
        unit="lote",
        qty=1.0,
        unit_price=150000000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=True,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # E) Material DC / AC
    items.append(Item(
        item_id="item_cables_dc",
        item_code="CAB-DC-001",
        category_id="cat_material_dc_ac",
        name="Cables DC",
        description="Cable solar 4mm2, 1000V DC, resistente a UV",
        unit="m",
        qty=15000.0,
        unit_price=8500.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    items.append(Item(
        item_id="item_cables_ac",
        item_code="CAB-AC-001",
        category_id="cat_material_dc_ac",
        name="Cables AC",
        description="Cable AC 35mm2, 600V, para interconexión",
        unit="m",
        qty=5000.0,
        unit_price=12000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # F) Interconexión MT
    items.append(Item(
        item_id="item_conexion_mt",
        item_code="MT-001",
        category_id="cat_interconexion_mt",
        name="Conexión a Red MT",
        description="Obra civil, postes, conductores, protecciones MT",
        unit="UND",
        qty=1.0,
        unit_price=25000000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=True,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # G) Protecciones / Reconectador
    items.append(Item(
        item_id="item_reconectador",
        item_code="PROT-001",
        category_id="cat_protecciones",
        name="Reconectador",
        description="Reconectador automático 13.2kV, con protecciones",
        unit="UND",
        qty=1.0,
        unit_price=18000000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # H) Estación / Transformador
    items.append(Item(
        item_id="item_trafo",
        item_code="TRAFO-001",
        category_id="cat_estacion",
        name="Transformador",
        description="Transformador 1000kVA, 13.2kV/480V, tipo seco",
        unit="kVA",
        qty=1000.0,
        unit_price=35000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.CIF,
        includes_transport_to_site=True,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # I) Alquiler de equipo (Montacarga)
    items.append(Item(
        item_id="item_montacarga",
        item_code="ALQ-001",
        category_id="cat_alquiler",
        name="Alquiler Montacarga",
        description="Alquiler montacarga 5 toneladas, 3 meses",
        unit="mes",
        qty=3.0,
        unit_price=2500000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # J) Mano de obra
    items.append(Item(
        item_id="item_instalacion",
        item_code="MO-001",
        category_id="cat_mano_obra",
        name="Instalación y Montaje",
        description="Mano de obra especializada, instalación paneles, inversores, cableado",
        unit="kWp",
        qty=1000.0,
        unit_price=250000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=True,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    # K) Trámites / Regulación
    items.append(Item(
        item_id="item_retie",
        item_code="TRAM-001",
        category_id="cat_tramites",
        name="RETIE",
        description="Registro RETIE, certificación de instalación",
        unit="UND",
        qty=1.0,
        unit_price=5000000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.NA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    items.append(Item(
        item_id="item_estudios",
        item_code="TRAM-002",
        category_id="cat_tramites",
        name="Estudios Técnicos",
        description="Estudios de ingeniería, diseño, planos, memorias de cálculo",
        unit="UND",
        qty=1.0,
        unit_price=15000000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.NA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    items.append(Item(
        item_id="item_medidor",
        item_code="TRAM-003",
        category_id="cat_tramites",
        name="Medidor Bidireccional",
        description="Medidor bidireccional, instalación y configuración",
        unit="UND",
        qty=1.0,
        unit_price=3500000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=True,
        includes_installation=True,
        includes_commissioning=True,
        order=order
    ))
    order += 1
    
    # L) Vigilancia / Seguridad
    items.append(Item(
        item_id="item_vigilancia",
        item_code="VIG-001",
        category_id="cat_vigilancia",
        name="Vigilancia y Seguridad",
        description="Servicio de vigilancia 24/7, 12 meses",
        unit="mes",
        qty=12.0,
        unit_price=2000000.0,
        price_includes_vat=False,
        vat_rate=19.0,
        aiu_applicable=True,
        client_provided=False,
        delivery_point=DeliveryPoint.OBRA,
        incoterm=Incoterm.NA,
        includes_transport_to_site=False,
        includes_installation=False,
        includes_commissioning=False,
        order=order
    ))
    order += 1
    
    scenario.items = items
    
    return scenario
