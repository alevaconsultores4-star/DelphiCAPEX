"""
Aplicación Streamlit para comparación de presupuestos por proyecto y escenario.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, List, Any
import uuid
from datetime import datetime
import hashlib
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

from budget_model import (
    Project, Scenario, Item, Category,
    AIUBaseRule, PercentageBase, DeliveryPoint, Incoterm,
    calculate_item_totals, calculate_scenario_summary,
    aggregate_by_category, calculate_percentage_item_value
)
from storage import (
    load_projects_index, save_projects_index,
    load_project, save_project, create_project,
    delete_project, duplicate_scenario, get_all_projects,
    copy_scenario_to_project
)
from formatting import format_cop, format_number, format_percentage, parse_number
from seed_template import get_seed_scenario
from ai_analyst import analyze_capex_diff


# Configuración de página
st.set_page_config(
    page_title="Comparador de Presupuestos",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar estado de sesión
if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None
if 'current_scenario_id' not in st.session_state:
    st.session_state.current_scenario_id = None
if 'edited_items' not in st.session_state:
    st.session_state.edited_items = None
if 'show_new_scenario' not in st.session_state:
    st.session_state.show_new_scenario = False
if 'show_dup_scenario' not in st.session_state:
    st.session_state.show_dup_scenario = False
if 'show_new_project' not in st.session_state:
    st.session_state.show_new_project = False


def get_current_project() -> Optional[Project]:
    """Obtiene el proyecto actual desde el estado de sesión."""
    if st.session_state.current_project_id:
        return load_project(st.session_state.current_project_id)
    return None


def get_current_scenario() -> Optional[Scenario]:
    """Obtiene el escenario actual desde el proyecto actual."""
    project = get_current_project()
    if project and st.session_state.current_scenario_id:
        for scenario in project.scenarios:
            if scenario.scenario_id == st.session_state.current_scenario_id:
                return scenario
    return None


def render_sidebar():
    """Renderiza el panel lateral izquierdo."""
    st.sidebar.title("📊 Presupuestos")
    
    # Selector de proyecto
    projects = get_all_projects()
    project_options = {p['name']: p['project_id'] for p in projects}
    
    if projects:
        selected_project_name = st.sidebar.selectbox(
            "Proyecto",
            options=[""] + list(project_options.keys()),
            index=0 if not st.session_state.current_project_id else 
                  list(project_options.keys()).index(
                      next(p['name'] for p in projects if p['project_id'] == st.session_state.current_project_id)
                  ) + 1 if st.session_state.current_project_id in project_options.values() else 0
        )
        
        if selected_project_name:
            st.session_state.current_project_id = project_options[selected_project_name]
        else:
            st.session_state.current_project_id = None
            st.session_state.current_scenario_id = None
    else:
        st.sidebar.info("No hay proyectos. Crea uno nuevo.")
        st.session_state.current_project_id = None
        st.session_state.current_scenario_id = None
    
    # Botón crear proyecto
    if st.sidebar.button("➕ Nuevo Proyecto", key="btn_new_project"):
        st.session_state.show_new_project = True
    
    # Mostrar formulario de nuevo proyecto
    if st.session_state.get('show_new_project', False):
        new_name = st.sidebar.text_input("Nombre del proyecto", key="new_project_name")
        
        # Opción para copiar escenario de otro proyecto
        copy_scenario = st.sidebar.checkbox("Copiar escenario de otro proyecto", key="copy_scenario_to_new_project")
        
        source_project_id = None
        source_scenario_id = None
        copied_scenario_name = None
        
        if copy_scenario and projects:
            # Filtrar proyectos que no sean el actual (si existe)
            available_projects = [p for p in projects if p['project_id'] != st.session_state.get('current_project_id')]
            
            if available_projects:
                source_project_name = st.sidebar.selectbox(
                    "Proyecto fuente",
                    options=[""] + [p['name'] for p in available_projects],
                    key="source_project_for_new"
                )
                
                if source_project_name:
                    source_project_id = next(p['project_id'] for p in available_projects if p['name'] == source_project_name)
                    source_project = load_project(source_project_id)
                    
                    if source_project and source_project.scenarios:
                        source_scenario_name = st.sidebar.selectbox(
                            "Escenario fuente",
                            options=[s.name for s in source_project.scenarios],
                            key="source_scenario_for_new"
                        )
                        
                        if source_scenario_name:
                            source_scenario_id = next(s.scenario_id for s in source_project.scenarios if s.name == source_scenario_name)
                            copied_scenario_name = st.sidebar.text_input(
                                "Nombre del escenario copiado",
                                value=source_scenario_name,
                                key="copied_scenario_name_new_project"
                            )
                    else:
                        st.sidebar.info("El proyecto fuente no tiene escenarios")
            else:
                st.sidebar.info("No hay otros proyectos disponibles")
        
        if st.sidebar.button("✅ Crear Proyecto", key="btn_create_project", type="primary"):
            if new_name and new_name.strip():
                try:
                    project = create_project(new_name.strip())
                    st.session_state.current_project_id = project.project_id
                    
                    # Si se seleccionó copiar escenario
                    if copy_scenario and source_project_id and source_scenario_id and copied_scenario_name and copied_scenario_name.strip():
                        copied_scenario = copy_scenario_to_project(
                            source_project_id,
                            source_scenario_id,
                            project.project_id,
                            copied_scenario_name.strip()
                        )
                        if copied_scenario:
                            st.session_state.current_scenario_id = copied_scenario.scenario_id
                            st.sidebar.success(f"Proyecto '{new_name}' creado con escenario copiado")
                        else:
                            st.sidebar.warning(f"Proyecto '{new_name}' creado, pero no se pudo copiar el escenario")
                    else:
                        st.sidebar.success(f"Proyecto '{new_name}' creado")
                    
                    st.session_state.show_new_project = False
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error: {e}")
            else:
                st.sidebar.warning("Ingresa un nombre para el proyecto")
        
        if st.sidebar.button("❌ Cancelar", key="btn_cancel_project"):
            st.session_state.show_new_project = False
            st.rerun()
    
    # Gestión de proyecto actual
    project = get_current_project()
    if project:
        st.sidebar.divider()
        st.sidebar.subheader("Gestión de Proyecto")
        
        # Renombrar proyecto
        new_name = st.sidebar.text_input("Renombrar proyecto", value=project.name, key="rename_project")
        if new_name and new_name != project.name:
            if st.sidebar.button("💾 Guardar nombre"):
                project.name = new_name
                save_project(project)
                st.sidebar.success("Nombre actualizado")
                st.rerun()
        
        # Borrar proyecto
        if st.sidebar.button("🗑️ Borrar Proyecto", type="secondary"):
            if st.sidebar.checkbox("Confirmar borrado", key="confirm_delete_project"):
                try:
                    delete_project(project.project_id)
                    st.session_state.current_project_id = None
                    st.session_state.current_scenario_id = None
                    st.sidebar.success("Proyecto eliminado")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error: {e}")
        
        # Selector de escenario
        st.sidebar.divider()
        st.sidebar.subheader("Escenario")
        
        scenario_options = {s.name: s.scenario_id for s in project.scenarios}
        
        if project.scenarios:
            selected_scenario_name = st.sidebar.selectbox(
                "Escenario",
                options=[""] + list(scenario_options.keys()),
                index=0 if not st.session_state.current_scenario_id else
                      list(scenario_options.keys()).index(
                          next(s.name for s in project.scenarios if s.scenario_id == st.session_state.current_scenario_id)
                      ) + 1 if st.session_state.current_scenario_id in scenario_options.values() else 0
            )
            
            if selected_scenario_name:
                st.session_state.current_scenario_id = scenario_options[selected_scenario_name]
            else:
                st.session_state.current_scenario_id = None
        else:
            st.sidebar.info("No hay escenarios. Crea uno nuevo.")
            st.session_state.current_scenario_id = None
        
        # Botones de gestión de escenario
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("➕ Nuevo", key="btn_new_scenario"):
                st.session_state.show_new_scenario = True
        
        # Mostrar formulario de nuevo escenario
        if st.session_state.get('show_new_scenario', False):
            new_scenario_name = st.sidebar.text_input("Nombre del escenario", key="new_scenario_name")
            
            # Opciones de creación de escenario
            scenario_creation_mode = st.sidebar.radio(
                "Tipo de escenario",
                options=["Escenario vacío", "Usar plantilla base", "Copiar de otro proyecto"],
                key="scenario_creation_mode"
            )
            
            source_project_id = None
            source_scenario_id = None
            
            # Si se selecciona copiar de otro proyecto
            if scenario_creation_mode == "Copiar de otro proyecto":
                all_projects = get_all_projects()
                # Filtrar proyectos que no sean el actual
                available_projects = [p for p in all_projects if p['project_id'] != project.project_id]
                
                if available_projects:
                    source_project_name = st.sidebar.selectbox(
                        "Proyecto fuente",
                        options=[""] + [p['name'] for p in available_projects],
                        key="source_project_for_scenario"
                    )
                    
                    if source_project_name:
                        source_project_id = next(p['project_id'] for p in available_projects if p['name'] == source_project_name)
                        source_project_obj = load_project(source_project_id)
                        
                        if source_project_obj and source_project_obj.scenarios:
                            source_scenario_name = st.sidebar.selectbox(
                                "Escenario fuente",
                                options=[s.name for s in source_project_obj.scenarios],
                                key="source_scenario_for_scenario"
                            )
                            
                            if source_scenario_name:
                                source_scenario_id = next(s.scenario_id for s in source_project_obj.scenarios if s.name == source_scenario_name)
                        else:
                            st.sidebar.info("El proyecto fuente no tiene escenarios")
                else:
                    st.sidebar.info("No hay otros proyectos disponibles")
            
            if st.sidebar.button("✅ Crear Escenario", key="btn_create_scenario", type="primary"):
                if new_scenario_name and new_scenario_name.strip():
                    try:
                        # Crear escenario según el modo seleccionado
                        if scenario_creation_mode == "Usar plantilla base":
                            new_scenario = get_seed_scenario()
                            new_scenario.scenario_id = str(uuid.uuid4())
                            new_scenario.name = new_scenario_name.strip()
                        elif scenario_creation_mode == "Copiar de otro proyecto":
                            if source_project_id and source_scenario_id:
                                new_scenario = copy_scenario_to_project(
                                    source_project_id,
                                    source_scenario_id,
                                    project.project_id,
                                    new_scenario_name.strip()
                                )
                                if not new_scenario:
                                    st.sidebar.error("No se pudo copiar el escenario")
                                    st.rerun()
                            else:
                                st.sidebar.warning("Selecciona proyecto y escenario fuente")
                                st.rerun()
                        else:  # Escenario vacío
                            # Crear escenario vacío con categoría por defecto
                            default_category = Category(
                                category_id=str(uuid.uuid4()),
                                label="General",
                                is_equipment=False
                            )
                            new_scenario = Scenario(
                                scenario_id=str(uuid.uuid4()),
                                name=new_scenario_name.strip(),
                                currency_input="COP",
                                prices_include_vat=False,
                                default_vat_rate=19.0,
                                categories=[default_category]
                            )
                            project.scenarios.append(new_scenario)
                        
                        # Guardar solo si no se copió (porque copy_scenario_to_project ya guarda)
                        if scenario_creation_mode != "Copiar de otro proyecto":
                            save_project(project)
                        
                        st.session_state.current_scenario_id = new_scenario.scenario_id
                        st.session_state.show_new_scenario = False
                        st.sidebar.success("Escenario creado")
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Error: {e}")
                else:
                    st.sidebar.warning("Ingresa un nombre para el escenario")
            
            if st.sidebar.button("❌ Cancelar", key="btn_cancel_scenario"):
                st.session_state.show_new_scenario = False
                st.rerun()
        
        scenario = get_current_scenario()
        if scenario:
            with col2:
                if st.button("📋 Duplicar", key="btn_dup_scenario"):
                    st.session_state.show_dup_scenario = True
            
            # Mostrar formulario de duplicar escenario
            if st.session_state.get('show_dup_scenario', False):
                dup_name = st.sidebar.text_input("Nombre del duplicado", value=f"{scenario.name} (copia)", key="dup_scenario_name")
                
                if st.sidebar.button("✅ Duplicar Escenario", key="btn_confirm_dup", type="primary"):
                    if dup_name and dup_name.strip():
                        try:
                            dup_scenario = duplicate_scenario(project.project_id, scenario.scenario_id, dup_name.strip())
                            if dup_scenario:
                                st.session_state.current_scenario_id = dup_scenario.scenario_id
                                st.session_state.show_dup_scenario = False
                                st.sidebar.success("Escenario duplicado")
                                st.rerun()
                            else:
                                st.sidebar.error("No se pudo duplicar el escenario")
                        except Exception as e:
                            st.sidebar.error(f"Error: {e}")
                    else:
                        st.sidebar.warning("Ingresa un nombre para el duplicado")
                
                if st.sidebar.button("❌ Cancelar", key="btn_cancel_dup"):
                    st.session_state.show_dup_scenario = False
                    st.rerun()
            
            if st.sidebar.button("✏️ Renombrar Escenario"):
                new_name = st.sidebar.text_input("Nuevo nombre", value=scenario.name, key="rename_scenario")
                if new_name and new_name != scenario.name:
                    scenario.name = new_name
                    project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                                       for s in project.scenarios]
                    save_project(project)
                    st.sidebar.success("Nombre actualizado")
                    st.rerun()
            
            # Checkbox de confirmación ANTES del botón
            st.sidebar.markdown("---")
            # Verificar si debemos limpiar el estado (después de un borrado exitoso)
            if st.session_state.get('_clear_confirm_delete', False):
                if 'confirm_delete_scenario' in st.session_state:
                    del st.session_state.confirm_delete_scenario
                st.session_state._clear_confirm_delete = False
            
            confirm_delete = st.sidebar.checkbox("Confirmar borrado", key="confirm_delete_scenario")
            
            if st.sidebar.button("🗑️ Borrar Escenario", type="secondary", disabled=not confirm_delete):
                if confirm_delete:
                    project.scenarios = [s for s in project.scenarios if s.scenario_id != scenario.scenario_id]
                    save_project(project)
                    # Marcar para limpiar el estado en el próximo render
                    st.session_state._clear_confirm_delete = True
                    if project.scenarios:
                        st.session_state.current_scenario_id = project.scenarios[0].scenario_id
                    else:
                        st.session_state.current_scenario_id = None
                    st.sidebar.success("Escenario eliminado")
                    st.rerun()
        
        # Parámetros globales
        scenario = get_current_scenario()
        if scenario:
            st.sidebar.divider()
            st.sidebar.subheader("Parámetros Globales")
            
            scenario.currency_input = st.sidebar.selectbox(
                "Moneda",
                options=["COP", "USD", "EUR"],
                index=["COP", "USD", "EUR"].index(scenario.currency_input) if scenario.currency_input in ["COP", "USD", "EUR"] else 0
            )
            
            scenario.prices_include_vat = st.sidebar.checkbox(
                "Precios incluyen IVA",
                value=scenario.prices_include_vat
            )
            
            scenario.default_vat_rate = st.sidebar.number_input(
                "IVA por defecto (%)",
                min_value=0.0,
                max_value=100.0,
                value=scenario.default_vat_rate,
                step=0.1
            )
            
            # Configuración AIU
            st.sidebar.divider()
            st.sidebar.subheader("Configuración AIU")
            
            scenario.aiu_enabled = st.sidebar.checkbox(
                "Habilitar AIU",
                value=scenario.aiu_enabled
            )
            
            if scenario.aiu_enabled:
                scenario.aiu_admin_pct = st.sidebar.number_input(
                    "Administración (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=scenario.aiu_admin_pct,
                    step=0.1
                )
                
                scenario.aiu_imprevistos_pct = st.sidebar.number_input(
                    "Imprevistos (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=scenario.aiu_imprevistos_pct,
                    step=0.1
                )
                
                scenario.aiu_utility_pct = st.sidebar.number_input(
                    "Utilidad (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=scenario.aiu_utility_pct,
                    step=0.1
                )
                
                aiu_rules = [
                    AIUBaseRule.DIRECT_COSTS_EXCL_VAT,
                    AIUBaseRule.DIRECT_COSTS_EXCL_CLIENT_PROVIDED,
                    AIUBaseRule.ONLY_SERVICES_LABOR
                ]
                
                current_rule_index = 0
                if scenario.aiu_base_rule in aiu_rules:
                    current_rule_index = aiu_rules.index(scenario.aiu_base_rule)
                
                selected_rule = st.sidebar.selectbox(
                    "Regla base AIU",
                    options=aiu_rules,
                    index=current_rule_index
                )
                scenario.aiu_base_rule = selected_rule
            
            # Administrar categorías
            st.sidebar.divider()
            with st.sidebar.expander("📁 Administrar Categorías"):
                for cat in scenario.categories:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        new_label = st.text_input(
                            "Nombre",
                            value=cat.label,
                            key=f"cat_label_{cat.category_id}"
                        )
                        if new_label != cat.label:
                            cat.label = new_label
                    with col2:
                        is_eq = st.checkbox(
                            "Equipo",
                            value=cat.is_equipment,
                            key=f"cat_eq_{cat.category_id}",
                            help="Marque si la categoría contiene equipos físicos. Se excluye del cálculo AIU cuando la regla es 'Solo servicios y mano de obra'."
                        )
                        cat.is_equipment = is_eq
                
                if st.button("➕ Nueva Categoría", key="new_category"):
                    new_cat = Category(
                        category_id=str(uuid.uuid4()),
                        label="Nueva Categoría",
                        is_equipment=False
                    )
                    scenario.categories.append(new_cat)
                    project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                                       for s in project.scenarios]
                    save_project(project)
                    st.rerun()
            
            # Botón guardar
            st.sidebar.divider()
            if st.sidebar.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                try:
                    project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                                       for s in project.scenarios]
                    save_project(project)
                    st.session_state['last_saved'] = datetime.now().strftime("%H:%M:%S")
                    st.sidebar.success("✅ Cambios guardados")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error guardando: {e}")


def update_calculated_columns_in_dataframe(df: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    """
    Actualiza las columnas calculadas (Base, IVA, Total) en un DataFrame
    usando los valores actuales de cantidad, precio, IVA, etc.
    
    Args:
        df: DataFrame con los ítems
        scenario: Escenario con los defaults
    
    Returns:
        DataFrame con las columnas calculadas actualizadas
    """
    df = df.copy()
    
    # Recalcular totales para cada fila
    for idx, row in df.iterrows():
        try:
            # Obtener valores de la fila
            qty = float(row['Cantidad']) if pd.notna(row['Cantidad']) else 0.0
            precio_str = str(row['Precio Unitario']) if pd.notna(row['Precio Unitario']) else "0"
            unit_price = parse_number(precio_str)
            price_includes_vat = bool(row['Precio incluye IVA']) if pd.notna(row['Precio incluye IVA']) else scenario.prices_include_vat
            vat_rate = float(row['IVA %']) if pd.notna(row['IVA %']) and pd.notna(row['IVA %']) else scenario.default_vat_rate
            
            # Calcular totales
            if price_includes_vat:
                base_unit = unit_price / (1 + vat_rate / 100.0)
                vat_unit = unit_price - base_unit
                total_unit = unit_price
            else:
                base_unit = unit_price
                vat_unit = base_unit * (vat_rate / 100.0)
                total_unit = base_unit + vat_unit
            
            # Totales de línea
            base_line = base_unit * qty
            vat_line = vat_unit * qty
            total_line = total_unit * qty
            
            # Actualizar columnas calculadas
            df.at[idx, 'Base (sin IVA)'] = format_cop(base_line)
            df.at[idx, 'IVA'] = format_cop(vat_line)
            df.at[idx, 'Total (con IVA)'] = format_cop(total_line)
        except Exception as e:
            # Si hay error, mantener valores por defecto
            df.at[idx, 'Base (sin IVA)'] = format_cop(0.0)
            df.at[idx, 'IVA'] = format_cop(0.0)
            df.at[idx, 'Total (con IVA)'] = format_cop(0.0)
    
    return df


def calculate_normalized_metrics(capex_value: float, pnom_total_kwp: float, potencia_total_kwac: float) -> Dict[str, Optional[float]]:
    """
    Calcula métricas normalizadas de CAPEX.
    
    Args:
        capex_value: Valor de CAPEX en COP
        pnom_total_kwp: Pnom total en kWp
        potencia_total_kwac: Potencia total en kWAC
    
    Returns:
        Dict con 'cop_per_kwp' y 'cop_per_mw', o None si no se puede calcular
    """
    cop_per_kwp = None
    cop_per_mw = None
    
    if pnom_total_kwp > 0:
        cop_per_kwp = capex_value / pnom_total_kwp
    
    if potencia_total_kwac > 0:
        potencia_mw = potencia_total_kwac / 1000.0
        cop_per_mw = capex_value / potencia_mw
    
    return {
        'cop_per_kwp': cop_per_kwp,
        'cop_per_mw': cop_per_mw
    }


def items_to_dataframe(scenario: Scenario, summary: Dict, sort_by: str = "order") -> pd.DataFrame:
    """Convierte los ítems del escenario a DataFrame para edición."""
    items_data = []
    items_totals = summary.get('items_totals', {})
    
    # Ordenar ítems según opción
    if sort_by == "order":
        sorted_items = sorted(scenario.items, key=lambda x: x.order)
    elif sort_by == "category":
        # Crear diccionario de nombres de categoría para acceso rápido
        cat_names = {cat.category_id: cat.label for cat in scenario.categories}
        sorted_items = sorted(scenario.items, key=lambda x: (
            cat_names.get(x.category_id, "Sin categoría"),
            x.name
        ))
    elif sort_by == "name":
        sorted_items = sorted(scenario.items, key=lambda x: x.name)
    elif sort_by == "code":
        sorted_items = sorted(scenario.items, key=lambda x: (x.item_code or "", x.name))
    else:
        sorted_items = sorted(scenario.items, key=lambda x: x.order)
    
    for item in sorted_items:
        totals = items_totals.get(item.item_id, {
            'base_line': 0.0, 'vat_line': 0.0, 'total_line': 0.0
        })
        
        # Obtener nombre de categoría
        category_name = "Sin categoría"
        for cat in scenario.categories:
            if cat.category_id == item.category_id:
                category_name = cat.label
                break
        
        # Obtener valores de delivery_point e incoterm con defaults
        delivery_point_val = getattr(item, 'delivery_point', DeliveryPoint.OBRA)
        incoterm_val = getattr(item, 'incoterm', Incoterm.NA)
        includes_transport = getattr(item, 'includes_transport_to_site', False)
        includes_install = getattr(item, 'includes_installation', False)
        includes_comm = getattr(item, 'includes_commissioning', False)
        description_val = getattr(item, 'description', "")
        
        items_data.append({
            'Seleccionar': False,  # Columna para seleccionar ítems a borrar
            'item_id': item.item_id,
            'Categoría': category_name,
            'category_id': item.category_id,
            'Código': item.item_code or "",
            'Nombre': item.name,
            'Descripción': description_val,
            'Unidad': item.unit,
            'Cantidad': item.qty,
            'Precio Unitario': format_cop(item.unit_price),  # Solo versión formateada
            'Precio incluye IVA': item.price_includes_vat,
            'IVA %': item.vat_rate,
            'Aplica AIU': item.aiu_applicable,
            'Cliente compra': item.client_provided,
            'Pass through': item.pass_through,
            'Punto de entrega': delivery_point_val,
            'Incoterm': incoterm_val,
            'Transporte a obra': includes_transport,
            'Incluye instalación': includes_install,
            'Incluye commissioning': includes_comm,
            'Base (sin IVA)': format_cop(totals['base_line']),  # Solo versión formateada
            'IVA': format_cop(totals['vat_line']),  # Solo versión formateada
            'Total (con IVA)': format_cop(totals['total_line']),  # Solo versión formateada
            'order': item.order
        })
    
    return pd.DataFrame(items_data)


def render_category_totals(scenario: Scenario, summary: Dict):
    """Muestra tabla de subtotales por categoría."""
    cat_totals = aggregate_by_category(scenario, summary)
    direct_cost_base = summary.get('direct_cost_base', 0.0)
    
    if not cat_totals:
        return
    
    # Crear DataFrame para mostrar
    totals_data = []
    for cat_id, totals in cat_totals.items():
        pct = (totals['base'] / direct_cost_base * 100) if direct_cost_base > 0 else 0.0
        totals_data.append({
            'Categoría': totals['name'],
            'Base (sin IVA)': format_cop(totals['base']),
            'IVA': format_cop(totals['vat']),
            'Total (con IVA)': format_cop(totals['total']),
            '% del costo directo': format_percentage(pct, decimals=1)
        })
    
    totals_df = pd.DataFrame(totals_data)
    st.subheader("📊 Subtotales por Categoría")
    # Aplicar alineación a la derecha a columnas numéricas
    styled_df = totals_df.style.applymap(
        lambda x: 'text-align: right', 
        subset=['Base (sin IVA)', 'IVA', 'Total (con IVA)', '% del costo directo']
    )
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def generate_consolidated_table_data(scenario: Scenario, summary: Dict) -> List[Dict[str, Any]]:
    """
    Genera datos de la tabla consolidada sin formatear (valores numéricos).
    
    Args:
        scenario: El escenario
        summary: El resumen calculado
    
    Returns:
        Lista de diccionarios con estructura: [
            {'Concepto': str, 'Base (sin IVA)': float, 'IVA': float, 'Total (con IVA)': float},
            ...
        ]
    """
    # Obtener subtotales por categoría
    cat_totals = aggregate_by_category(scenario, summary)
    
    # Calcular total CAPEX (epc_total + client_capex_total)
    total_capex = summary.get('epc_total', 0) + summary.get('client_capex_total', 0)
    
    # Preparar datos de la tabla
    summary_data = []
    
    # 1. Subtotales por categoría (agrupar por nombre)
    cat_by_name = group_categories_by_name(cat_totals)
    for cat_name in sorted(cat_by_name.keys()):
        totals = cat_by_name[cat_name]
        summary_data.append({
            'Concepto': cat_name,
            'Base (sin IVA)': totals['base'],
            'IVA': totals['vat'],
            'Total (con IVA)': totals['total']
        })
    
    # 2. AIU (si está habilitado)
    if scenario.aiu_enabled and summary.get('aiu_total', 0) > 0:
        aiu_base = summary.get('aiu_base', 0)
        aiu_admin = summary.get('aiu_admin', 0)
        aiu_imprevistos = summary.get('aiu_imprevistos', 0)
        aiu_utility = summary.get('aiu_utility', 0)
        aiu_total = summary.get('aiu_total', 0)
        
        # Calcular porcentajes de cada componente sobre base AIU
        admin_pct = (aiu_admin / aiu_base * 100) if aiu_base > 0 else 0.0
        imprev_pct = (aiu_imprevistos / aiu_base * 100) if aiu_base > 0 else 0.0
        util_pct = (aiu_utility / aiu_base * 100) if aiu_base > 0 else 0.0
        
        summary_data.append({
            'Concepto': f"AIU (Admin {format_percentage(admin_pct, decimals=1)}, Imprev {format_percentage(imprev_pct, decimals=1)}, Util {format_percentage(util_pct, decimals=1)})",
            'Base (sin IVA)': 0.0,  # AIU no tiene base
            'IVA': 0.0,  # AIU no tiene IVA
            'Total (con IVA)': aiu_total
        })
    
    # 3. Total CAPEX
    total_base = summary.get('epc_base', 0) + summary.get('client_capex_base', 0)
    total_vat = summary.get('epc_vat', 0) + summary.get('client_capex_vat', 0)
    total_capex_final = summary.get('epc_total', 0) + summary.get('client_capex_total', 0)
    
    summary_data.append({
        'Concepto': 'Total CAPEX',
        'Base (sin IVA)': total_base,
        'IVA': total_vat,
        'Total (con IVA)': total_capex_final
    })
    
    return summary_data


def render_consolidated_summary_table(scenario: Scenario, summary: Dict):
    """Muestra tabla resumen consolidada: categorías + indirectos + AIU = Total CAPEX."""
    st.subheader("📋 Resumen Consolidado CAPEX")
    
    # Obtener subtotales por categoría
    cat_totals = aggregate_by_category(scenario, summary)
    
    # Calcular total CAPEX (epc_total + client_capex_total)
    total_capex = summary.get('epc_total', 0) + summary.get('client_capex_total', 0)
    
    # Preparar datos de la tabla
    summary_data = []
    
    # 1. Subtotales por categoría
    for cat_id, totals in cat_totals.items():
        pct = (totals['total'] / total_capex * 100) if total_capex > 0 else 0.0
        # Calcular métricas normalizadas
        metrics = calculate_normalized_metrics(totals['total'], scenario.pnom_total_kwp, scenario.potencia_total_kwac)
        cop_kwp = format_cop(metrics['cop_per_kwp']) if metrics['cop_per_kwp'] is not None else "N/A"
        cop_mw = format_cop(metrics['cop_per_mw']) if metrics['cop_per_mw'] is not None else "N/A"
        
        summary_data.append({
            'Concepto': totals['name'],
            'Base (sin IVA)': format_cop(totals['base']),
            'IVA': format_cop(totals['vat']),
            'Total (con IVA)': format_cop(totals['total']),
            '% del Total CAPEX': format_percentage(pct, decimals=1),
            'COP/kWp': cop_kwp,
            'COP/MW': cop_mw
        })
    
    # 2. AIU (detallado)
    if scenario.aiu_enabled and summary.get('aiu_total', 0) > 0:
        aiu_base = summary.get('aiu_base', 0)
        aiu_admin = summary.get('aiu_admin', 0)
        aiu_imprevistos = summary.get('aiu_imprevistos', 0)
        aiu_utility = summary.get('aiu_utility', 0)
        aiu_total = summary.get('aiu_total', 0)
        
        # Calcular porcentajes de cada componente sobre base AIU
        admin_pct = (aiu_admin / aiu_base * 100) if aiu_base > 0 else 0.0
        imprev_pct = (aiu_imprevistos / aiu_base * 100) if aiu_base > 0 else 0.0
        util_pct = (aiu_utility / aiu_base * 100) if aiu_base > 0 else 0.0
        
        # Mostrar AIU como fila consolidada con detalles en columna adicional
        pct_aiu_total = (aiu_total / total_capex * 100) if total_capex > 0 else 0.0
        # Calcular métricas normalizadas para AIU
        metrics_aiu = calculate_normalized_metrics(aiu_total, scenario.pnom_total_kwp, scenario.potencia_total_kwac)
        cop_kwp_aiu = format_cop(metrics_aiu['cop_per_kwp']) if metrics_aiu['cop_per_kwp'] is not None else "N/A"
        cop_mw_aiu = format_cop(metrics_aiu['cop_per_mw']) if metrics_aiu['cop_per_mw'] is not None else "N/A"
        
        summary_data.append({
            'Concepto': f"AIU (Admin {format_percentage(admin_pct, decimals=1)}, Imprev {format_percentage(imprev_pct, decimals=1)}, Util {format_percentage(util_pct, decimals=1)})",
            'Base (sin IVA)': format_cop(0),  # AIU no tiene base, se muestra como 0
            'IVA': format_cop(0),  # AIU no tiene IVA
            'Total (con IVA)': format_cop(aiu_total),
            '% del Total CAPEX': format_percentage(pct_aiu_total, decimals=1),
            'COP/kWp': cop_kwp_aiu,
            'COP/MW': cop_mw_aiu
        })
    
    # 3. Total CAPEX (suma de todo)
    # Nota: direct_cost_base ya incluye todos los ítems (client_provided y no client_provided)
    # epc_base solo incluye ítems NO client_provided, así que necesitamos sumar client_capex_base
    # Excluir aiu_base del total_base ya que AIU no tiene base (se muestra como 0)
    total_base = summary.get('epc_base', 0) + summary.get('client_capex_base', 0)
    total_vat = summary.get('epc_vat', 0) + summary.get('client_capex_vat', 0)
    total_capex_final = summary.get('epc_total', 0) + summary.get('client_capex_total', 0)
    
    # Calcular métricas normalizadas para Total CAPEX
    metrics_total = calculate_normalized_metrics(total_capex_final, scenario.pnom_total_kwp, scenario.potencia_total_kwac)
    cop_kwp_total = format_cop(metrics_total['cop_per_kwp']) if metrics_total['cop_per_kwp'] is not None else "N/A"
    cop_mw_total = format_cop(metrics_total['cop_per_mw']) if metrics_total['cop_per_mw'] is not None else "N/A"
    
    summary_data.append({
        'Concepto': '**Total CAPEX**',
        'Base (sin IVA)': format_cop(total_base),
        'IVA': format_cop(total_vat),
        'Total (con IVA)': format_cop(total_capex_final),
        '% del Total CAPEX': '100,0%',
        'COP/kWp': cop_kwp_total,
        'COP/MW': cop_mw_total
    })
    
    # Crear DataFrame y mostrar
    summary_df = pd.DataFrame(summary_data)
    # Aplicar alineación a la derecha a columnas numéricas
    styled_df = summary_df.style.applymap(
        lambda x: 'text-align: right', 
        subset=['Base (sin IVA)', 'IVA', 'Total (con IVA)', '% del Total CAPEX', 'COP/kWp', 'COP/MW']
    )
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_incoterm_help():
    """Muestra ayuda contextual sobre Incoterms."""
    with st.expander("❓ ¿Qué significan los Incoterms?"):
        st.markdown("""
        ### Incoterms (Términos de Comercio Internacional)
        
        | Incoterm | Transporte | Seguro | Importación | Útil cuando... |
        |----------|------------|--------|-------------|----------------|
        | **EXW** | Comprador | Comprador | Comprador | Vendedor entrega en planta; comprador asume todo desde recogida |
        | **FOB** | Comprador | Comprador | Comprador | Vendedor entrega a bordo en puerto de salida; comprador asume flete/seguro/importación |
        | **CIF** | Vendedor | Vendedor | Comprador | Vendedor paga flete y seguro hasta puerto destino; comprador asume importación y transporte a obra |
        | **DDP** | Vendedor | Vendedor | Vendedor | Vendedor entrega en destino con impuestos/aduanas pagados |
        | **NA** | - | - | - | No aplica o no definido |
        
        **Definiciones detalladas:**
        - **EXW (Ex Works)**: El vendedor pone la mercancía a disposición del comprador en sus instalaciones. El comprador asume todos los costos y riesgos desde el punto de entrega.
        - **FOB (Free On Board)**: El vendedor entrega la mercancía a bordo del buque en el puerto de embarque. El comprador asume todos los costos y riesgos desde ese momento.
        - **CIF (Cost, Insurance and Freight)**: El vendedor paga el costo del transporte y seguro hasta el puerto de destino, pero el riesgo se transfiere al comprador cuando la mercancía está a bordo en el puerto de embarque.
        - **DDP (Delivered Duty Paid)**: El vendedor entrega la mercancía en el destino acordado, habiendo pagado todos los costos, incluyendo impuestos y aranceles. Máxima responsabilidad del vendedor.
        """)


def render_direct_cost_summary(scenario: Scenario, summary: Dict):
    """Muestra el resumen de Costo Directo."""
    st.markdown("### Resumen de Costo Directo")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Base (sin IVA)", format_cop(summary['direct_cost_base']))
    
    with col2:
        st.metric("IVA", format_cop(summary['direct_cost_vat']))
    
    with col3:
        st.metric("Total (con IVA)", format_cop(summary['direct_cost_total']))


def render_subtotal_costs(scenario: Scenario, summary: Dict):
    """Muestra el Subtotal Costos (Costo Directo)."""
    subtotal_base = summary['direct_cost_base']
    subtotal_vat = summary['direct_cost_vat']
    subtotal_total = summary['direct_cost_total']
    
    st.markdown("### Subtotal Costos")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Base (sin IVA)", format_cop(subtotal_base))
    
    with col2:
        st.metric("IVA", format_cop(subtotal_vat))
    
    with col3:
        st.metric("Total (con IVA)", format_cop(subtotal_total))


def render_percentage_modules(scenario: Scenario, summary: Dict):
    """Muestra los módulos porcentuales (Transporte, Pólizas, Ingeniería)."""
    if summary.get('transport_total', 0.0) > 0 or summary.get('policies_total', 0.0) > 0 or summary.get('engineering_total', 0.0) > 0:
        st.markdown("### Otros Costos Indirectos")
        
        modules_data = []
        if summary.get('transport_total', 0.0) > 0:
            modules_data.append({
                'Concepto': 'Transporte',
                'Base (sin IVA)': format_cop(summary['transport_base']),
                'IVA': format_cop(summary['transport_vat']),
                'Total (con IVA)': format_cop(summary['transport_total']),
                '%': format_percentage(scenario.transport_pct)
            })
        if summary.get('policies_total', 0.0) > 0:
            modules_data.append({
                'Concepto': 'Pólizas',
                'Base (sin IVA)': format_cop(summary['policies_base']),
                'IVA': format_cop(summary['policies_vat']),
                'Total (con IVA)': format_cop(summary['policies_total']),
                '%': format_percentage(scenario.policies_pct)
            })
        if summary.get('engineering_total', 0.0) > 0:
            modules_data.append({
                'Concepto': 'Ingeniería',
                'Base (sin IVA)': format_cop(summary['engineering_base']),
                'IVA': format_cop(summary['engineering_vat']),
                'Total (con IVA)': format_cop(summary['engineering_total']),
                '%': format_percentage(scenario.engineering_pct)
            })
        
        if modules_data:
            modules_df = pd.DataFrame(modules_data)
            # Aplicar alineación a la derecha a columnas numéricas
            styled_df = modules_df.style.applymap(
                lambda x: 'text-align: right', 
                subset=['Base (sin IVA)', 'IVA', 'Total (con IVA)', '%']
            )
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Base Módulos", format_cop(summary.get('transport_base', 0) + summary.get('policies_base', 0) + summary.get('engineering_base', 0)))
        with col2:
            st.metric("Total IVA Módulos", format_cop(summary.get('transport_vat', 0) + summary.get('policies_vat', 0) + summary.get('engineering_vat', 0)))
        with col3:
            st.metric("Total Módulos", format_cop(summary.get('transport_total', 0) + summary.get('policies_total', 0) + summary.get('engineering_total', 0)))


def render_aiu_section(scenario: Scenario, summary: Dict):
    """Muestra la sección de AIU."""
    if scenario.aiu_enabled and summary['aiu_base'] > 0:
        st.markdown("### AIU")
        
        aiu_base = summary['aiu_base']
        aiu_admin = summary['aiu_admin']
        aiu_imprevistos = summary['aiu_imprevistos']
        aiu_utility = summary['aiu_utility']
        aiu_total = summary['aiu_total']
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Base AIU", format_cop(aiu_base))
        
        with col2:
            admin_pct = (aiu_admin / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("Administración", format_cop(aiu_admin), delta=format_percentage(admin_pct))
        
        with col3:
            imprev_pct = (aiu_imprevistos / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("Imprevistos", format_cop(aiu_imprevistos), delta=format_percentage(imprev_pct))
        
        with col4:
            util_pct = (aiu_utility / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("Utilidad", format_cop(aiu_utility), delta=format_percentage(util_pct))
        
        with col5:
            total_pct = (aiu_total / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("**Total AIU**", format_cop(aiu_total), delta=format_percentage(total_pct))


def render_capex_breakdown(scenario: Scenario, summary: Dict):
    """Muestra el desglose CAPEX completo del escenario."""
    st.subheader("📋 Desglose CAPEX")
    
    # Costo directo
    st.markdown("### Costo Directo")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Base (sin IVA)", format_cop(summary['direct_cost_base']))
    
    with col2:
        st.metric("IVA", format_cop(summary['direct_cost_vat']))
    
    with col3:
        st.metric("Total (con IVA)", format_cop(summary['direct_cost_total']))
    
    # Otros Costos Indirectos
    if summary.get('transport_total', 0.0) > 0 or summary.get('policies_total', 0.0) > 0 or summary.get('engineering_total', 0.0) > 0:
        st.divider()
        st.markdown("### Otros Costos Indirectos")
        
        modules_data = []
        if summary.get('transport_total', 0.0) > 0:
            modules_data.append({
                'Concepto': 'Transporte',
                'Base (sin IVA)': format_cop(summary['transport_base']),
                'IVA': format_cop(summary['transport_vat']),
                'Total (con IVA)': format_cop(summary['transport_total']),
                '%': format_percentage(scenario.transport_pct)
            })
        if summary.get('policies_total', 0.0) > 0:
            modules_data.append({
                'Concepto': 'Pólizas',
                'Base (sin IVA)': format_cop(summary['policies_base']),
                'IVA': format_cop(summary['policies_vat']),
                'Total (con IVA)': format_cop(summary['policies_total']),
                '%': format_percentage(scenario.policies_pct)
            })
        if summary.get('engineering_total', 0.0) > 0:
            modules_data.append({
                'Concepto': 'Ingeniería',
                'Base (sin IVA)': format_cop(summary['engineering_base']),
                'IVA': format_cop(summary['engineering_vat']),
                'Total (con IVA)': format_cop(summary['engineering_total']),
                '%': format_percentage(scenario.engineering_pct)
            })
        
        if modules_data:
            modules_df = pd.DataFrame(modules_data)
            # Aplicar alineación a la derecha a columnas numéricas
            styled_df = modules_df.style.applymap(
                lambda x: 'text-align: right', 
                subset=['Base (sin IVA)', 'IVA', 'Total (con IVA)', '%']
            )
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Base Módulos", format_cop(summary.get('transport_base', 0) + summary.get('policies_base', 0) + summary.get('engineering_base', 0)))
        with col2:
            st.metric("Total IVA Módulos", format_cop(summary.get('transport_vat', 0) + summary.get('policies_vat', 0) + summary.get('engineering_vat', 0)))
        with col3:
            st.metric("Total Módulos", format_cop(summary.get('transport_total', 0) + summary.get('policies_total', 0) + summary.get('engineering_total', 0)))
    
    # Total directo (costo directo + módulos)
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("**Total Directo Base**", format_cop(summary['total_base']))
    with col2:
        st.metric("**Total Directo IVA**", format_cop(summary['total_vat']))
    with col3:
        st.metric("**Total Directo (con IVA)**", format_cop(summary['total_direct']))
    
    # AIU
    if scenario.aiu_enabled and summary['aiu_base'] > 0:
        st.divider()
        st.markdown("### AIU")
        
        aiu_base = summary['aiu_base']
        aiu_admin = summary['aiu_admin']
        aiu_imprevistos = summary['aiu_imprevistos']
        aiu_utility = summary['aiu_utility']
        aiu_total = summary['aiu_total']
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Base AIU", format_cop(aiu_base))
        
        with col2:
            admin_pct = (aiu_admin / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("Administración", format_cop(aiu_admin), delta=format_percentage(admin_pct))
        
        with col3:
            imprev_pct = (aiu_imprevistos / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("Imprevistos", format_cop(aiu_imprevistos), delta=format_percentage(imprev_pct))
        
        with col4:
            util_pct = (aiu_utility / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("Utilidad", format_cop(aiu_utility), delta=format_percentage(util_pct))
        
        with col5:
            total_pct = (aiu_total / aiu_base * 100) if aiu_base > 0 else 0.0
            st.metric("**Total AIU**", format_cop(aiu_total), delta=format_percentage(total_pct))
    
    # Total contrato EPC (excluyendo client_provided)
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("**Total Contrato EPC Base**", format_cop(summary['epc_base']))
    with col2:
        st.metric("**Total Contrato EPC IVA**", format_cop(summary['epc_vat']))
    with col3:
        st.metric("**Total Contrato EPC**", format_cop(summary['epc_total']))
    
    # Total general
    st.divider()
    st.metric("**🎯 Total General**", format_cop(summary['grand_total']))


def render_edit_scenario():
    """Renderiza la pestaña de edición de escenario."""
    scenario = get_current_scenario()
    if not scenario:
        st.info("Selecciona un escenario para editar.")
        return
    
    project = get_current_project()
    if project:
        st.header(f"📝 Editar: {project.name} - {scenario.name}")
    else:
        st.header(f"📝 Editar: {scenario.name}")
    
    # Indicador de estado de guardado
    if 'last_saved' in st.session_state:
        st.info(f"💾 Último guardado: {st.session_state['last_saved']}")
    
    # Calcular resumen inicial (se actualizará después de procesar cambios si hay cambios)
    summary = calculate_scenario_summary(scenario)
    
    # 0. VARIABLES CLAVE DEL PROYECTO (ANTES DEL DESGLOSE DE CAPEX)
    st.subheader("📊 Variables Clave del Proyecto")
    
    col1, col2 = st.columns(2)
    
    with col1:
        potencia_total_kwac = st.number_input(
            "Potencia total en kWAC",
            min_value=0.0,
            value=float(scenario.potencia_total_kwac),
            step=0.1,
            format="%.2f",
            key="potencia_total_kwac_input"
        )
        energia_p50_mwh_anio = st.number_input(
            "Energía producida P50 en MWH/año",
            min_value=0.0,
            value=float(scenario.energia_p50_mwh_anio),
            step=0.1,
            format="%.2f",
            key="energia_p50_mwh_anio_input"
        )
    
    with col2:
        pnom_total_kwp = st.number_input(
            "Pnom total en kWp",
            min_value=0.0,
            value=float(scenario.pnom_total_kwp),
            step=0.1,
            format="%.2f",
            key="pnom_total_kwp_input"
        )
        produccion_especifica_kwh_kwp_anio = st.number_input(
            "Producción específica en kWh/kWp/año",
            min_value=0.0,
            value=float(scenario.produccion_especifica_kwh_kwp_anio),
            step=0.1,
            format="%.2f",
            key="produccion_especifica_kwh_kwp_anio_input"
        )
    
    # Actualizar valores en el escenario si cambiaron
    if (potencia_total_kwac != scenario.potencia_total_kwac or
        energia_p50_mwh_anio != scenario.energia_p50_mwh_anio or
        pnom_total_kwp != scenario.pnom_total_kwp or
        produccion_especifica_kwh_kwp_anio != scenario.produccion_especifica_kwh_kwp_anio):
        scenario.potencia_total_kwac = potencia_total_kwac
        scenario.energia_p50_mwh_anio = energia_p50_mwh_anio
        scenario.pnom_total_kwp = pnom_total_kwp
        scenario.produccion_especifica_kwh_kwp_anio = produccion_especifica_kwh_kwp_anio
    
    st.divider()
    
    # 1. DESGLOSE DE CAPEX - Tabla de ítems (PRIMERO)
    st.subheader("DESGLOSE DE CAPEX")
    
    # Selector de ordenamiento y botón rápido
    # Inicializar estado si no existe
    if 'sort_items_option' not in st.session_state:
        st.session_state.sort_items_option = "Orden original"
    
    sort_options = ["Orden original", "Por categoría", "Por nombre", "Por código"]
    
    # Verificar si el botón fue presionado en el rerun anterior
    # Usar una key separada para el botón para evitar conflictos
    if 'force_sort_category' in st.session_state and st.session_state.force_sort_category:
        st.session_state.sort_items_option = "Por categoría"
        st.session_state.force_sort_category = False
    
    # Crear columnas
    col_sort1, col_sort2, col_filter = st.columns([2, 1, 3])
    
    # Procesar botón PRIMERO (antes del selectbox)
    with col_sort2:
        if st.button("📊 Ordenar por Categoría", use_container_width=True, key="btn_sort_category"):
            # Usar un flag separado para evitar conflicto con el selectbox
            st.session_state.force_sort_category = True
            st.rerun()
    
    # Luego crear el selectbox que leerá el valor de session_state
    with col_sort1:
        # Determinar el índice basado en el estado actual
        current_value = st.session_state.get('sort_items_option', "Orden original")
        current_index = sort_options.index(current_value) if current_value in sort_options else 0
        
        sort_option = st.selectbox(
            "Ordenar por",
            options=sort_options,
            key="sort_items_option",
            index=current_index
        )
    
    with col_filter:
        category_filter = st.selectbox(
            "Filtrar por categoría",
            options=["Todas"] + [cat.label for cat in scenario.categories],
            key="category_filter"
        )
    
    # Convertir a DataFrame con ordenamiento
    sort_by_map = {
        "Orden original": "order",
        "Por categoría": "category",
        "Por nombre": "name",
        "Por código": "code"
    }
    sort_by_value = sort_by_map.get(sort_option, "order")
    df = items_to_dataframe(scenario, summary, sort_by=sort_by_value)
    
    # Aplicar filtro si está seleccionado
    if category_filter != "Todas":
        df = df[df['Categoría'] == category_filter]
    
    # Columnas para mostrar (ocultar category_id, order, pero mantener item_id para sincronización)
    display_columns = [
        'Seleccionar', 'Categoría', 'Código', 'Nombre', 'Descripción', 'Unidad', 'Cantidad',
        'Precio Unitario', 'Precio incluye IVA', 'IVA %',
        'Aplica AIU', 'Cliente compra', 'Pass through',
        'Punto de entrega', 'Incoterm', 'Transporte a obra', 'Incluye instalación', 'Incluye commissioning',
        'Base (sin IVA)', 'IVA', 'Total (con IVA)'
    ]
    
    # Crear DataFrame para edición - incluir item_id aunque no se muestre para facilitar sincronización
    editable_columns = display_columns.copy()
    if 'item_id' in df.columns:
        editable_columns.append('item_id')
    
    # Filtrar editable_columns para incluir solo las columnas que existen en df
    existing_columns = [col for col in editable_columns if col in df.columns]
    editable_df = df[existing_columns].copy() if existing_columns else pd.DataFrame()
    
    # Agregar columnas faltantes con valores por defecto
    for col in editable_columns:
        if col not in editable_df.columns:
            if col == 'Seleccionar':
                editable_df[col] = False
            elif col == 'item_id':
                editable_df[col] = None
            elif col in ['Base (sin IVA)', 'IVA', 'Total (con IVA)']:
                editable_df[col] = format_cop(0.0)
            elif col in ['Cantidad', 'IVA %']:
                editable_df[col] = 0.0
            elif col in ['Precio incluye IVA', 'Aplica AIU', 'Cliente compra', 'Pass through', 
                         'Transporte a obra', 'Incluye instalación', 'Incluye commissioning']:
                editable_df[col] = False
            else:
                editable_df[col] = ""
    
    # Si hay filas nuevas sin item_id, generar uno para cada una
    # Esto se hace antes de pasar al editor para que las filas nuevas tengan un identificador
    if len(editable_df) > len(scenario.items):
        # Hay filas nuevas (agregadas directamente en el editor)
        for idx in range(len(scenario.items), len(editable_df)):
            row_idx = editable_df.index[idx]
            current_item_id = editable_df.at[row_idx, 'item_id'] if 'item_id' in editable_df.columns else None
            if pd.isna(current_item_id) or (isinstance(current_item_id, str) and current_item_id.strip() == ''):
                editable_df.at[row_idx, 'item_id'] = str(uuid.uuid4())
    
    # Configurar columnas para data_editor
    column_config = {
        'Seleccionar': st.column_config.CheckboxColumn('Seleccionar', help="Marcar para borrar este ítem"),
        'Categoría': st.column_config.SelectboxColumn(
            'Categoría',
            options=[""] + [cat.label for cat in scenario.categories],
            required=True
        ),
        'Código': st.column_config.TextColumn('Código'),
        'Nombre': st.column_config.TextColumn('Nombre', required=True),
        'Descripción': st.column_config.TextColumn('Descripción / Especificación'),
        'Unidad': st.column_config.SelectboxColumn(
            'Unidad',
            options=['UND', 'kWp', 'kW', 'kVA', 'm', 'm2', 'lote', '%', 'mes', 'hora'],
            required=True
        ),
        'Cantidad': st.column_config.NumberColumn('Cantidad', min_value=0.0, step=0.01, format="%.2f"),
        'Precio Unitario': st.column_config.TextColumn(
            'Precio Unitario',
            help="Ingrese el precio con separadores de miles (ej: 3.800.000) o sin ellos (ej: 3800000)"
        ),
        'Precio incluye IVA': st.column_config.CheckboxColumn('Precio incluye IVA'),
        'IVA %': st.column_config.NumberColumn('IVA %', min_value=0.0, max_value=100.0, step=0.1, format="%.1f"),
        'Aplica AIU': st.column_config.CheckboxColumn('Aplica AIU'),
        'Cliente compra': st.column_config.CheckboxColumn('Cliente compra'),
        'Pass through': st.column_config.CheckboxColumn('Pass through'),
        'Punto de entrega': st.column_config.SelectboxColumn(
            'Punto de entrega',
            options=[DeliveryPoint.PUERTO, DeliveryPoint.BODEGA, DeliveryPoint.OBRA, DeliveryPoint.INSTALADO]
        ),
        'Incoterm': st.column_config.SelectboxColumn(
            'Incoterm',
            options=[Incoterm.EXW, Incoterm.FOB, Incoterm.CIF, Incoterm.DDP, Incoterm.NA]
        ),
        'Transporte a obra': st.column_config.CheckboxColumn('Transporte a obra'),
        'Incluye instalación': st.column_config.CheckboxColumn('Incluye instalación'),
        'Incluye commissioning': st.column_config.CheckboxColumn('Incluye commissioning'),
        'Base (sin IVA)': st.column_config.TextColumn('Base (sin IVA)', disabled=True),
        'IVA': st.column_config.TextColumn('IVA', disabled=True),
        'Total (con IVA)': st.column_config.TextColumn('Total (con IVA)', disabled=True),
    }
    
    # Botones de acción
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Agregar Ítem"):
            new_item = Item(
                item_id=str(uuid.uuid4()),
                category_id=scenario.categories[0].category_id if scenario.categories else "",
                name="Nuevo ítem",
                description="",
                delivery_point=DeliveryPoint.OBRA,
                incoterm=Incoterm.NA,
                includes_transport_to_site=False,
                includes_installation=False,
                includes_commissioning=False,
                order=len(scenario.items)
            )
            scenario.items.append(new_item)
            project = get_current_project()
            project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                               for s in project.scenarios]
            save_project(project)
            st.session_state['last_saved'] = datetime.now().strftime("%H:%M:%S")
            # Limpiar el estado preservado del editor para que el nuevo ítem aparezca correctamente
            editor_state_key = f'items_editor_state_{scenario.scenario_id}'
            if editor_state_key in st.session_state:
                del st.session_state[editor_state_key]
            # Limpiar también el hash para forzar recálculo
            last_hash_key = f'items_editor_hash_{scenario.scenario_id}'
            if last_hash_key in st.session_state:
                del st.session_state[last_hash_key]
            st.rerun()  # Mantener rerun para cambios estructurales
    
    with col2:
        # Botón para borrar ítems seleccionados (se procesará después de obtener edited_df)
        delete_selected_button = st.button("🗑️ Borrar Seleccionados", type="secondary", use_container_width=True, key="delete_selected_items")
    
    with col3:
        if st.button("🔄 Recalcular"):
            st.rerun()
    
    # Preservar estado del editor en session_state para evitar pérdida de datos durante reruns
    editor_state_key = f'items_editor_state_{scenario.scenario_id}'
    preserved_df = st.session_state.get(editor_state_key, None)
    
    # Si hay un estado preservado y el número de filas coincide, usarlo como base
    # Esto preserva la información durante reruns
    if preserved_df is not None and len(preserved_df) == len(editable_df):
        # Verificar si el editable_df actual tiene menos información que el preservado
        # Si es así, usar el preservado como base
        try:
            # Comparar si hay valores vacíos en editable_df que están llenos en preserved_df
            use_preserved = False
            for col in editable_df.columns:
                if col in preserved_df.columns:
                    # Si hay más valores no nulos en preserved_df, usarlo
                    if preserved_df[col].notna().sum() > editable_df[col].notna().sum():
                        use_preserved = True
                        break
            if use_preserved:
                editable_df = preserved_df.copy()
        except:
            pass
    
    # Actualizar columnas calculadas antes de renderizar el editor
    # Esto asegura que los totales estén actualizados con los valores actuales
    editable_df = update_calculated_columns_in_dataframe(editable_df, scenario)
    
    # Editor de datos
    edited_df = st.data_editor(
        editable_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="items_editor"
    )
    
    # Actualizar columnas calculadas en el edited_df antes de guardarlo
    # Esto asegura que los totales estén actualizados con los valores actuales
    edited_df = update_calculated_columns_in_dataframe(edited_df, scenario)
    
    # Guardar estado actual del editor para preservarlo en el próximo rerun
    st.session_state[editor_state_key] = edited_df.copy()
    
    # Ayuda contextual de Incoterms
    render_incoterm_help()
    
    # Procesar borrado de ítems seleccionados ANTES de procesar otros cambios
    if delete_selected_button:
        # Identificar ítems a borrar (marcados con "Seleccionar" = True)
        items_to_remove_ids = set()
        if 'Seleccionar' in edited_df.columns and 'item_id' in edited_df.columns:
            for idx, row in edited_df.iterrows():
                is_selected = bool(row.get('Seleccionar', False)) if pd.notna(row.get('Seleccionar', False)) else False
                item_id = row.get('item_id', None)
                if is_selected and item_id and pd.notna(item_id) and str(item_id).strip():
                    items_to_remove_ids.add(str(item_id).strip())
        
        # Eliminar ítems seleccionados del escenario
        if items_to_remove_ids:
            original_count = len(scenario.items)
            scenario.items = [item for item in scenario.items if item.item_id not in items_to_remove_ids]
            
            # Actualizar orden de los ítems restantes
            for i, item in enumerate(scenario.items):
                item.order = i
            
            # Guardar cambios
            project = get_current_project()
            project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                               for s in project.scenarios]
            save_project(project)
            st.session_state['last_saved'] = datetime.now().strftime("%H:%M:%S")
            
            # Limpiar estado preservado del editor para que se regenere el DataFrame
            editor_state_key = f'items_editor_state_{scenario.scenario_id}'
            if editor_state_key in st.session_state:
                del st.session_state[editor_state_key]
            # Limpiar también el hash para forzar recálculo
            last_hash_key = f'items_editor_hash_{scenario.scenario_id}'
            if last_hash_key in st.session_state:
                del st.session_state[last_hash_key]
            
            # Recalcular summary con los ítems actualizados
            summary = calculate_scenario_summary(scenario)
            
            # Mostrar mensaje de éxito
            deleted_count = original_count - len(scenario.items)
            if deleted_count > 0:
                st.success(f"✅ {deleted_count} ítem(s) eliminado(s) correctamente. Los totales se han actualizado.")
            else:
                st.warning("⚠️ No se seleccionaron ítems para borrar.")
            st.rerun()
        else:
            st.warning("⚠️ No se seleccionaron ítems para borrar. Marca los ítems que deseas eliminar usando la columna 'Seleccionar'.")
    
    # Procesar cambios después de edición
    # Sincronizar cambios del DataFrame editado de vuelta a los objetos Item
    # Detectar si hay cambios usando hash del contenido
    try:
        # Calcular hash del DataFrame editado para detectar cambios
        # Usar to_string() para compatibilidad con todas las versiones de pandas
        edited_str = edited_df.to_string()
        edited_hash = hashlib.md5(edited_str.encode('utf-8')).hexdigest()
        
        # Comparar con hash anterior
        last_hash_key = f'items_editor_hash_{scenario.scenario_id}'
        last_hash = st.session_state.get(last_hash_key, None)
        has_changes = (edited_hash != last_hash)
        
        # Guardar hash actual
        st.session_state[last_hash_key] = edited_hash
        
        # Crear diccionario de item_id -> Item para acceso rápido
        items_by_id = {item.item_id: item for item in scenario.items}
        
        # Sincronizar cambios de vuelta a los ítems
        items_to_keep = []
        for idx, row in edited_df.iterrows():
            # Saltar ítems marcados para borrar (aunque ya deberían estar borrados)
            if 'Seleccionar' in row and pd.notna(row.get('Seleccionar', False)) and bool(row.get('Seleccionar', False)):
                continue
            
            # Intentar obtener item_id de la fila editada
            item_id = None
            if 'item_id' in row and pd.notna(row['item_id']) and str(row['item_id']).strip():
                item_id = str(row['item_id']).strip()
            
            # Buscar ítem por item_id
            item = None
            if item_id and item_id in items_by_id:
                item = items_by_id[item_id]
            else:
                # Si no se encontró por item_id, es una fila nueva o el item_id no está disponible
                # Generar nuevo item_id si no existe
                if not item_id:
                    item_id = str(uuid.uuid4())
                    # Asignar el item_id a la fila editada para preservarlo
                    edited_df.at[idx, 'item_id'] = item_id
                
                # Crear nuevo ítem
                item = Item(
                    item_id=item_id,
                    order=len(items_to_keep)
                )
            
            # Actualizar campos editables
            # Buscar category_id por nombre y detectar cambios
            cat_name = str(row['Categoría']) if pd.notna(row['Categoría']) else ""
            old_category_id = item.category_id
            item.category_id = ""
            for cat in scenario.categories:
                if cat.label == cat_name:
                    item.category_id = cat.category_id
                    break
            
            # Detectar cambios en categoría
            if old_category_id != item.category_id:
                has_changes = True
            
            item.item_code = str(row['Código']) if pd.notna(row['Código']) and str(row['Código']).strip() else None
            item.name = str(row['Nombre']) if pd.notna(row['Nombre']) else ""
            item.description = str(row['Descripción']) if pd.notna(row['Descripción']) else ""
            item.unit = str(row['Unidad']) if pd.notna(row['Unidad']) else "UND"
            
            # Detectar cambios en cantidad
            nuevo_qty = float(row['Cantidad']) if pd.notna(row['Cantidad']) else 0.0
            if abs(item.qty - nuevo_qty) > 0.001:
                has_changes = True
            item.qty = nuevo_qty
            
            # Parsear precio unitario que ahora viene como texto formateado
            nuevo_precio = parse_number(str(row['Precio Unitario']) if pd.notna(row['Precio Unitario']) else "")
            # Detectar cambios comparando valores
            if abs(item.unit_price - nuevo_precio) > 0.01:
                has_changes = True
            item.unit_price = nuevo_precio
            
            item.price_includes_vat = bool(row['Precio incluye IVA']) if pd.notna(row['Precio incluye IVA']) else False
            item.vat_rate = float(row['IVA %']) if pd.notna(row['IVA %']) else scenario.default_vat_rate
            item.aiu_applicable = bool(row['Aplica AIU']) if pd.notna(row['Aplica AIU']) else True
            item.client_provided = bool(row['Cliente compra']) if pd.notna(row['Cliente compra']) else False
            item.pass_through = bool(row['Pass through']) if pd.notna(row['Pass through']) else False
            # Nuevos campos de alcance/logística
            if 'Punto de entrega' in row and pd.notna(row['Punto de entrega']):
                item.delivery_point = str(row['Punto de entrega'])
            if 'Incoterm' in row and pd.notna(row['Incoterm']):
                item.incoterm = str(row['Incoterm'])
            item.includes_transport_to_site = bool(row['Transporte a obra']) if pd.notna(row['Transporte a obra']) else False
            item.includes_installation = bool(row['Incluye instalación']) if pd.notna(row['Incluye instalación']) else False
            item.includes_commissioning = bool(row['Incluye commissioning']) if pd.notna(row['Incluye commissioning']) else False
            
            items_to_keep.append(item)
        
        # Actualizar lista de ítems (mantener orden)
        scenario.items = items_to_keep
        # Actualizar orden
        for i, item in enumerate(scenario.items):
            item.order = i
        
        # Actualizar el estado preservado con los nuevos item_ids asignados
        # Esto asegura que las filas nuevas mantengan su item_id en el próximo rerun
        if 'item_id' in edited_df.columns:
            st.session_state[editor_state_key] = edited_df.copy()
        
        # Guardar cambios automáticamente y recalcular si hubo cambios
        if has_changes:
            project = get_current_project()
            project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                               for s in project.scenarios]
            save_project(project)
            # Guardar timestamp de último guardado
            st.session_state['last_saved'] = datetime.now().strftime("%H:%M:%S")
            # Recalcular summary con datos actualizados (sin rerun)
            summary = calculate_scenario_summary(scenario)
            
            # Actualizar las columnas calculadas (Base, IVA, Total) en el edited_df
            # usando los valores actuales del DataFrame
            edited_df = update_calculated_columns_in_dataframe(edited_df, scenario)
            
            # Actualizar el estado preservado con los valores actualizados
            if 'item_id' in edited_df.columns:
                st.session_state[editor_state_key] = edited_df.copy()
            
            # Hacer un rerun suave para actualizar las columnas calculadas en el editor
            # Esto es necesario porque st.data_editor no se puede actualizar en el mismo rerun
            # Solo hacer rerun si hay cambios significativos (no solo al cargar la página)
            if last_hash is not None:  # Solo si no es la primera vez
                st.rerun()
            
            # NO hacer st.rerun() si es la primera vez - las secciones siguientes usarán el summary actualizado
        
    except Exception as e:
        st.warning(f"Error procesando cambios: {e}")
        st.session_state.items_editor_processed = False
    
    st.divider()
    
    # 1. Subtotales por categoría (PRIMERO)
    render_category_totals(scenario, summary)
    
    st.divider()
    
    # 2. Resumen de Costo Directo (SEGUNDO) - usa summary actualizado
    render_direct_cost_summary(scenario, summary)
    
    st.divider()
    
    # 3. Subtotal Costos (TERCERO) - Costo Directo
    render_subtotal_costs(scenario, summary)
    
    st.divider()
    
    # 6. AIU (SEXTO) - calculado sobre Subtotal Costos
    render_aiu_section(scenario, summary)
    
    st.divider()
    
    # 7. Total CAPEX a contratar en EPC, Total CAPEX Cliente y Total CAPEX (SÉPTIMO) - 3 columnas
    st.subheader("Resumen Total CAPEX")
    
    # Calcular sumas para la tercera columna
    total_base = summary['epc_base'] + summary.get('client_capex_base', 0)
    total_vat = summary['epc_vat'] + summary.get('client_capex_vat', 0)
    total_aiu = summary.get('aiu_total', 0) + 0  # client_capex no tiene AIU
    total_capex_final = summary['epc_total'] + summary.get('client_capex_total', 0)
    
    # Crear tabla para alineación perfecta
    capex_data = {
        'Concepto': ['Base', 'IVA', 'AIU', 'Total'],
        'Total CAPEX a contratar en EPC': [
            format_cop(summary['epc_base']),
            format_cop(summary['epc_vat']),
            format_cop(summary.get('aiu_total', 0)),
            format_cop(summary['epc_total'])
        ],
        'Total CAPEX Cliente': [
            format_cop(summary.get('client_capex_base', 0)),
            format_cop(summary.get('client_capex_vat', 0)),
            format_cop(0),
            format_cop(summary.get('client_capex_total', 0))
        ],
        'Total CAPEX': [
            format_cop(total_base),
            format_cop(total_vat),
            format_cop(total_aiu),
            format_cop(total_capex_final)
        ]
    }
    
    capex_df = pd.DataFrame(capex_data)
    # Aplicar alineación a la derecha a columnas numéricas
    styled_capex_df = capex_df.style.applymap(
        lambda x: 'text-align: right', 
        subset=['Total CAPEX a contratar en EPC', 'Total CAPEX Cliente', 'Total CAPEX']
    )
    st.dataframe(styled_capex_df, use_container_width=True, hide_index=True)
    st.caption("Total CAPEX Cliente: Solo ítems marcados como 'Cliente compra'")
    
    st.divider()
    
    # 8. Tabla Resumen Consolidada (OCTAVO)
    render_consolidated_summary_table(scenario, summary)
    
    # Botón de guardar al final
    st.divider()
    col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
    with col_save2:
        if st.button("💾 Guardar Cambios", type="primary", use_container_width=True, key="save_main_button"):
            project = get_current_project()
            if project:
                project.scenarios = [s if s.scenario_id != scenario.scenario_id else scenario 
                                   for s in project.scenarios]
                save_project(project)
                st.session_state['last_saved'] = datetime.now().strftime("%H:%M:%S")
                st.success("✅ Cambios guardados correctamente")
                st.rerun()


def create_waterfall_chart(cat_totals_a: Dict, cat_totals_b: Dict, summary_a: Dict, summary_b: Dict) -> go.Figure:
    """
    Crea un gráfico waterfall mostrando el delta CAPEX por categoría.
    
    Args:
        cat_totals_a: Totales por categoría del escenario A
        cat_totals_b: Totales por categoría del escenario B
        summary_a: Resumen del escenario A
        summary_b: Resumen del escenario B
    
    Returns:
        plotly.graph_objects.Figure con waterfall chart
    """
    # Calcular deltas por categoría
    all_categories = set(cat_totals_a.keys()) | set(cat_totals_b.keys())
    
    category_deltas = []
    for cat_id in all_categories:
        cat_a = cat_totals_a.get(cat_id, {'name': 'N/A', 'base': 0.0})
        cat_b = cat_totals_b.get(cat_id, {'name': 'N/A', 'base': 0.0})
        
        base_a = cat_a['base']
        base_b = cat_b['base']
        delta = base_b - base_a
        
        if abs(delta) > 0.01:  # Solo incluir categorías con cambios significativos
            category_deltas.append({
                'category': cat_a['name'] if cat_a['name'] != 'N/A' else cat_b['name'],
                'delta': delta,
                'delta_pct': (delta / base_a * 100) if base_a != 0 else (100.0 if base_b != 0 else 0.0)
            })
    
    # Ordenar por delta absoluto descendente
    category_deltas.sort(key=lambda x: abs(x['delta']), reverse=True)
    
    if not category_deltas:
        # Si no hay deltas, crear gráfico vacío
        fig = go.Figure()
        fig.add_annotation(text="No hay diferencias significativas entre escenarios", 
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="Waterfall: Delta CAPEX por Categoría (Base sin IVA)")
        return fig
    
    # Preparar datos para waterfall
    categories = [cat['category'] for cat in category_deltas]
    deltas = [cat['delta'] for cat in category_deltas]
    delta_pcts = [cat['delta_pct'] for cat in category_deltas]
    
    # Agregar categoría inicial "Inicio" y final "Total Delta"
    total_delta = sum(deltas)
    categories_with_total = ["Inicio"] + categories + ["Total Delta"]
    measures = ["absolute"] + ["relative"] * len(categories) + ["total"]
    
    # Valores: 0 para inicio, deltas, y total al final
    y_values = [0.0] + deltas + [total_delta]
    
    # Textos para mostrar
    texts = [""] + [format_cop(d) for d in deltas] + [format_cop(total_delta)]
    
    # Preparar hover texts
    hover_texts = ["<b>Inicio</b><br>Base: 0"] + [
        f"<b>{cat}</b><br>Delta: {format_cop(d)}<br>Delta %: {format_percentage(dp, decimals=1)}"
        for cat, d, dp in zip(categories, deltas, delta_pcts)
    ] + [
        f"<b>Total Delta</b><br>Delta: {format_cop(total_delta)}<br>Delta %: {format_percentage((total_delta / summary_a['direct_cost_base'] * 100) if summary_a['direct_cost_base'] != 0 else 0, decimals=1)}"
    ]
    
    # Crear figura
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=measures,
        x=categories_with_total,
        textposition="outside",
        text=texts,
        y=y_values,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts
    ))
    
    # Actualizar colores: verde para aumentos, rojo para disminuciones, azul para total
    # Los gráficos waterfall usan increasing/decreasing/totals en lugar de marker_color
    fig.update_traces(
        increasing={'marker': {'color': '#2ecc71'}},  # Verde para barras positivas
        decreasing={'marker': {'color': '#e74c3c'}},  # Rojo para barras negativas
        totals={'marker': {'color': '#3498db'}}  # Azul para barras de total
    )
    
    # Actualizar layout
    fig.update_layout(
        title="Waterfall: Delta CAPEX por Categoría (Base sin IVA)",
        xaxis_title="Categoría",
        yaxis_title="Delta (COP)",
        hovermode='x unified',
        showlegend=False,
        height=600,
        xaxis={'tickangle': -45}
    )
    
    # Formatear eje Y con separadores de miles
    fig.update_yaxes(tickformat=".0f")
    
    return fig


def create_comparative_bars_chart(cat_totals_a: Dict, cat_totals_b: Dict) -> go.Figure:
    """
    Crea un gráfico de barras comparativas A vs B por categoría.
    
    Args:
        cat_totals_a: Totales por categoría del escenario A
        cat_totals_b: Totales por categoría del escenario B
    
    Returns:
        plotly.graph_objects.Figure con barras comparativas
    """
    all_categories = set(cat_totals_a.keys()) | set(cat_totals_b.keys())
    
    categories_data = []
    for cat_id in all_categories:
        cat_a = cat_totals_a.get(cat_id, {'name': 'N/A', 'base': 0.0})
        cat_b = cat_totals_b.get(cat_id, {'name': 'N/A', 'base': 0.0})
        
        base_a = cat_a['base']
        base_b = cat_b['base']
        total_base = base_a + base_b
        
        categories_data.append({
            'category': cat_a['name'] if cat_a['name'] != 'N/A' else cat_b['name'],
            'base_a': base_a,
            'base_b': base_b,
            'total_base': total_base
        })
    
    # Ordenar por total_base descendente
    categories_data.sort(key=lambda x: x['total_base'], reverse=True)
    
    categories = [cat['category'] for cat in categories_data]
    bases_a = [cat['base_a'] for cat in categories_data]
    bases_b = [cat['base_b'] for cat in categories_data]
    
    # Calcular deltas para hover
    deltas = [b - a for a, b in zip(bases_a, bases_b)]
    delta_pcts = [((b - a) / a * 100) if a != 0 else (100.0 if b != 0 else 0.0) for a, b in zip(bases_a, bases_b)]
    
    # Preparar hover texts
    hover_texts_a = [f"<b>{cat}</b><br>Escenario A: {format_cop(a)}" for cat, a in zip(categories, bases_a)]
    hover_texts_b = [
        f"<b>{cat}</b><br>Escenario B: {format_cop(b)}<br>Delta: {format_cop(d)}<br>Delta %: {format_percentage(dp, decimals=1)}"
        for cat, b, d, dp in zip(categories, bases_b, deltas, delta_pcts)
    ]
    
    fig = go.Figure()
    
    # Barra Escenario A
    fig.add_trace(go.Bar(
        name='Escenario A',
        x=categories,
        y=bases_a,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts_a,
        marker_color='#3498db'
    ))
    
    # Barra Escenario B
    fig.add_trace(go.Bar(
        name='Escenario B',
        x=categories,
        y=bases_b,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts_b,
        marker_color='#e67e22'
    ))
    
    fig.update_layout(
        title="Comparación A vs B por Categoría (Base sin IVA)",
        xaxis_title="Categoría",
        yaxis_title="Base sin IVA (COP)",
        barmode='group',
        hovermode='x unified',
        height=600,
        xaxis={'tickangle': -45}
    )
    
    # Formatear eje Y con separadores de miles
    fig.update_yaxes(tickformat=".0f")
    
    return fig


def create_tornado_chart(scenario_a: Scenario, scenario_b: Scenario, summary_a: Dict, summary_b: Dict) -> go.Figure:
    """
    Crea un gráfico tornado (barras horizontales) de top 10 ítems por impacto.
    
    Args:
        scenario_a: Escenario A
        scenario_b: Escenario B
        summary_a: Resumen del escenario A
        summary_b: Resumen del escenario B
    
    Returns:
        plotly.graph_objects.Figure con tornado chart
    """
    # Obtener matches de ítems
    from ai_analyst import match_items_by_code_and_name
    
    matches = match_items_by_code_and_name(scenario_a.items, scenario_b.items)
    items_totals_a = summary_a.get('items_totals', {})
    items_totals_b = summary_b.get('items_totals', {})
    
    # Calcular deltas
    items_deltas = []
    for item_a, item_b in matches:
        if item_a is None:
            # Solo en B
            totals_b = items_totals_b.get(item_b.item_id, {})
            delta = totals_b.get('base_line', 0.0)
            items_deltas.append({
                'name': item_b.name[:40] + "..." if len(item_b.name) > 40 else item_b.name,
                'name_full': item_b.name,
                'item_code': item_b.item_code or "",
                'delta': delta,
                'qty_a': 0.0,
                'qty_b': item_b.qty,
                'price_a': 0.0,
                'price_b': item_b.unit_price,
                'base_a': 0.0,
                'base_b': totals_b.get('base_line', 0.0)
            })
        elif item_b is None:
            # Solo en A
            totals_a = items_totals_a.get(item_a.item_id, {})
            delta = -totals_a.get('base_line', 0.0)
            items_deltas.append({
                'name': item_a.name[:40] + "..." if len(item_a.name) > 40 else item_a.name,
                'name_full': item_a.name,
                'item_code': item_a.item_code or "",
                'delta': delta,
                'qty_a': item_a.qty,
                'qty_b': 0.0,
                'price_a': item_a.unit_price,
                'price_b': 0.0,
                'base_a': totals_a.get('base_line', 0.0),
                'base_b': 0.0
            })
        else:
            # Ambos existen
            totals_a = items_totals_a.get(item_a.item_id, {})
            totals_b = items_totals_b.get(item_b.item_id, {})
            base_a = totals_a.get('base_line', 0.0)
            base_b = totals_b.get('base_line', 0.0)
            delta = base_b - base_a
            
            items_deltas.append({
                'name': item_a.name[:40] + "..." if len(item_a.name) > 40 else item_a.name,
                'name_full': item_a.name,
                'item_code': item_a.item_code or item_b.item_code or "",
                'delta': delta,
                'qty_a': item_a.qty,
                'qty_b': item_b.qty,
                'price_a': item_a.unit_price,
                'price_b': item_b.unit_price,
                'base_a': base_a,
                'base_b': base_b
            })
    
    # Filtrar top 10 por |delta| absoluto
    items_deltas.sort(key=lambda x: abs(x['delta']), reverse=True)
    top_items = items_deltas[:10]
    
    if not top_items:
        fig = go.Figure()
        fig.add_annotation(text="No hay ítems para comparar", 
                          xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(title="Tornado: Top 10 Ítems por Impacto")
        return fig
    
    # Preparar datos: separar positivos y negativos
    names = [item['name'] for item in top_items]
    deltas_values = [item['delta'] for item in top_items]
    
    # Crear figura
    fig = go.Figure()
    
    # Preparar textos para hover
    hover_texts = []
    for item in top_items:
        hover_text = (
            f"<b>{item['name_full']}</b><br>"
            f"Delta: {format_cop(item['delta'])}<br>"
            f"Código: {item['item_code'] or 'N/A'}<br>"
            f"Qty A: {format_number(item['qty_a'], decimals=2)} | Qty B: {format_number(item['qty_b'], decimals=2)}<br>"
            f"Precio A: {format_cop(item['price_a'])} | Precio B: {format_cop(item['price_b'])}<br>"
            f"Base A: {format_cop(item['base_a'])} | Base B: {format_cop(item['base_b'])}"
        )
        hover_texts.append(hover_text)
    
    # Barras positivas (derecha)
    positive_deltas = [d if d > 0 else 0 for d in deltas_values]
    fig.add_trace(go.Bar(
        y=names,
        x=positive_deltas,
        orientation='h',
        name='Aumento',
        marker_color='#2ecc71',
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        base=0
    ))
    
    # Barras negativas (izquierda)
    negative_deltas = [d if d < 0 else 0 for d in deltas_values]
    fig.add_trace(go.Bar(
        y=names,
        x=negative_deltas,
        orientation='h',
        name='Disminución',
        marker_color='#e74c3c',
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        base=0
    ))
    
    fig.update_layout(
        title="Tornado: Top 10 Ítems por Impacto Absoluto (Base sin IVA)",
        xaxis_title="Delta (COP)",
        yaxis_title="Ítem",
        barmode='overlay',
        hovermode='closest',
        height=600,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    # Formatear eje X con separadores de miles
    fig.update_xaxes(tickformat=".0f")
    
    return fig


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


def render_compare():
    """Renderiza la pestaña de comparación."""
    st.header("⚖️ Comparar Escenarios")
    
    projects = get_all_projects()
    
    if len(projects) < 1:
        st.info("Necesitas al menos un proyecto con escenarios para comparar.")
        return
    
    # Selectores lado A y B
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lado A")
        proj_a_name = st.selectbox(
            "Proyecto A",
            options=[p['name'] for p in projects],
            key="compare_proj_a"
        )
        
        if proj_a_name:
            proj_a = load_project(next(p['project_id'] for p in projects if p['name'] == proj_a_name))
            if proj_a and proj_a.scenarios:
                scenario_a_name = st.selectbox(
                    "Escenario A",
                    options=[s.name for s in proj_a.scenarios],
                    key="compare_scenario_a"
                )
                scenario_a = next(s for s in proj_a.scenarios if s.name == scenario_a_name)
            else:
                scenario_a = None
        else:
            scenario_a = None
    
    with col2:
        st.subheader("Lado B")
        proj_b_name = st.selectbox(
            "Proyecto B",
            options=[p['name'] for p in projects],
            key="compare_proj_b"
        )
        
        if proj_b_name:
            proj_b = load_project(next(p['project_id'] for p in projects if p['name'] == proj_b_name))
            if proj_b and proj_b.scenarios:
                scenario_b_name = st.selectbox(
                    "Escenario B",
                    options=[s.name for s in proj_b.scenarios],
                    key="compare_scenario_b"
                )
                scenario_b = next(s for s in proj_b.scenarios if s.name == scenario_b_name)
            else:
                scenario_b = None
        else:
            scenario_b = None
    
    if not scenario_a or not scenario_b:
        st.info("Selecciona ambos escenarios para comparar.")
        return
    
    # Calcular resúmenes
    summary_a = calculate_scenario_summary(scenario_a)
    summary_b = calculate_scenario_summary(scenario_b)
    
    # Resumen Total CAPEX
    st.divider()
    st.subheader("Resumen Total CAPEX")
    
    # Calcular valores para Escenario A
    epc_base_a = summary_a['epc_base']
    epc_vat_a = summary_a['epc_vat']
    epc_total_a = summary_a['epc_total']
    epc_aiu_a = summary_a.get('aiu_total', 0)
    
    client_base_a = summary_a.get('client_capex_base', 0)
    client_vat_a = summary_a.get('client_capex_vat', 0)
    client_total_a = summary_a.get('client_capex_total', 0)
    
    total_base_a = epc_base_a + client_base_a
    total_vat_a = epc_vat_a + client_vat_a
    total_aiu_a = epc_aiu_a  # AIU solo aplica a EPC
    total_capex_a = epc_total_a + client_total_a
    
    # Calcular valores para Escenario B
    epc_base_b = summary_b['epc_base']
    epc_vat_b = summary_b['epc_vat']
    epc_total_b = summary_b['epc_total']
    epc_aiu_b = summary_b.get('aiu_total', 0)
    
    client_base_b = summary_b.get('client_capex_base', 0)
    client_vat_b = summary_b.get('client_capex_vat', 0)
    client_total_b = summary_b.get('client_capex_total', 0)
    
    total_base_b = epc_base_b + client_base_b
    total_vat_b = epc_vat_b + client_vat_b
    total_aiu_b = epc_aiu_b  # AIU solo aplica a EPC
    total_capex_b = epc_total_b + client_total_b
    
    # Crear datos de la tabla comparativa
    compare_summary_data = []
    
    # Fila Base (sin IVA)
    diff_base_total = total_base_b - total_base_a
    diff_pct_base = ((diff_base_total / total_base_a * 100) if total_base_a != 0 else (100.0 if total_base_b != 0 else 0.0))
    compare_summary_data.append({
        'Concepto': 'Base (sin IVA)',
        'EPC A': format_cop(epc_base_a),
        'EPC B': format_cop(epc_base_b),
        'Cliente A': format_cop(client_base_a),
        'Cliente B': format_cop(client_base_b),
        'Total A': format_cop(total_base_a),
        'Total B': format_cop(total_base_b),
        'Dif. Total': format_cop(diff_base_total),
        'Dif. %': f"{diff_pct_base:.1f}%"
    })
    
    # Fila IVA
    diff_vat_total = total_vat_b - total_vat_a
    diff_pct_vat = ((diff_vat_total / total_vat_a * 100) if total_vat_a != 0 else (100.0 if total_vat_b != 0 else 0.0))
    compare_summary_data.append({
        'Concepto': 'IVA',
        'EPC A': format_cop(epc_vat_a),
        'EPC B': format_cop(epc_vat_b),
        'Cliente A': format_cop(client_vat_a),
        'Cliente B': format_cop(client_vat_b),
        'Total A': format_cop(total_vat_a),
        'Total B': format_cop(total_vat_b),
        'Dif. Total': format_cop(diff_vat_total),
        'Dif. %': f"{diff_pct_vat:.1f}%"
    })
    
    # Fila AIU (solo aplica a EPC y Total)
    diff_aiu_total = total_aiu_b - total_aiu_a
    diff_pct_aiu = ((diff_aiu_total / total_aiu_a * 100) if total_aiu_a != 0 else (100.0 if total_aiu_b != 0 else 0.0))
    compare_summary_data.append({
        'Concepto': 'AIU',
        'EPC A': format_cop(epc_aiu_a),
        'EPC B': format_cop(epc_aiu_b),
        'Cliente A': format_cop(0),
        'Cliente B': format_cop(0),
        'Total A': format_cop(total_aiu_a),
        'Total B': format_cop(total_aiu_b),
        'Dif. Total': format_cop(diff_aiu_total),
        'Dif. %': f"{diff_pct_aiu:.1f}%"
    })
    
    # Fila Total (con IVA)
    diff_total_capex = total_capex_b - total_capex_a
    diff_pct_total = ((diff_total_capex / total_capex_a * 100) if total_capex_a != 0 else (100.0 if total_capex_b != 0 else 0.0))
    compare_summary_data.append({
        'Concepto': 'Total (con IVA)',
        'EPC A': format_cop(epc_total_a),
        'EPC B': format_cop(epc_total_b),
        'Cliente A': format_cop(client_total_a),
        'Cliente B': format_cop(client_total_b),
        'Total A': format_cop(total_capex_a),
        'Total B': format_cop(total_capex_b),
        'Dif. Total': format_cop(diff_total_capex),
        'Dif. %': f"{diff_pct_total:.1f}%"
    })
    
    # Crear DataFrame y mostrar
    compare_summary_df = pd.DataFrame(compare_summary_data)
    # Aplicar alineación a la derecha a columnas numéricas
    styled_summary_df = compare_summary_df.style.applymap(
        lambda x: 'text-align: right',
        subset=['EPC A', 'EPC B', 'Cliente A', 'Cliente B',
                'Total A', 'Total B', 'Dif. Total', 'Dif. %']
    )
    st.dataframe(styled_summary_df, use_container_width=True, hide_index=True)
    st.caption("EPC: Total CAPEX a contratar en EPC | Cliente: Total CAPEX Cliente | Total: Suma de EPC + Cliente")
    
    # Análisis IA
    st.divider()
    st.subheader("🤖 Análisis IA de Diferencias CAPEX")
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.info("💡 Para habilitar el análisis IA, configura GEMINI_API_KEY en el archivo .env")
    else:
        # Checkbox para forzar regeneración
        force_regenerate = st.checkbox("🔄 Forzar regeneración (ignorar caché)", 
                                       help="Marca esta opción para generar un nuevo análisis ignorando los resultados en caché")
        
        if st.button("🔍 Generar Análisis IA", type="primary"):
            with st.spinner("Generando análisis con IA..."):
                analysis = analyze_capex_diff(scenario_a, scenario_b, summary_a, summary_b, api_key, force_regenerate=force_regenerate)
                
                if "error" in analysis:
                    error_msg = analysis.get('error', 'Error desconocido')
                    st.error(f"**Error al generar análisis IA:**")
                    st.code(error_msg, language='text')
                    # Mostrar también el mensaje si existe y es diferente
                    if 'message' in analysis and analysis['message'] != error_msg:
                        st.info(f"Detalles adicionales: {analysis['message']}")
                else:
                    # Renderizar análisis
                    # Executive Summary
                    if analysis.get("executive_summary"):
                        st.markdown("### Resumen Ejecutivo")
                        for point in analysis["executive_summary"]:
                            st.markdown(f"- {point}")
                    
                    # Main Drivers
                    if analysis.get("main_drivers"):
                        st.markdown("### Principales Drivers")
                        drivers_data = []
                        for driver in analysis["main_drivers"]:
                            drivers_data.append({
                                "Driver": driver.get("title", ""),
                                "Impacto (COP)": format_cop(driver.get("impact_cop", 0)),
                                "Explicación": driver.get("explanation", "")
                            })
                        drivers_df = pd.DataFrame(drivers_data)
                        # Aplicar alineación a la derecha a columnas numéricas
                        styled_drivers_df = drivers_df.style.applymap(
                            lambda x: 'text-align: right', 
                            subset=['Impacto (COP)']
                        )
                        st.dataframe(styled_drivers_df, use_container_width=True, hide_index=True)
                    
                    # Root Causes
                    if analysis.get("root_causes"):
                        st.markdown("### Causas Raíz")
                        for cause in analysis["root_causes"]:
                            st.markdown(f"**{cause.get('cause', 'N/A')}**: {cause.get('details', '')}")
                    
                    # Red Flags
                    if analysis.get("red_flags"):
                        st.markdown("### Alertas")
                        flags_data = []
                        for flag in analysis["red_flags"]:
                            flags_data.append({
                                "Severidad": flag.get("severity", "").upper(),
                                "Problema": flag.get("issue", ""),
                                "Por qué importa": flag.get("why_it_matters", "")
                            })
                        flags_df = pd.DataFrame(flags_data)
                        st.dataframe(flags_df, use_container_width=True, hide_index=True)
                    
                    # Recommended Actions
                    if analysis.get("recommended_actions"):
                        st.markdown("### Acciones Recomendadas")
                        actions_data = []
                        for action in analysis["recommended_actions"]:
                            actions_data.append({
                                "Acción": action.get("action", ""),
                                "Impacto Esperado": action.get("expected_impact", ""),
                                "Responsable": action.get("who", "")
                            })
                        actions_df = pd.DataFrame(actions_data)
                        st.dataframe(actions_df, use_container_width=True, hide_index=True)
                    
                    # Questions to Validate
                    if analysis.get("questions_to_validate"):
                        st.markdown("### Preguntas para Validar")
                        for question in analysis["questions_to_validate"]:
                            st.markdown(f"- {question}")


def main():
    """Función principal de la aplicación."""
    # Cargar variables de entorno
    load_dotenv()
    
    # CSS para alinear números a la derecha
    st.markdown("""
    <style>
    /* Alinear números en st.metric a la derecha */
    [data-testid="stMetricValue"] {
        text-align: right !important;
    }
    
    /* Alinear números en st.number_input a la derecha */
    input[type="number"] {
        text-align: right !important;
    }
    
    /* Alinear números en tablas de pandas - todas las columnas excepto la primera */
    /* Usar múltiples selectores para asegurar que funcione con todas las variantes de Streamlit */
    .dataframe td,
    table.dataframe td,
    div[data-testid="stDataFrame"] table td,
    div[data-testid="stDataFrame"] td {
        text-align: right !important;
    }
    .dataframe td:first-child,
    table.dataframe td:first-child,
    div[data-testid="stDataFrame"] table td:first-child,
    div[data-testid="stDataFrame"] td:first-child {
        text-align: left !important;
    }
    .dataframe th,
    table.dataframe th,
    div[data-testid="stDataFrame"] table th,
    div[data-testid="stDataFrame"] th {
        text-align: right !important;
    }
    .dataframe th:first-child,
    table.dataframe th:first-child,
    div[data-testid="stDataFrame"] table th:first-child,
    div[data-testid="stDataFrame"] th:first-child {
        text-align: left !important;
    }
    
    /* Selectores adicionales para tablas de Streamlit */
    div[data-testid="stDataFrame"] table tbody td:not(:first-child),
    div[data-testid="stDataFrame"] table thead th:not(:first-child) {
        text-align: right !important;
    }
    
    /* Alinear números en st.data_editor - solo columnas numéricas específicas */
    /* Por defecto, todas las celdas alineadas a la izquierda */
    .stDataEditor td {
        text-align: left !important;
    }
    .stDataEditor th {
        text-align: left !important;
    }
    /* Columna 7: Cantidad (número) - alinear a la derecha */
    .stDataEditor td:nth-child(7),
    .stDataEditor th:nth-child(7) {
        text-align: right !important;
    }
    /* Columna 8: Precio Unitario (número) - alinear a la derecha */
    .stDataEditor td:nth-child(8),
    .stDataEditor th:nth-child(8) {
        text-align: right !important;
    }
    /* Columna 10: IVA % (número) - alinear a la derecha */
    .stDataEditor td:nth-child(10),
    .stDataEditor th:nth-child(10) {
        text-align: right !important;
    }
    /* Columnas calculadas: Base (sin IVA), IVA, Total (con IVA) - alinear a la derecha */
    /* Estas son las últimas 3 columnas visibles */
    .stDataEditor td:nth-last-child(3),
    .stDataEditor td:nth-last-child(2),
    .stDataEditor td:nth-last-child(1),
    .stDataEditor th:nth-last-child(3),
    .stDataEditor th:nth-last-child(2),
    .stDataEditor th:nth-last-child(1) {
        text-align: right !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    render_sidebar()
    
    # Pestañas principales
    tab1, tab2 = st.tabs(["📝 Editar Escenario", "⚖️ Comparar"])
    
    with tab1:
        render_edit_scenario()
    
    with tab2:
        render_compare()


if __name__ == "__main__":
    main()
