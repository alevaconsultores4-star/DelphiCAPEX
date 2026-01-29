"""
CAPEX Builder - Complete Refactor
Client → Project → Scenario hierarchy with Library, AIU, VAT, and Excel-like UX.
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, List
import uuid
from datetime import datetime
import plotly.express as px

# New modules
from models import (
    Client, Project, Scenario, ScenarioItem, ScenarioVariables, AIUConfig, VATConfig,
    PricingMode, AIUFactors, DeliveryPoint, Incoterm
)
from storage_new import (
    ensure_directories, migrate_legacy_data,
    create_client, save_client, load_client, get_all_clients, delete_client,
    create_project, save_project, load_project, get_projects_by_client, delete_project, duplicate_project,
    create_scenario, save_scenario, load_scenario, get_scenarios_by_project, delete_scenario,
    duplicate_scenario, copy_scenario_to_project, clone_scenario_as_template
)
from library_service import (
    load_library_categories, load_library_items, get_category_by_code, get_item_by_code,
    create_library_item, update_library_item, delete_library_item,
    validate_item_code_unique, add_item_from_library, save_item_to_library
)
from capex_engine import (
    calculate_scenario_totals, calculate_normalization_metrics, aggregate_by_category,
    calculate_item_total, calculate_item_cop_per_kwp
)
from ui_components import (
    inject_delphi_css, kpi_card, category_band,
    render_metrics_tiles, render_subtotal_row, create_item_dataframe,
    render_item_table_readonly, render_commercial_details_drawer, render_aiu_breakdown,
    render_epc_summary, login_form, logout_button
)
from uploads_service import upload_file, list_uploads, delete_upload, attach_upload_to_item
from excel_export import export_to_excel, export_items_to_csv, export_summary_to_csv
from compare_service import compare_scenarios, compare_four_scenarios
from formatting import format_cop, format_number, format_percentage, parse_number
import auth


# Page config
st.set_page_config(
    page_title="CAPEX Builder",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Delphi CSS
inject_delphi_css()

# Initialize session state
if 'current_client_id' not in st.session_state:
    st.session_state.current_client_id = None
if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None
if 'current_scenario_id' not in st.session_state:
    st.session_state.current_scenario_id = None
if 'migration_done' not in st.session_state:
    st.session_state.migration_done = False
if 'user' not in st.session_state:
    st.session_state.user = None

# Simple auth gating: if no user, show login form and return
if not st.session_state.user:
    # Provide a small sidebar note and show login in main area
    st.sidebar.info("Inicia sesión para acceder a la aplicación.")
    # Offer seed admin action for local setups (visible only when no users exist)
    users_exist = False
    try:
        users_exist = bool(__import__('storage').get_user_by_email) and len(__import__('storage').load_users()) > 0
    except Exception:
        users_exist = False
    if not users_exist:
        st.info("No se encontraron usuarios. Puedes crear un administrador inicial localmente.")
        if st.button("Crear admin local (delphi@delphi.local)"):
            try:
                admin = auth.seed_admin()
                st.success(f"Admin creado: {admin.email}. Por favor cambia la contraseña.")
            except Exception as e:
                st.error(f"Error creando admin: {e}")
    login_form()
    st.stop()


# ============================================================================
# MIGRATION
# ============================================================================

def run_migration():
    """Run migration on startup (idempotent)."""
    if not st.session_state.migration_done:
        try:
            migrated = migrate_legacy_data()
            if migrated:
                st.success("✅ Migración completada: datos existentes movidos a cliente 'Default'")
            st.session_state.migration_done = True
        except Exception as e:
            st.error(f"Error en migración: {e}")


# ============================================================================
# SIDEBAR - HIERARCHY NAVIGATION
# ============================================================================

def render_sidebar():
    """Render sidebar with Client → Project → Scenario navigation."""
    st.sidebar.title("📊 CAPEX Builder")
    
    # Run migration once
    run_migration()
    
    # CLIENT SELECTOR
    clients = get_all_clients()
    client_options = {c['name']: c['client_id'] for c in clients}
    
    if clients:
        selected_client_name = st.sidebar.selectbox(
            "Cliente",
            options=[""] + list(client_options.keys()),
            index=0 if not st.session_state.current_client_id else (
                list(client_options.keys()).index(
                    next(c['name'] for c in clients if c['client_id'] == st.session_state.current_client_id)
                ) + 1 if st.session_state.current_client_id in client_options.values() else 0
            ),
            key="client_selector"
        )
        
        if selected_client_name:
            st.session_state.current_client_id = client_options[selected_client_name]
        else:
            st.session_state.current_client_id = None
            st.session_state.current_project_id = None
            st.session_state.current_scenario_id = None
    else:
        st.sidebar.info("No hay clientes. Crea uno nuevo.")
        st.session_state.current_client_id = None
    
    # Logout button (if logged in)
    try:
        if st.session_state.user:
            from ui_components import logout_button
            st.sidebar.markdown(f"**Usuario:** {st.session_state.user.get('email')} — `{st.session_state.user.get('role')}`")
            logout_button()
            # Admin quick link
            if st.session_state.user.get('role') == 'delphi_admin':
                if st.sidebar.button("Administrar usuarios"):
                    st.session_state.show_admin = True
    except Exception:
        pass
    
    # Client management
    if st.sidebar.button("➕ Nuevo Cliente", key="btn_new_client"):
        st.session_state.show_new_client = True
    
    if st.session_state.get('show_new_client', False):
        new_client_name = st.sidebar.text_input("Nombre del cliente", key="new_client_name")
        if st.sidebar.button("✅ Crear", key="btn_create_client"):
            if new_client_name and new_client_name.strip():
                try:
                    client = create_client(new_client_name.strip())
                    st.session_state.current_client_id = client.client_id
                    st.session_state.show_new_client = False
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error: {e}")
        if st.sidebar.button("❌ Cancelar", key="btn_cancel_client"):
            st.session_state.show_new_client = False
    
    # Client rename/delete (if client selected)
    if st.session_state.current_client_id:
        client = load_client(st.session_state.current_client_id)
        if client:
            st.sidebar.divider()
            st.sidebar.subheader("Gestión Cliente")
            
            # Rename
            new_client_name = st.sidebar.text_input("Renombrar cliente", value=client.name, key="rename_client")
            if new_client_name and new_client_name != client.name:
                if st.sidebar.button("💾 Guardar nombre", key="save_client_name"):
                    client.name = new_client_name
                    save_client(client)
                    st.sidebar.success("Nombre actualizado")
                    st.rerun()
            
            # Delete with double confirmation
            if st.sidebar.button("🗑️ Eliminar Cliente", type="secondary", key="btn_delete_client"):
                st.session_state.show_delete_client = True
            
            if st.session_state.get('show_delete_client', False):
                st.sidebar.warning("⚠️ Esta acción eliminará el cliente y TODOS sus proyectos y escenarios.")
                confirm_checkbox = st.sidebar.checkbox("Confirmar eliminación", key="confirm_delete_checkbox")
                confirm_name = st.sidebar.text_input("Escribe el nombre exacto del cliente para confirmar", key="confirm_delete_name")
                
                if st.sidebar.button("🗑️ Eliminar", type="primary", key="btn_confirm_delete_client"):
                    if confirm_checkbox and confirm_name == client.name:
                        try:
                            delete_client(client.client_id)
                            st.session_state.current_client_id = None
                            st.session_state.current_project_id = None
                            st.session_state.current_scenario_id = None
                            st.session_state.show_delete_client = False
                            st.sidebar.success("Cliente eliminado")
                            st.rerun()
                        except Exception as e:
                            st.sidebar.error(f"Error: {e}")
                    else:
                        st.sidebar.error("Debes marcar la casilla y escribir el nombre exacto del cliente")
                
                if st.sidebar.button("❌ Cancelar", key="btn_cancel_delete_client"):
                    st.session_state.show_delete_client = False
    
    # PROJECT SELECTOR (if client selected)
    if st.session_state.current_client_id:
        st.sidebar.divider()
        projects = get_projects_by_client(st.session_state.current_client_id)
        project_options = {p['name']: p['project_id'] for p in projects}
        
        if projects:
            selected_project_name = st.sidebar.selectbox(
                "Proyecto",
                options=[""] + list(project_options.keys()),
                index=0 if not st.session_state.current_project_id else (
                    list(project_options.keys()).index(
                        next(p['name'] for p in projects if p['project_id'] == st.session_state.current_project_id)
                    ) + 1 if st.session_state.current_project_id in project_options.values() else 0
                ),
                key="project_selector"
            )
            
            if selected_project_name:
                st.session_state.current_project_id = project_options[selected_project_name]
            else:
                st.session_state.current_project_id = None
                st.session_state.current_scenario_id = None
        else:
            st.sidebar.info("No hay proyectos. Crea uno nuevo.")
            st.session_state.current_project_id = None
        
        # Project management
        if st.sidebar.button("➕ Nuevo Proyecto", key="btn_new_project"):
            st.session_state.show_new_project = True
        
        if st.session_state.get('show_new_project', False):
            new_project_name = st.sidebar.text_input("Nombre del proyecto", key="new_project_name")
            duplicate_project_option = st.sidebar.checkbox("Duplicar proyecto existente", key="dup_project_option")
            
            source_project_id = None
            if duplicate_project_option and projects:
                source_project_name = st.sidebar.selectbox(
                    "Proyecto a duplicar",
                    options=[p['name'] for p in projects],
                    key="source_project_dup"
                )
                if source_project_name:
                    source_project_id = next(p['project_id'] for p in projects if p['name'] == source_project_name)
            
            if st.sidebar.button("✅ Crear", key="btn_create_project"):
                if new_project_name and new_project_name.strip():
                    try:
                        if duplicate_project_option and source_project_id:
                            # Duplicate project
                            new_project = duplicate_project(source_project_id, new_project_name.strip())
                        else:
                            # Create new project
                            new_project = create_project(st.session_state.current_client_id, new_project_name.strip())
                        st.session_state.current_project_id = new_project.project_id
                        st.session_state.show_new_project = False
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Error: {e}")
            if st.sidebar.button("❌ Cancelar", key="btn_cancel_project"):
                st.session_state.show_new_project = False
        
        # Project rename/delete (if project selected)
        if st.session_state.current_project_id:
            project = load_project(st.session_state.current_project_id)
            if project:
                st.sidebar.divider()
                st.sidebar.subheader("Gestión Proyecto")
                
                # Rename
                new_project_name = st.sidebar.text_input("Renombrar proyecto", value=project.name, key="rename_project")
                if new_project_name and new_project_name != project.name:
                    if st.sidebar.button("💾 Guardar nombre", key="save_project_name"):
                        project.name = new_project_name
                        save_project(project)
                        st.sidebar.success("Nombre actualizado")
                        st.rerun()
                
                # Delete
                if st.sidebar.button("🗑️ Eliminar Proyecto", type="secondary", key="btn_delete_project"):
                    if st.sidebar.checkbox("Confirmar eliminación", key="confirm_delete_project"):
                        try:
                            delete_project(project.project_id)
                            st.session_state.current_project_id = None
                            st.session_state.current_scenario_id = None
                            st.sidebar.success("Proyecto eliminado")
                            st.rerun()
                        except Exception as e:
                            st.sidebar.error(f"Error: {e}")
        
        # SCENARIO SELECTOR (if project selected)
        if st.session_state.current_project_id:
            st.sidebar.divider()
            scenarios = get_scenarios_by_project(st.session_state.current_project_id)
            scenario_options = {s['name']: s['scenario_id'] for s in scenarios}
            
            if scenarios:
                selected_scenario_name = st.sidebar.selectbox(
                    "Escenario",
                    options=[""] + list(scenario_options.keys()),
                    index=0 if not st.session_state.current_scenario_id else (
                        list(scenario_options.keys()).index(
                            next(s['name'] for s in scenarios if s['scenario_id'] == st.session_state.current_scenario_id)
                        ) + 1 if st.session_state.current_scenario_id in scenario_options.values() else 0
                    ),
                    key="scenario_selector"
                )
                
                if selected_scenario_name:
                    st.session_state.current_scenario_id = scenario_options[selected_scenario_name]
                else:
                    st.session_state.current_scenario_id = None
            else:
                st.sidebar.info("No hay escenarios. Crea uno nuevo.")
                st.session_state.current_scenario_id = None
            
            # Scenario management
            if st.sidebar.button("➕ Nuevo Escenario", key="btn_new_scenario"):
                st.session_state.show_new_scenario = True
            
            if st.session_state.get('show_new_scenario', False):
                new_scenario_name = st.sidebar.text_input("Nombre del escenario", key="new_scenario_name")
                scenario_action = st.sidebar.radio(
                    "Acción",
                    options=["Crear nuevo", "Duplicar escenario", "Copiar a otro proyecto", "Clonar como plantilla"],
                    key="scenario_action"
                )
                
                source_scenario_id = None
                target_project_id = None
                
                if scenario_action == "Duplicar escenario" and scenarios:
                    source_scenario_name = st.sidebar.selectbox(
                        "Escenario a duplicar",
                        options=[s['name'] for s in scenarios],
                        key="source_scenario_dup"
                    )
                    if source_scenario_name:
                        source_scenario_id = next(s['scenario_id'] for s in scenarios if s['name'] == source_scenario_name)
                
                elif scenario_action == "Copiar a otro proyecto":
                    other_projects = [p for p in projects if p['project_id'] != st.session_state.current_project_id]
                    if other_projects:
                        target_project_name = st.sidebar.selectbox(
                            "Proyecto destino",
                            options=[p['name'] for p in other_projects],
                            key="target_project_copy"
                        )
                        if target_project_name:
                            target_project_id = next(p['project_id'] for p in other_projects if p['name'] == target_project_name)
                        if scenarios:
                            source_scenario_name = st.sidebar.selectbox(
                                "Escenario a copiar",
                                options=[s['name'] for s in scenarios],
                                key="source_scenario_copy"
                            )
                            if source_scenario_name:
                                source_scenario_id = next(s['scenario_id'] for s in scenarios if s['name'] == source_scenario_name)
                
                elif scenario_action == "Clonar como plantilla" and scenarios:
                    source_scenario_name = st.sidebar.selectbox(
                        "Escenario a clonar",
                        options=[s['name'] for s in scenarios],
                        key="source_scenario_template"
                    )
                    if source_scenario_name:
                        source_scenario_id = next(s['scenario_id'] for s in scenarios if s['name'] == source_scenario_name)
                
                if st.sidebar.button("✅ Crear", key="btn_create_scenario"):
                    if new_scenario_name and new_scenario_name.strip():
                        try:
                            if scenario_action == "Duplicar escenario" and source_scenario_id:
                                scenario = duplicate_scenario(source_scenario_id, new_scenario_name.strip())
                            elif scenario_action == "Copiar a otro proyecto" and source_scenario_id and target_project_id:
                                scenario = copy_scenario_to_project(source_scenario_id, target_project_id, new_scenario_name.strip())
                            elif scenario_action == "Clonar como plantilla" and source_scenario_id:
                                scenario = clone_scenario_as_template(source_scenario_id, new_scenario_name.strip())
                            else:
                                scenario = create_scenario(st.session_state.current_project_id, new_scenario_name.strip())
                            st.session_state.current_scenario_id = scenario.scenario_id
                            st.session_state.show_new_scenario = False
                            st.rerun()
                        except Exception as e:
                            st.sidebar.error(f"Error: {e}")
                if st.sidebar.button("❌ Cancelar", key="btn_cancel_scenario"):
                    st.session_state.show_new_scenario = False
            
            # Scenario rename/delete (if scenario selected)
            if st.session_state.current_scenario_id:
                scenario = load_scenario(st.session_state.current_scenario_id)
                if scenario:
                    st.sidebar.divider()
                    st.sidebar.subheader("Gestión Escenario")
                    
                    # Rename
                    new_scenario_name = st.sidebar.text_input("Renombrar escenario", value=scenario.name, key="rename_scenario")
                    if new_scenario_name and new_scenario_name != scenario.name:
                        if st.sidebar.button("💾 Guardar nombre", key="save_scenario_name"):
                            scenario.name = new_scenario_name
                            save_scenario(scenario)
                            st.sidebar.success("Nombre actualizado")
                            st.rerun()
                    
                    # Delete
                    if st.sidebar.button("🗑️ Eliminar Escenario", type="secondary", key="btn_delete_scenario"):
                        if st.sidebar.checkbox("Confirmar eliminación", key="confirm_delete_scenario"):
                            try:
                                delete_scenario(scenario.scenario_id)
                                st.session_state.current_scenario_id = None
                                st.sidebar.success("Escenario eliminado")
                                st.rerun()
                            except Exception as e:
                                st.sidebar.error(f"Error: {e}")


# ============================================================================
# CAPEX BUILDER TAB
# ============================================================================

def save_scenario_changes(scenario: Scenario):
    """
    Helper function to save all scenario changes from session state.
    Applies all tracked changes to items, variables, and configs.
    """
    # Apply all tracked changes to items
    for item in scenario.items:
        item_key = f"item_{item.item_id}"
        if item_key in st.session_state:
            changes = st.session_state[item_key]
            item.item_code = changes.get('code', item.item_code)
            item.name = changes.get('name', item.name)
            item.qty = changes.get('qty', item.qty)
            item.unit = changes.get('unit', item.unit)
            item.pricing_mode = changes.get('pricing_mode', item.pricing_mode)
            item.price = changes.get('price', item.price)
            item.vat_rate = changes.get('vat_rate', item.vat_rate)
            item.price_includes_vat = changes.get('price_includes_vat', getattr(item, 'price_includes_vat', False))
            item.client_pays = changes.get('client_pays', item.client_pays)
            
            # Apply commercial details
            if 'commercial' in changes:
                comm = changes['commercial']
                item.incoterm = comm.get('incoterm', item.incoterm)
                item.includes_installation = comm.get('includes_installation', item.includes_installation)
                item.includes_transport = comm.get('includes_transport', item.includes_transport)
                item.delivery_point = comm.get('delivery_point', item.delivery_point)
                item.includes_commissioning = comm.get('includes_commissioning', item.includes_commissioning)
                item.notes = comm.get('notes', item.notes)
            
            # Apply AIU factors
            if 'aiu_factors' in changes:
                factors = changes['aiu_factors']
                item.aiu_factors.admin_factor = factors.get('admin_factor', item.aiu_factors.admin_factor)
                item.aiu_factors.imprev_factor = factors.get('imprev_factor', item.aiu_factors.imprev_factor)
                item.aiu_factors.util_factor = factors.get('util_factor', item.aiu_factors.util_factor)
    
    # Apply variable changes from session state
    if 'p50_input' in st.session_state:
        scenario.variables.p50_mwh_per_year = st.session_state['p50_input']
    if 'p90_input' in st.session_state:
        scenario.variables.p90_mwh_per_year = st.session_state['p90_input']
    if 'ac_power_input' in st.session_state:
        scenario.variables.ac_power_mw = st.session_state['ac_power_input']
    if 'dc_power_input' in st.session_state:
        scenario.variables.dc_power_mwp = st.session_state['dc_power_input']
    if 'currency_input' in st.session_state:
        scenario.variables.currency = st.session_state['currency_input']
    if 'fx_rate_input' in st.session_state:
        scenario.variables.fx_rate = st.session_state['fx_rate_input']
    
    # Apply AIU config changes
    if 'aiu_enabled' in st.session_state:
        scenario.aiu_config.enabled = st.session_state['aiu_enabled']
    if 'admin_pct' in st.session_state:
        scenario.aiu_config.admin_pct = st.session_state['admin_pct']
    if 'imprev_pct' in st.session_state:
        scenario.aiu_config.imprev_pct = st.session_state['imprev_pct']
    if 'util_pct' in st.session_state:
        scenario.aiu_config.util_pct = st.session_state['util_pct']
    
    # Apply VAT config changes
    if 'vat_recoverable' in st.session_state:
        scenario.vat_config.vat_recoverable = st.session_state['vat_recoverable']
    if 'vat_on_util' in st.session_state:
        scenario.vat_config.vat_on_utilidad_enabled = st.session_state['vat_on_util']
    if 'vat_rate_util' in st.session_state:
        scenario.vat_config.vat_rate_utilidad = st.session_state['vat_rate_util']
    
    # Save the scenario
    save_scenario(scenario)


def render_capex_builder():
    """Render the main CAPEX Builder tab."""
    scenario = load_scenario(st.session_state.current_scenario_id) if st.session_state.current_scenario_id else None
    
    if not scenario:
        st.info("Selecciona un escenario para editar.")
        return
    
    project = load_project(st.session_state.current_project_id)
    client = load_client(st.session_state.current_client_id)
    
    st.header(f"📝 CAPEX Builder: {client.name if client else ''} → {project.name if project else ''} → {scenario.name}")
    
    # Save button at the top
    col_save, col_spacer = st.columns([1, 5])
    with col_save:
        if st.button("💾 Guardar Cambios", type="primary", key="save_changes_top", use_container_width=True):
            save_scenario_changes(scenario)
            st.success("✅ Cambios guardados")
            st.rerun()
    
    # Create temporary scenario with current widget values for live totals
    # Read directly from widget session state keys to get most recent values
    temp_scenario = Scenario.from_dict(scenario.to_dict())
    for item in temp_scenario.items:
        item_key = f"item_{item.item_id}"
        
        # Read from widget keys directly (Streamlit stores widget values there)
        # Fallback to nested session state, then to item defaults
        widget_qty_key = f"qty_{item.item_id}"
        widget_price_key = f"price_{item.item_id}"
        widget_vat_key = f"vat_{item.item_id}"
        widget_mode_key = f"mode_{item.item_id}"
        widget_client_key = f"client_{item.item_id}"
        widget_price_includes_vat_key = f"price_includes_vat_{item.item_id}"
        widget_code_key = f"code_{item.item_id}"
        widget_name_key = f"name_{item.item_id}"
        widget_unit_key = f"unit_{item.item_id}"
        
        # Get values from widget keys (most recent) or fallback to nested session state
        if widget_qty_key in st.session_state:
            item.qty = st.session_state[widget_qty_key]
        elif item_key in st.session_state:
            item.qty = st.session_state[item_key].get('qty', item.qty)
            
        if widget_price_key in st.session_state:
            item.price = st.session_state[widget_price_key]
        elif item_key in st.session_state:
            item.price = st.session_state[item_key].get('price', item.price)
            
        if widget_vat_key in st.session_state:
            item.vat_rate = st.session_state[widget_vat_key]
        elif item_key in st.session_state:
            item.vat_rate = st.session_state[item_key].get('vat_rate', item.vat_rate)
            
        if widget_mode_key in st.session_state:
            item.pricing_mode = st.session_state[widget_mode_key]
        elif item_key in st.session_state:
            item.pricing_mode = st.session_state[item_key].get('pricing_mode', item.pricing_mode)
            
        if widget_client_key in st.session_state:
            item.client_pays = st.session_state[widget_client_key]
        elif item_key in st.session_state:
            item.client_pays = st.session_state[item_key].get('client_pays', item.client_pays)
            
        if widget_price_includes_vat_key in st.session_state:
            item.price_includes_vat = st.session_state[widget_price_includes_vat_key]
        elif item_key in st.session_state:
            item.price_includes_vat = st.session_state[item_key].get('price_includes_vat', getattr(item, 'price_includes_vat', False))
        else:
            item.price_includes_vat = getattr(item, 'price_includes_vat', False)
            
        if widget_code_key in st.session_state:
            item.item_code = st.session_state[widget_code_key]
        elif item_key in st.session_state:
            item.item_code = st.session_state[item_key].get('code', item.item_code)
            
        if widget_name_key in st.session_state:
            item.name = st.session_state[widget_name_key]
        elif item_key in st.session_state:
            item.name = st.session_state[item_key].get('name', item.name)
            
        if widget_unit_key in st.session_state:
            item.unit = st.session_state[widget_unit_key]
        elif item_key in st.session_state:
            item.unit = st.session_state[item_key].get('unit', item.unit)
    
    # Calculate totals with current values
    totals = calculate_scenario_totals(temp_scenario)
    
    # Quick Summary at Top - Show current totals
    st.markdown("### 📊 Resumen Actual")
    col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
    with col_sum1:
        kpi_card("Total EPC", format_cop(totals['epc_total']))
    with col_sum2:
        kpi_card("Total Compra Directa del Cliente", format_cop(totals['client_total']))
    with col_sum3:
        kpi_card("Total Proyecto", format_cop(totals['project_total']))
    with col_sum4:
        scenario_kwp = scenario.variables.dc_power_mwp
        cop_per_kwp_total = totals['project_total'] / scenario_kwp if scenario_kwp > 0 else 0.0
        kpi_card("COP/kWp", format_cop(cop_per_kwp_total) if cop_per_kwp_total > 0 else "N/A")
    
    st.info("💡 **Nota:** Los cambios se reflejan en tiempo real arriba. Haz clic en '💾 Guardar Cambios' al final para guardar permanentemente.")
    st.divider()
    
    # SCENARIO VARIABLES - Wrapped in Delphi container
    st.markdown('<div class="delphi-container">', unsafe_allow_html=True)
    st.subheader("Variables del Escenario")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        p50 = st.number_input("P50 MWh/año", value=scenario.variables.p50_mwh_per_year, format="%.2f", key="p50_input")
        ac_power = st.number_input("Potencia AC (MW)", value=scenario.variables.ac_power_mw, format="%.2f", key="ac_power_input")
    
    with col2:
        p90 = st.number_input("P90 MWh/año", value=scenario.variables.p90_mwh_per_year, format="%.2f", key="p90_input")
        dc_power = st.number_input("Potencia DC (kWp)", value=scenario.variables.dc_power_mwp, format="%.2f", key="dc_power_input")
    
    with col3:
        currency = st.selectbox("Moneda", options=["COP", "USD", "EUR"], index=["COP", "USD", "EUR"].index(scenario.variables.currency) if scenario.variables.currency in ["COP", "USD", "EUR"] else 0, key="currency_input")
        fx_rate = st.number_input("Tasa de cambio", value=scenario.variables.fx_rate, format="%.4f", key="fx_rate_input")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Update variables
    scenario.variables.p50_mwh_per_year = p50
    scenario.variables.p90_mwh_per_year = p90
    scenario.variables.ac_power_mw = ac_power
    scenario.variables.dc_power_mwp = dc_power
    scenario.variables.currency = currency
    scenario.variables.fx_rate = fx_rate
    
    # Derived metrics (always visible) - Using KPI cards
    st.subheader("Métricas Derivadas")
    scenario_kwp = scenario.variables.dc_power_mwp
    metrics_epc = calculate_normalization_metrics(totals['epc_total'], scenario)
    metrics_project = calculate_normalization_metrics(totals['project_total'], scenario)
    
    # EPC Scope KPIs
    st.markdown("**EPC Scope:**")
    col1, col2 = st.columns(2)
    with col1:
        kpi_card("COP/kWp", format_cop(metrics_epc.get('cop_per_kwp')) if metrics_epc.get('cop_per_kwp') is not None else "N/A")
    with col2:
        kpi_card("COP/MWac", format_cop(metrics_epc.get('cop_per_mwac')) if metrics_epc.get('cop_per_mwac') is not None else "N/A")
    
    # Total Proyecto KPIs
    st.markdown("**Total Proyecto:**")
    col1, col2 = st.columns(2)
    with col1:
        kpi_card("COP/kWp", format_cop(metrics_project.get('cop_per_kwp')) if metrics_project.get('cop_per_kwp') is not None else "N/A")
    with col2:
        kpi_card("COP/MWac", format_cop(metrics_project.get('cop_per_mwac')) if metrics_project.get('cop_per_mwac') is not None else "N/A")
    
    st.divider()
    
    # AIU CONFIG
    st.subheader("Configuración AIU")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        aiu_enabled = st.checkbox("Habilitar AIU", value=scenario.aiu_config.enabled, key="aiu_enabled")
        admin_pct = st.number_input("Admin %", value=scenario.aiu_config.admin_pct, format="%.2f", key="admin_pct")
    
    with col2:
        imprev_pct = st.number_input("Imprev %", value=scenario.aiu_config.imprev_pct, format="%.2f", key="imprev_pct")
        util_pct = st.number_input("Util %", value=scenario.aiu_config.util_pct, format="%.2f", key="util_pct")
    
    with col3:
        vat_recoverable = st.checkbox("IVA Recuperable", value=scenario.vat_config.vat_recoverable, key="vat_recoverable")
        vat_on_util = st.checkbox("IVA sobre Utilidad", value=scenario.vat_config.vat_on_utilidad_enabled, key="vat_on_util")
    
    with col4:
        if vat_on_util:
            vat_rate_util = st.number_input("IVA Rate Utilidad %", value=scenario.vat_config.vat_rate_utilidad, format="%.2f", key="vat_rate_util")
        else:
            vat_rate_util = scenario.vat_config.vat_rate_utilidad
    
    # Update configs
    scenario.aiu_config.enabled = aiu_enabled
    scenario.aiu_config.admin_pct = admin_pct
    scenario.aiu_config.imprev_pct = imprev_pct
    scenario.aiu_config.util_pct = util_pct
    scenario.vat_config.vat_recoverable = vat_recoverable
    scenario.vat_config.vat_on_utilidad_enabled = vat_on_util
    scenario.vat_config.vat_rate_utilidad = vat_rate_util
    
    st.divider()
    
    # CATEGORY-FIRST EDITING
    st.subheader("Ítems por Categoría")
    
    categories = load_library_categories()
    categories_sorted = sorted(categories, key=lambda c: c.ordering)
    
    # Group items by category
    items_by_category = {}
    for item in scenario.items:
        cat_code = item.category_code or 'UNCATEGORIZED'
        if cat_code not in items_by_category:
            items_by_category[cat_code] = []
        items_by_category[cat_code].append(item)
    
    # Render each category
    for category in categories_sorted:
        cat_items = items_by_category.get(category.category_code, [])
        # Use temp_scenario for real-time totals (includes current widget values)
        cat_totals = aggregate_by_category(temp_scenario, totals)
        cat_data = cat_totals.get(category.category_code, {'base': 0.0, 'vat': 0.0, 'total': 0.0, 'name': category.name_es})
        
        # Category band with totals on the right (always visible, shows totals even when collapsed)
        item_count = len(cat_items)
        category_band(
            title=category.name_es,
            total=cat_data['total'],
            item_count=item_count
        )
        
        # Session state for expand/collapse (default: expanded if has items, collapsed if empty)
        expander_key = f"category_expanded_{category.category_code}"
        if expander_key not in st.session_state:
            st.session_state[expander_key] = len(cat_items) > 0
        
        is_expanded = st.session_state[expander_key]
        
        with st.expander(f"{category.name_es} - Total: {format_cop(cat_data['total'])}", expanded=is_expanded):
            # Item table with edit functionality
            if cat_items:
                # Header row for column labels
                col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11, col12 = st.columns([2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
                with col1:
                    st.markdown("**Código**")
                with col2:
                    st.markdown("**Ítem**")
                with col3:
                    st.markdown("**Cantidad**")
                with col4:
                    st.markdown("**Unidad**")
                with col5:
                    st.markdown("**Modo**")
                with col6:
                    st.markdown("**Precio**")
                with col7:
                    st.markdown("**IVA %**")
                with col8:
                    st.markdown("**Precio incl. IVA**")
                with col9:
                    st.markdown("**Total**")
                with col10:
                    st.markdown("**COP/kWp**")
                with col11:
                    st.markdown("**Compra Directa del Cliente**")
                with col12:
                    st.markdown("**Acciones**")
                
                for idx, item in enumerate(cat_items):
                    item_total = totals['item_totals'].get(item.item_id, {'base': 0.0, 'vat': 0.0, 'total': 0.0})
                    cop_per_kwp = calculate_item_cop_per_kwp(item_total['total'], scenario_kwp)
                    
                    with st.container():
                        # Initialize session state if not exists
                        item_key = f"item_{item.item_id}"
                        if item_key not in st.session_state:
                            st.session_state[item_key] = {
                                'code': item.item_code,
                                'name': item.name,
                                'qty': item.qty,
                                'unit': item.unit,
                                'pricing_mode': item.pricing_mode,
                                'price': item.price,
                                'vat_rate': item.vat_rate,
                                'price_includes_vat': getattr(item, 'price_includes_vat', False),
                                'client_pays': item.client_pays
                            }
                        
                        # Get current values from session state
                        current_code = st.session_state[item_key].get('code', item.item_code)
                        current_name = st.session_state[item_key].get('name', item.name)
                        current_qty = st.session_state[item_key].get('qty', item.qty)
                        current_unit = st.session_state[item_key].get('unit', item.unit)
                        current_mode = st.session_state[item_key].get('pricing_mode', item.pricing_mode)
                        current_price = st.session_state[item_key].get('price', item.price)
                        current_vat = st.session_state[item_key].get('vat_rate', item.vat_rate)
                        current_price_includes_vat = st.session_state[item_key].get('price_includes_vat', getattr(item, 'price_includes_vat', False))
                        current_client = st.session_state[item_key].get('client_pays', item.client_pays)
                        
                        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11, col12 = st.columns([2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
                        
                        with col1:
                            item_code = st.text_input("Código", value=current_code, key=f"code_{item.item_id}")
                        with col2:
                            item_name = st.text_input("Ítem", value=current_name, key=f"name_{item.item_id}")
                        with col3:
                            qty = st.number_input("Cantidad", value=current_qty, format="%.2f", key=f"qty_{item.item_id}", min_value=0.0)
                        with col4:
                            unit = st.text_input("Unidad", value=current_unit, key=f"unit_{item.item_id}")
                        with col5:
                            pricing_mode = st.selectbox("Modo", options=["UNIT", "PER_KWP"], index=0 if current_mode == PricingMode.UNIT else 1, key=f"mode_{item.item_id}")
                        with col6:
                            price = st.number_input("Precio", value=current_price, format="%.0f", key=f"price_{item.item_id}", min_value=0.0)
                        with col7:
                            vat_rate = st.number_input("IVA %", value=current_vat, format="%.1f", key=f"vat_{item.item_id}", min_value=0.0, max_value=100.0)
                        with col8:
                            price_includes_vat = st.checkbox("Incl. IVA", value=current_price_includes_vat, key=f"price_includes_vat_{item.item_id}")
                        with col9:
                            st.markdown(f"**{format_cop(item_total['total'])}**")
                        with col10:
                            st.text(format_cop(cop_per_kwp) if cop_per_kwp else "N/A")
                        with col11:
                            client_pays = st.checkbox("Compra Directa del Cliente", value=current_client, key=f"client_{item.item_id}")
                        with col11:
                            col_edit, col_del = st.columns(2)
                            with col_edit:
                                if st.button("✏️", key=f"edit_{item.item_id}", help="Editar detalles comerciales"):
                                    st.session_state[f"edit_item_{item.item_id}"] = not st.session_state.get(f"edit_item_{item.item_id}", False)
                            with col_del:
                                if st.button("🗑️", key=f"delete_{item.item_id}", help="Eliminar ítem"):
                                    scenario.items = [i for i in scenario.items if i.item_id != item.item_id]
                                    # Clear session state for deleted item
                                    if item_key in st.session_state:
                                        del st.session_state[item_key]
                                    save_scenario(scenario)
                                    st.rerun()
                        
                        # Update session state with new values from inputs
                        st.session_state[item_key]['code'] = item_code
                        st.session_state[item_key]['name'] = item_name
                        st.session_state[item_key]['qty'] = qty
                        st.session_state[item_key]['unit'] = unit
                        st.session_state[item_key]['pricing_mode'] = pricing_mode
                        st.session_state[item_key]['price'] = price
                        st.session_state[item_key]['vat_rate'] = vat_rate
                        st.session_state[item_key]['price_includes_vat'] = price_includes_vat
                        st.session_state[item_key]['client_pays'] = client_pays
                        
                        # Commercial details drawer (using container instead of nested expander)
                        if st.session_state.get(f"edit_item_{item.item_id}", False):
                            st.markdown('<div class="delphi-container" style="margin-top: 16px; padding: 16px; border: 1px solid var(--border); border-radius: var(--radius-small);">', unsafe_allow_html=True)
                            st.subheader("Detalles comerciales")
                            
                            # Initialize commercial details in session state
                            if 'commercial' not in st.session_state[item_key]:
                                st.session_state[item_key]['commercial'] = {
                                    'incoterm': item.incoterm,
                                    'includes_installation': item.includes_installation,
                                    'includes_transport': item.includes_transport,
                                    'delivery_point': item.delivery_point,
                                    'includes_commissioning': item.includes_commissioning,
                                    'notes': item.notes
                                }
                            if 'aiu_factors' not in st.session_state[item_key]:
                                st.session_state[item_key]['aiu_factors'] = {
                                    'admin_factor': item.aiu_factors.admin_factor,
                                    'imprev_factor': item.aiu_factors.imprev_factor,
                                    'util_factor': item.aiu_factors.util_factor
                                }
                            
                            # Render commercial details drawer (use session state values if available)
                            temp_item = ScenarioItem.from_dict(item.to_dict())
                            if 'commercial' in st.session_state[item_key]:
                                comm = st.session_state[item_key]['commercial']
                                temp_item.incoterm = comm.get('incoterm', temp_item.incoterm)
                                temp_item.includes_installation = comm.get('includes_installation', temp_item.includes_installation)
                                temp_item.includes_transport = comm.get('includes_transport', temp_item.includes_transport)
                                temp_item.delivery_point = comm.get('delivery_point', temp_item.delivery_point)
                                temp_item.includes_commissioning = comm.get('includes_commissioning', temp_item.includes_commissioning)
                                temp_item.notes = comm.get('notes', temp_item.notes)
                            
                            details = render_commercial_details_drawer(temp_item, f"details_{item.item_id}")
                            
                            # Update session state
                            st.session_state[item_key]['commercial']['incoterm'] = details['incoterm']
                            st.session_state[item_key]['commercial']['includes_installation'] = details['includes_installation']
                            st.session_state[item_key]['commercial']['includes_transport'] = details['includes_transport']
                            st.session_state[item_key]['commercial']['delivery_point'] = details['delivery_point']
                            st.session_state[item_key]['commercial']['includes_commissioning'] = details['includes_commissioning']
                            st.session_state[item_key]['commercial']['notes'] = details['notes']
                            
                            # AIU factors
                            st.subheader("Factores AIU")
                            col_a, col_i, col_u = st.columns(3)
                            with col_a:
                                admin_factor = st.number_input("Admin %", value=st.session_state[item_key]['aiu_factors']['admin_factor'], format="%.1f", key=f"aiu_a_{item.item_id}", min_value=0.0, max_value=100.0)
                            with col_i:
                                imprev_factor = st.number_input("Imprev %", value=st.session_state[item_key]['aiu_factors']['imprev_factor'], format="%.1f", key=f"aiu_i_{item.item_id}", min_value=0.0, max_value=100.0)
                            with col_u:
                                util_factor = st.number_input("Util %", value=st.session_state[item_key]['aiu_factors']['util_factor'], format="%.1f", key=f"aiu_u_{item.item_id}", min_value=0.0, max_value=100.0)
                            
                            st.session_state[item_key]['aiu_factors']['admin_factor'] = admin_factor
                            st.session_state[item_key]['aiu_factors']['imprev_factor'] = imprev_factor
                            st.session_state[item_key]['aiu_factors']['util_factor'] = util_factor
                            
                            if st.button("❌ Cerrar", key=f"close_item_{item.item_id}"):
                                st.session_state[f"edit_item_{item.item_id}"] = False
                                st.rerun()
                            
                            st.markdown('</div>', unsafe_allow_html=True)
                        
                        st.divider()
            
            # Actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"➕ Agregar ítem", key=f"add_item_{category.category_code}"):
                    new_item = ScenarioItem(
                        item_id=str(uuid.uuid4()),
                        item_code="",
                        name="Nuevo ítem",
                        category_code=category.category_code,
                        order=len(scenario.items)
                    )
                    scenario.items.append(new_item)
                    save_scenario(scenario)
                    st.rerun()
            
            with col2:
                if st.button(f"📚 Desde biblioteca", key=f"from_lib_{category.category_code}"):
                    st.session_state[f"show_lib_{category.category_code}"] = True
            
            if st.session_state.get(f"show_lib_{category.category_code}", False):
                library_items = load_library_items()
                cat_lib_items = [item for item in library_items if item.default_category_code == category.category_code]
                if cat_lib_items:
                    # Create display options with code, name, and description
                    lib_options = []
                    lib_code_map = {}  # Maps display string to item_code
                    for item in cat_lib_items:
                        # Format: "CODE - Name (Description)" or "CODE - Name" if no description
                        if item.description:
                            display = f"{item.item_code} - {item.name_es} ({item.description})"
                        else:
                            display = f"{item.item_code} - {item.name_es}"
                        lib_options.append(display)
                        lib_code_map[display] = item.item_code
                    
                    selected_display = st.selectbox(
                        "Seleccionar de biblioteca",
                        options=lib_options,
                        key=f"lib_select_{category.category_code}"
                    )
                    
                    # Extract item_code from selected display
                    selected_lib_item = lib_code_map.get(selected_display, "")
                    
                    if st.button("Agregar", key=f"add_lib_{category.category_code}"):
                        if selected_lib_item:
                            lib_item = get_item_by_code(selected_lib_item)
                            if lib_item:
                                scenario_item = add_item_from_library(selected_lib_item, scenario)
                                if scenario_item:
                                    scenario.items.append(scenario_item)
                                    save_scenario(scenario)
                                    st.session_state[f"show_lib_{category.category_code}"] = False
                                    st.rerun()
                else:
                    st.info("No hay ítems en la biblioteca para esta categoría")
    
    # SUMMARY
    st.divider()
    st.subheader("Resumen")
    
    # Category subtotals
    cat_totals = aggregate_by_category(scenario, totals)
    total_project = totals['project_total']
    
    # Header row for subtotals table
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1.5])
    with col1:
        st.markdown("**Categoría**")
    with col2:
        st.markdown("**Base (sin IVA)**")
    with col3:
        st.markdown("**IVA**")
    with col4:
        st.markdown("**Total (con IVA)**")
    with col5:
        st.markdown("**% del Total**")
    
    # Render each category with percentage
    for cat_code, cat_data in sorted(cat_totals.items(), key=lambda x: x[1].get('name', '')):
        pct = (cat_data['total'] / total_project * 100) if total_project > 0 else 0.0
        render_subtotal_row(cat_data['name'], cat_data['base'], cat_data['vat'], cat_data['total'], pct)
    
    # Pie chart showing category distribution
    if cat_totals and total_project > 0:
        st.divider()
        st.markdown("### 📊 Distribución de Costos por Categoría")
        
        # Prepare data for pie chart
        chart_data = []
        for cat_code, cat_data in sorted(cat_totals.items(), key=lambda x: x[1].get('name', '')):
            pct = (cat_data['total'] / total_project * 100) if total_project > 0 else 0.0
            if pct > 0:  # Only include categories with > 0%
                chart_data.append({
                    'Categoría': cat_data['name'],
                    'Total': cat_data['total'],
                    'Porcentaje': pct
                })
        
        if chart_data:
            df_chart = pd.DataFrame(chart_data)
            
            # Create color palette based on Delphi teal
            # Generate variations of teal and complementary colors
            n_colors = len(chart_data)
            colors = px.colors.qualitative.Set3[:n_colors] if n_colors <= 12 else px.colors.qualitative.Set3
            
            # Create pie chart
            fig = px.pie(
                df_chart,
                values='Total',
                names='Categoría',
                title='',
                color_discrete_sequence=colors,
                hole=0.3  # Donut chart style
            )
            
            # Update layout for better appearance
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label',
                textfont_size=11,
                hovertemplate='<b>%{label}</b><br>Total: %{value:,.0f} COP<br>Porcentaje: %{percent}<extra></extra>'
            )
            
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.05
                ),
                margin=dict(l=0, r=150, t=0, b=0),
                font=dict(family="sans serif", size=12),
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Totals - Using KPI cards
    st.subheader("Totales del Proyecto")
    
    # EPC Summary with new structure
    render_epc_summary(
        direct_epc_total=totals['direct_epc_total'],
        direct_epc_vat=totals['direct_epc_vat'],
        direct_epc_base=totals['direct_epc_base'],
        aiu_admin=totals['aiu_admin'],
        aiu_imprev=totals['aiu_imprev'],
        aiu_util=totals['aiu_util'],
        aiu_total=totals['aiu_total'],
        vat_on_utilidad=totals['vat_on_utilidad'],
        epc_total=totals['epc_total'],
        admin_pct=scenario.aiu_config.admin_pct,
        imprev_pct=scenario.aiu_config.imprev_pct,
        util_pct=scenario.aiu_config.util_pct
    )
    
    st.divider()
    
    # Additional Totals
    col1, col2 = st.columns(2)
    with col1:
        kpi_card("Total Compra Directa del Cliente", format_cop(totals['client_total']))
    with col2:
        kpi_card("Total Proyecto", format_cop(totals['project_total']))
    
    # Apply all item changes and save
    st.divider()
    st.markdown("### 💾 Guardar Cambios")
    st.markdown("Todos los cambios realizados arriba se guardarán permanentemente al hacer clic en el botón.")
    
    if st.button("💾 Guardar Cambios", type="primary", use_container_width=True, key="save_changes_bottom"):
        save_scenario_changes(scenario)
        st.success("✅ Cambios guardados")
        st.rerun()
    
    # File uploads section
    st.divider()
    st.subheader("Archivos Adjuntos")
    
    upload_tab1, upload_tab2, upload_tab3 = st.tabs(["Proyecto", "Escenario", "Ítems"])
    
    with upload_tab1:
        st.file_uploader("Subir archivo a nivel proyecto", key="upload_project_file", type=None)
        if st.session_state.get('upload_project_file'):
            file = st.session_state.upload_project_file
            if st.button("Subir", key="btn_upload_project"):
                try:
                    metadata = upload_file(
                        file.read(),
                        file.name,
                        st.session_state.current_client_id,
                        st.session_state.current_project_id,
                        st.session_state.current_scenario_id,
                        "project"
                    )
                    st.success(f"Archivo '{file.name}' subido correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        # List project uploads
        uploads = list_uploads(
            st.session_state.current_client_id,
            st.session_state.current_project_id,
            st.session_state.current_scenario_id,
            level="project"
        )
        if uploads:
            for upload in uploads:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{upload.label} ({upload.filename})")
                with col2:
                    if st.button("🗑️", key=f"delete_upload_{upload.upload_id}"):
                        delete_upload(upload.upload_id, st.session_state.current_client_id, st.session_state.current_project_id, st.session_state.current_scenario_id, "project")
                        st.rerun()
    
    with upload_tab2:
        st.file_uploader("Subir archivo a nivel escenario", key="upload_scenario_file", type=None)
        if st.session_state.get('upload_scenario_file'):
            file = st.session_state.upload_scenario_file
            if st.button("Subir", key="btn_upload_scenario"):
                try:
                    metadata = upload_file(
                        file.read(),
                        file.name,
                        st.session_state.current_client_id,
                        st.session_state.current_project_id,
                        st.session_state.current_scenario_id,
                        "scenario"
                    )
                    st.success(f"Archivo '{file.name}' subido correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        # List scenario uploads
        uploads = list_uploads(
            st.session_state.current_client_id,
            st.session_state.current_project_id,
            st.session_state.current_scenario_id,
            level="scenario"
        )
        if uploads:
            for upload in uploads:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{upload.label} ({upload.filename})")
                with col2:
                    if st.button("🗑️", key=f"delete_upload_{upload.upload_id}"):
                        delete_upload(upload.upload_id, st.session_state.current_client_id, st.session_state.current_project_id, st.session_state.current_scenario_id, "scenario")
                        st.rerun()
    
    with upload_tab3:
        st.info("Los archivos de ítems se pueden adjuntar desde el editor de detalles comerciales de cada ítem.")
    
    # Export buttons
    st.divider()
    st.subheader("Exportar")
    col1, col2 = st.columns(2)
    with col1:
        excel_data = export_to_excel(scenario, totals)
        st.download_button(
            "📥 Exportar Excel",
            excel_data,
            file_name=f"{scenario.name}.xlsx",
            mime="application/vnd.openpyxl.document.spreadsheetml.sheet"
        )
    with col2:
        csv_data = export_items_to_csv(scenario, totals)
        st.download_button(
            "📥 Exportar CSV",
            csv_data,
            file_name=f"{scenario.name}.csv",
            mime="text/csv"
        )


# ============================================================================
# LIBRARY TAB
# ============================================================================

def render_library():
    """Render Library management tab."""
    st.header("📚 Biblioteca")
    
    tab1, tab2 = st.tabs(["Categorías", "Ítems"])
    
    with tab1:
        st.subheader("Categorías")
        categories = load_library_categories()
        categories_sorted = sorted(categories, key=lambda c: c.ordering)
        
        for cat in categories_sorted:
            st.text(f"{cat.category_code}: {cat.name_es} ({cat.name_en})")
    
    with tab2:
        st.subheader("Ítems")
        items = load_library_items()
        
        # Filter by category
        categories = load_library_categories()
        cat_options = ["Todas"] + [cat.category_code for cat in categories]
        selected_cat = st.selectbox("Filtrar por categoría", options=cat_options)
        
        if selected_cat != "Todas":
            items = [item for item in items if item.default_category_code == selected_cat]
        
        # Display items
        items_data = []
        for item in items:
            items_data.append({
                'Código': item.item_code,
                'Nombre ES': item.name_es,
                'Nombre EN': item.name_en,
                'Categoría': item.default_category_code,
                'Unidad': item.default_unit,
                'IVA %': item.default_vat_rate * 100
            })
        
        if items_data:
            df = pd.DataFrame(items_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay ítems en la biblioteca")


# ============================================================================
# PROJECTS OVERVIEW
# ============================================================================

def render_projects_overview():
    """Render overview of all projects for the selected client with metrics."""
    client = load_client(st.session_state.current_client_id)
    
    if not client:
        st.info("Cliente no encontrado.")
        return
    
    st.header(f"📊 Resumen de Proyectos: {client.name}")
    
    # Get all projects for client
    projects = get_projects_by_client(st.session_state.current_client_id)
    
    if not projects:
        st.info("No hay proyectos para este cliente. Crea uno nuevo desde el panel lateral.")
        return
    
    # Store selected scenarios per project in session state
    if 'project_scenario_selections' not in st.session_state:
        st.session_state.project_scenario_selections = {}
    
    # Prepare data for table
    table_data = []
    
    # Initialize totals accumulators
    total_capex = 0.0
    total_kwp = 0.0
    total_mwh = 0.0
    total_epc = 0.0
    total_client = 0.0
    
    for project in projects:
        project_id = project['project_id']
        project_name = project['name']
        
        # Get scenarios for this project
        scenarios = get_scenarios_by_project(project_id)
        
        if not scenarios:
            # No scenarios, show empty row
            table_data.append({
                'Proyecto': project_name,
                'Escenario': 'Sin escenarios',
                'CAPEX Total': 'N/A',
                'kWp': 'N/A',
                'MWh/año': 'N/A',
                'Valor EPC': 'N/A',
                'Compras Cliente': 'N/A',
                'Acción': project_id
            })
            continue
        
        # Get or set default scenario for this project
        if project_id not in st.session_state.project_scenario_selections:
            # Default to first scenario or most recently updated
            st.session_state.project_scenario_selections[project_id] = scenarios[0]['scenario_id']
        
        selected_scenario_id = st.session_state.project_scenario_selections[project_id]
        
        # Find selected scenario
        selected_scenario = next((s for s in scenarios if s['scenario_id'] == selected_scenario_id), None)
        if not selected_scenario:
            # If selected scenario not found, use first one
            selected_scenario = scenarios[0]
            st.session_state.project_scenario_selections[project_id] = selected_scenario['scenario_id']
        
        # Load full scenario to calculate metrics
        scenario = load_scenario(selected_scenario_id)
        
        if scenario:
            # Calculate totals
            totals = calculate_scenario_totals(scenario)
            
            # Get metrics
            capex_total = totals['project_total']
            kwp = scenario.variables.dc_power_mwp
            mwh_per_year = scenario.variables.p50_mwh_per_year
            epc_total = totals['epc_total']
            client_total = totals['client_total']
            
            # Accumulate totals (only numeric values)
            total_capex += capex_total
            total_kwp += kwp
            total_mwh += mwh_per_year
            total_epc += epc_total
            total_client += client_total
            
            table_data.append({
                'Proyecto': project_name,
                'Escenario': selected_scenario['name'],
                'CAPEX Total': format_cop(capex_total),
                'kWp': format_number(kwp, decimals=2),
                'MWh/año': format_number(mwh_per_year, decimals=2),
                'Valor EPC': format_cop(epc_total),
                'Compras Cliente': format_cop(client_total),
                'Acción': project_id,
                '_scenario_id': selected_scenario_id,
                '_scenarios': scenarios
            })
        else:
            table_data.append({
                'Proyecto': project_name,
                'Escenario': 'Error cargando',
                'CAPEX Total': 'N/A',
                'kWp': 'N/A',
                'MWh/año': 'N/A',
                'Valor EPC': 'N/A',
                'Compras Cliente': 'N/A',
                'Acción': project_id,
                '_scenarios': scenarios
            })
    
    # Display table with scenario selectors
    st.subheader("Proyectos y Métricas")
    
    # Header row
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 2, 1.5, 1.5, 2, 2, 1.5])
    with col1:
        st.markdown("**Proyecto**")
    with col2:
        st.markdown("**Escenario**")
    with col3:
        st.markdown("**CAPEX Total**")
    with col4:
        st.markdown("**kWp**")
    with col5:
        st.markdown("**MWh/año**")
    with col6:
        st.markdown("**Valor EPC**")
    with col7:
        st.markdown("**Compras Cliente**")
    with col8:
        st.markdown("**Acción**")
    
    st.divider()
    
    # Create a more interactive table using columns
    for idx, row_data in enumerate(table_data):
        with st.container():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 2, 1.5, 1.5, 2, 2, 1.5])
            
            project_id = row_data['Acción']
            
            with col1:
                st.markdown(f"**{row_data['Proyecto']}**")
            
            with col2:
                if row_data.get('_scenarios') and len(row_data['_scenarios']) > 0:
                    scenario_options = {s['name']: s['scenario_id'] for s in row_data['_scenarios']}
                    selected_scenario_name = next(
                        (s['name'] for s in row_data['_scenarios'] if s['scenario_id'] == row_data.get('_scenario_id', '')),
                        row_data['_scenarios'][0]['name']
                    )
                    
                    new_selection = st.selectbox(
                        "Escenario",
                        options=list(scenario_options.keys()),
                        index=list(scenario_options.keys()).index(selected_scenario_name) if selected_scenario_name in scenario_options.keys() else 0,
                        key=f"scenario_selector_{project_id}",
                        label_visibility="collapsed"
                    )
                    
                    # Update selection if changed
                    if new_selection in scenario_options:
                        new_scenario_id = scenario_options[new_selection]
                        if st.session_state.project_scenario_selections.get(project_id) != new_scenario_id:
                            st.session_state.project_scenario_selections[project_id] = new_scenario_id
                            st.rerun()
                else:
                    st.markdown("Sin escenarios")
            
            with col3:
                st.markdown(row_data['CAPEX Total'])
            
            with col4:
                st.markdown(row_data['kWp'])
            
            with col5:
                st.markdown(row_data['MWh/año'])
            
            with col6:
                st.markdown(row_data['Valor EPC'])
            
            with col7:
                st.markdown(row_data['Compras Cliente'])
            
            with col8:
                if row_data.get('_scenario_id'):
                    if st.button("Ver", key=f"view_{project_id}", use_container_width=True):
                        st.session_state.current_project_id = project_id
                        st.session_state.current_scenario_id = row_data['_scenario_id']
                        st.rerun()
            
            st.divider()
    
    # Totals row
    st.markdown('<div style="background-color: #F5F7FA; padding: 12px; border-radius: 8px; margin-top: 8px;">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 2, 1.5, 1.5, 2, 2, 1.5])
    with col1:
        st.markdown("**TOTALES**")
    with col2:
        st.markdown("")  # Vacío para escenario
    with col3:
        st.markdown(f"**{format_cop(total_capex)}**")
    with col4:
        st.markdown(f"**{format_number(total_kwp, decimals=2)}**")
    with col5:
        st.markdown(f"**{format_number(total_mwh, decimals=2)}**")
    with col6:
        st.markdown(f"**{format_cop(total_epc)}**")
    with col7:
        st.markdown(f"**{format_cop(total_client)}**")
    with col8:
        st.markdown("")  # Vacío para acción
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Alternative: Show as dataframe (simpler but less interactive)
    # df = pd.DataFrame([{k: v for k, v in row.items() if not k.startswith('_')} for row in table_data])
    # st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================================
# COMPARE TAB
# ============================================================================

def render_compare():
    """Render scenario comparison tab."""
    st.header("⚖️ Comparar Escenarios")
    
    if not st.session_state.current_client_id:
        st.info("Selecciona un cliente para comparar escenarios.")
        return
    
    # Get all projects for client
    projects = get_projects_by_client(st.session_state.current_client_id)
    
    if len(projects) < 1:
        st.info("Necesitas al menos un proyecto para comparar.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.subheader("Escenario A")
        project_a_name = st.selectbox("Proyecto A", options=[p['name'] for p in projects], key="compare_project_a")
        if project_a_name:
            project_a = next(p for p in projects if p['name'] == project_a_name)
            scenarios_a = get_scenarios_by_project(project_a['project_id'])
            if scenarios_a:
                scenario_a_name = st.selectbox("Escenario A", options=[s['name'] for s in scenarios_a], key="compare_scenario_a")
            else:
                scenario_a_name = None
        else:
            scenario_a_name = None
    
    with col2:
        st.subheader("Escenario B")
        project_b_name = st.selectbox("Proyecto B", options=[p['name'] for p in projects], key="compare_project_b")
        if project_b_name:
            project_b = next(p for p in projects if p['name'] == project_b_name)
            scenarios_b = get_scenarios_by_project(project_b['project_id'])
            if scenarios_b:
                scenario_b_name = st.selectbox("Escenario B", options=[s['name'] for s in scenarios_b], key="compare_scenario_b")
            else:
                scenario_b_name = None
        else:
            scenario_b_name = None
    
    with col3:
        st.subheader("Escenario C")
        project_c_name = st.selectbox("Proyecto C", options=[p['name'] for p in projects], key="compare_project_c")
        if project_c_name:
            project_c = next(p for p in projects if p['name'] == project_c_name)
            scenarios_c = get_scenarios_by_project(project_c['project_id'])
            if scenarios_c:
                scenario_c_name = st.selectbox("Escenario C", options=[s['name'] for s in scenarios_c], key="compare_scenario_c")
            else:
                scenario_c_name = None
        else:
            scenario_c_name = None
    
    with col4:
        st.subheader("Escenario D")
        project_d_name = st.selectbox("Proyecto D", options=[p['name'] for p in projects], key="compare_project_d")
        if project_d_name:
            project_d = next(p for p in projects if p['name'] == project_d_name)
            scenarios_d = get_scenarios_by_project(project_d['project_id'])
            if scenarios_d:
                scenario_d_name = st.selectbox("Escenario D", options=[s['name'] for s in scenarios_d], key="compare_scenario_d")
            else:
                scenario_d_name = None
        else:
            scenario_d_name = None
    
    # Compare
    if scenario_a_name and scenario_b_name and scenario_c_name and scenario_d_name:
        scenario_a_id = next(s['scenario_id'] for s in scenarios_a if s['name'] == scenario_a_name)
        scenario_b_id = next(s['scenario_id'] for s in scenarios_b if s['name'] == scenario_b_name)
        scenario_c_id = next(s['scenario_id'] for s in scenarios_c if s['name'] == scenario_c_name)
        scenario_d_id = next(s['scenario_id'] for s in scenarios_d if s['name'] == scenario_d_name)
        
        scenario_a = load_scenario(scenario_a_id)
        scenario_b = load_scenario(scenario_b_id)
        scenario_c = load_scenario(scenario_c_id)
        scenario_d = load_scenario(scenario_d_id)
        
        if scenario_a and scenario_b and scenario_c and scenario_d:
            comparison = compare_four_scenarios(scenario_a, scenario_b, scenario_c, scenario_d)
            
            st.divider()
            st.subheader("Comparación General")
            
            # Fila 1: Valor Total del Proyecto
            st.markdown("**A) Valor Total del Proyecto**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                kpi_card("Escenario A", format_cop(comparison['overall']['project_total_a']))
            with col2:
                kpi_card("Escenario B", format_cop(comparison['overall']['project_total_b']))
            with col3:
                kpi_card("Escenario C", format_cop(comparison['overall']['project_total_c']))
            with col4:
                kpi_card("Escenario D", format_cop(comparison['overall']['project_total_d']))
            
            # Fila 2: Total Compra por Cliente
            st.markdown("**B) Total Compra por Cliente**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                kpi_card("Escenario A", format_cop(comparison['overall']['client_total_a']))
            with col2:
                kpi_card("Escenario B", format_cop(comparison['overall']['client_total_b']))
            with col3:
                kpi_card("Escenario C", format_cop(comparison['overall']['client_total_c']))
            with col4:
                kpi_card("Escenario D", format_cop(comparison['overall']['client_total_d']))
            
            # Fila 3: Total Valor EPC
            st.markdown("**C) Total Valor EPC**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                kpi_card("Escenario A", format_cop(comparison['overall']['epc_total_a']))
            with col2:
                kpi_card("Escenario B", format_cop(comparison['overall']['epc_total_b']))
            with col3:
                kpi_card("Escenario C", format_cop(comparison['overall']['epc_total_c']))
            with col4:
                kpi_card("Escenario D", format_cop(comparison['overall']['epc_total_d']))
            
            # Fila 4: COP/kWp Total Proyecto
            st.markdown("**D) COP/kWp Total Proyecto**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                kpi_card("Escenario A", format_cop(comparison['overall']['cop_per_kwp_a']) if comparison['overall']['cop_per_kwp_a'] > 0 else "N/A")
            with col2:
                kpi_card("Escenario B", format_cop(comparison['overall']['cop_per_kwp_b']) if comparison['overall']['cop_per_kwp_b'] > 0 else "N/A")
            with col3:
                kpi_card("Escenario C", format_cop(comparison['overall']['cop_per_kwp_c']) if comparison['overall']['cop_per_kwp_c'] > 0 else "N/A")
            with col4:
                kpi_card("Escenario D", format_cop(comparison['overall']['cop_per_kwp_d']) if comparison['overall']['cop_per_kwp_d'] > 0 else "N/A")
            
            # Fila 5: Potencia DC (kWp)
            st.markdown("**E) Potencia DC (kWp)**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                kpi_card("Escenario A", format_number(comparison['overall']['kwp_a'], decimals=2))
            with col2:
                kpi_card("Escenario B", format_number(comparison['overall']['kwp_b'], decimals=2))
            with col3:
                kpi_card("Escenario C", format_number(comparison['overall']['kwp_c'], decimals=2))
            with col4:
                kpi_card("Escenario D", format_number(comparison['overall']['kwp_d'], decimals=2))
            
            # Fila 6: P50 MWh/año
            st.markdown("**F) P50 MWh/año**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                kpi_card("Escenario A", format_number(comparison['overall']['p50_mwh_a'], decimals=2))
            with col2:
                kpi_card("Escenario B", format_number(comparison['overall']['p50_mwh_b'], decimals=2))
            with col3:
                kpi_card("Escenario C", format_number(comparison['overall']['p50_mwh_c'], decimals=2))
            with col4:
                kpi_card("Escenario D", format_number(comparison['overall']['p50_mwh_d'], decimals=2))
            
            st.divider()
            st.subheader("Por Categoría")
            
            # Sort categories: normal categories first, then AIU, then Total Proyecto
            sorted_categories = []
            aiu_category = None
            total_project_category = None
            
            for cat in comparison['by_category']:
                if cat['category_code'] == 'AIU':
                    aiu_category = cat
                elif cat['category_code'] == 'TOTAL_PROJECT':
                    total_project_category = cat
                else:
                    sorted_categories.append(cat)
            
            # Add AIU and Total Proyecto at the end
            if aiu_category:
                sorted_categories.append(aiu_category)
            if total_project_category:
                sorted_categories.append(total_project_category)
            
            # Prepare data for table with Total A, Total B, Total C, Total D
            category_data = []
            for cat in sorted_categories:
                category_data.append({
                    'Categoría': cat['category_name'],
                    'Total A': format_cop(cat['total_a']),
                    'Total B': format_cop(cat['total_b']),
                    'Total C': format_cop(cat['total_c']),
                    'Total D': format_cop(cat['total_d'])
                })
            
            comparison_df = pd.DataFrame(category_data)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)
            
            # Gráfico de barras
            st.divider()
            st.subheader("Gráfico Comparativo por Categoría")
            
            # Preparar datos para el gráfico (usando categorías ordenadas)
            chart_data = []
            for cat in sorted_categories:
                chart_data.append({
                    'Categoría': cat['category_name'],
                    'Escenario A': cat['total_a'],
                    'Escenario B': cat['total_b'],
                    'Escenario C': cat['total_c'],
                    'Escenario D': cat['total_d']
                })
            
            df_chart = pd.DataFrame(chart_data)
            
            # Crear gráfico de barras agrupadas
            fig = px.bar(
                df_chart,
                x='Categoría',
                y=['Escenario A', 'Escenario B', 'Escenario C', 'Escenario D'],
                barmode='group',
                title='Comparación de Totales por Categoría',
                labels={'value': 'Valor Total (COP)', 'variable': 'Escenario'},
                color_discrete_map={
                    'Escenario A': '#0B7285',  # Delphi teal
                    'Escenario B': '#075A66',  # Delphi teal dark
                    'Escenario C': '#14A085',  # Alternative teal shade
                    'Escenario D': '#0891B2'   # Another teal shade for D
                }
            )
            
            # Ajustar layout del gráfico
            fig.update_layout(
                xaxis_title="Categoría",
                yaxis_title="Valor Total (COP)",
                legend_title="Escenario",
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main application entry point."""
    render_sidebar()
    
    # If admin requested user management, show admin panel
    if st.session_state.get('show_admin'):
        render_admin_panel()
        return
    if not st.session_state.current_client_id:
        st.info("👈 Selecciona un cliente en el panel lateral para comenzar.")
        return
    
    # Si hay cliente pero no escenario, mostrar vista de resumen
    if not st.session_state.current_scenario_id:
        render_projects_overview()
        return
    
    # Si hay escenario seleccionado, mostrar tabs normales
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📝 Builder", "📚 Biblioteca", "⚖️ Comparar"])
    
    with tab1:
        render_capex_builder()
    
    with tab2:
        render_library()
    
    with tab3:
        render_compare()


def render_admin_panel():
    """Admin panel for user management (Delphi admins only)."""
    import storage
    st.header("Administración de usuarios")
    if not st.session_state.user or st.session_state.user.get('role') != 'delphi_admin':
        st.error("Acceso denegado. Se requiere rol Delphi admin.")
        return

    users = storage.load_users()
    # List users
    st.subheader("Cuentas existentes")
    for u in users:
        cols = st.columns([3, 2, 1])
        with cols[0]:
            st.markdown(f"**{u.get('email','')}** — {u.get('role','')}")
            if u.get('client_id'):
                st.markdown(f"_Client:_ {u.get('client_id')}")
        with cols[1]:
            if st.button(f"Editar:{u.get('user_id')}", key=f"edit_user_{u.get('user_id')}"):
                st.session_state.edit_user = u
                st.experimental_rerun()
        with cols[2]:
            if st.button(f"Eliminar:{u.get('user_id')}", key=f"del_user_{u.get('user_id')}"):
                storage.delete_user(u.get('user_id'))
                st.success("Usuario eliminado")
                st.experimental_rerun()

    st.divider()
    st.subheader("Crear nueva cuenta")
    with st.form("create_user_form"):
        email = st.text_input("Email", value="")
        role = st.selectbox("Rol", options=["client_viewer", "delphi_admin"])
        client_id = st.text_input("Client ID (opcional)", value="")
        password = st.text_input("Contraseña inicial", type="password")
        submitted = st.form_submit_button("Crear usuario")
        if submitted:
            if not email or not password:
                st.error("Email y contraseña son requeridos.")
            else:
                import auth
                new_user = models.User(
                    email=email.strip(),
                    password_hash=auth.hash_password(password),
                    role=role,
                    client_id=client_id.strip() or None
                )
                storage.create_user(new_user.to_dict())
                st.success(f"Usuario creado: {email}")
                st.experimental_rerun()

    # Edit user drawer
    if st.session_state.get('edit_user'):
        u = st.session_state.get('edit_user')
        st.subheader(f"Editar {u.get('email')}")
        with st.form("edit_user_form"):
            new_email = st.text_input("Email", value=u.get('email',''))
            new_role = st.selectbox("Rol", options=["client_viewer", "delphi_admin"], index=0 if u.get('role','')=="client_viewer" else 1)
            new_client = st.text_input("Client ID (opcional)", value=u.get('client_id') or "")
            new_password = st.text_input("Nueva contraseña (dejar vacío = mantener)", type="password")
            save = st.form_submit_button("Guardar cambios")
            if save:
                updated = u.copy()
                updated['email'] = new_email.strip()
                updated['role'] = new_role
                updated['client_id'] = new_client.strip() or None
                if new_password:
                    import auth
                    updated['password_hash'] = auth.hash_password(new_password)
                updated['updated_at'] = datetime.now().isoformat()
                storage.update_user(updated)
                st.success("Usuario actualizado")
                st.session_state.edit_user = None
                st.experimental_rerun()


if __name__ == "__main__":
    main()
