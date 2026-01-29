"""
Reusable UI components for CAPEX Builder.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from models import ScenarioItem, PricingMode
from formatting import format_cop, format_number, format_percentage


def inject_delphi_css():
    """Inject Delphi CSS styles from assets/style.css."""
    css_path = Path("assets/style.css")
    if css_path.exists():
        try:
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
        except Exception:
            # Gracefully fail if CSS file can't be read
            pass


def login_form():
    """Render a simple login form and handle authentication."""
    import auth
    st.markdown("## Iniciar sesión")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Correo electrónico", value="", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            user = auth.authenticate(email.strip(), password)
            if user:
                st.session_state.user = user.to_dict()
                st.success(f"Bienvenido {user.email}")
                # Rerun so app shows content for authenticated user.
                # Some Streamlit deployments may not expose `experimental_rerun`;
                # fall back to setting a session flag and stopping execution.
                if hasattr(st, "experimental_rerun") and callable(getattr(st, "experimental_rerun")):
                    st.experimental_rerun()
                else:
                    st.session_state['_rerun_requested'] = True
                    st.stop()
            else:
                st.error("Credenciales inválidas. Verifica email y contraseña.")


def logout_button():
    """Render a logout button in the UI (sidebar recommended)."""
    if st.sidebar.button("Cerrar sesión"):
        if 'user' in st.session_state:
            del st.session_state['user']
        # Try to rerun, otherwise stop to force UI refresh on next interaction
        if hasattr(st, "experimental_rerun") and callable(getattr(st, "experimental_rerun")):
            st.experimental_rerun()
        else:
            st.session_state['_rerun_requested'] = True
            st.stop()


def kpi_card(label: str, value: str, sub: str = ""):
    """Render a Delphi KPI card using HTML + CSS classes."""
    sub_html = f'<p class="delphi-card-sub">{sub}</p>' if sub else ''
    card_html = f"""
    <div class="delphi-card">
        <div class="delphi-card-label">{label}</div>
        <div class="delphi-card-value">{value}</div>
        {sub_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def category_band(title: str, total: Optional[float] = None, item_count: int = 0, meta: str = ""):
    """
    Render a Delphi category header band using HTML + CSS.
    
    Args:
        title: Category title
        total: Optional total amount (if provided, displayed on the right)
        item_count: Number of items in category
        meta: Optional meta text (for backward compatibility, only used if total not provided)
    """
    if total is not None:
        # New format: total on the right
        total_text = f"Total: {format_cop(total)} • {item_count} ítem{'s' if item_count != 1 else ''}"
        total_html = f'<div class="delphi-band-total">{total_text}</div>'
        meta_html = ""
    else:
        # Backward compatibility: use meta text below title
        total_html = ""
        meta_html = f'<p class="delphi-band-meta">{meta}</p>' if meta else ''
    
    band_html = f"""
    <div class="delphi-band">
        <h3 class="delphi-band-title">{title}</h3>
        {total_html}
        {meta_html}
    </div>
    """
    st.markdown(band_html, unsafe_allow_html=True)


def format_number_right_aligned(value: float, decimals: int = 0) -> str:
    """Format number with separators, right-aligned for display."""
    if value is None:
        return ""
    return format_number(value, decimals=decimals)


def render_number_input(
    label: str,
    value: float,
    min_value: float = 0.0,
    max_value: Optional[float] = None,
    step: float = 1.0,
    format_str: str = "%.2f",
    key: Optional[str] = None
) -> float:
    """Render a right-aligned number input."""
    return st.number_input(
        label,
        min_value=min_value,
        max_value=max_value,
        step=step,
        value=value,
        format=format_str,
        key=key
    )


def render_metrics_tiles(metrics: Dict[str, Optional[float]], label_prefix: str = ""):
    """Render metrics as tiles."""
    cols = st.columns(4)
    
    with cols[0]:
        if metrics.get('cop_per_kwp') is not None:
            st.metric(
                f"{label_prefix}COP/kWp",
                format_cop(metrics['cop_per_kwp'])
            )
        else:
            st.metric(f"{label_prefix}COP/kWp", "N/A")
    
    with cols[1]:
        if metrics.get('cop_per_mwac') is not None:
            st.metric(
                f"{label_prefix}COP/MWac",
                format_cop(metrics['cop_per_mwac'])
            )
        else:
            st.metric(f"{label_prefix}COP/MWac", "N/A")
    
    with cols[2]:
        if metrics.get('cop_per_mwh_p50') is not None:
            st.metric(
                f"{label_prefix}COP/MWh P50",
                format_cop(metrics['cop_per_mwh_p50'])
            )
        else:
            st.metric(f"{label_prefix}COP/MWh P50", "N/A")
    
    with cols[3]:
        if metrics.get('cop_per_mwh_p90') is not None:
            st.metric(
                f"{label_prefix}COP/MWh P90",
                format_cop(metrics['cop_per_mwh_p90'])
            )
        else:
            st.metric(f"{label_prefix}COP/MWh P90", "N/A")


def render_subtotal_row(
    category_name: str,
    base: float,
    vat: float,
    total: float,
    percentage: Optional[float] = None,
    col_span: int = 5
):
    """Render a subtotal row for a category with optional percentage."""
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1.5])
    with col1:
        st.markdown(f"**{category_name}**")
    with col2:
        st.markdown(f"**Base:** {format_cop(base)}")
    with col3:
        st.markdown(f"**IVA:** {format_cop(vat)}")
    with col4:
        st.markdown(f"**Total:** {format_cop(total)}")
    with col5:
        if percentage is not None:
            st.markdown(f"**{format_percentage(percentage, decimals=1)}**")
        else:
            st.markdown("**—**")


def create_item_dataframe(
    items: List[ScenarioItem],
    totals: Dict[str, Dict[str, float]],
    scenario_kwp: float
) -> pd.DataFrame:
    """Create a compact DataFrame for items with right-aligned numbers."""
    from capex_engine import calculate_item_cop_per_kwp
    
    data = []
    for item in items:
        item_total = totals.get(item.item_id, {'base': 0.0, 'vat': 0.0, 'total': 0.0})
        cop_per_kwp = calculate_item_cop_per_kwp(item_total['total'], scenario_kwp)
        
        data.append({
            'item_id': item.item_id,
            'Código': item.item_code,
            'Ítem': item.name,
            'Cantidad': item.qty,
            'Unidad': item.unit,
            'Modo precio': 'Por unidad' if item.pricing_mode == PricingMode.UNIT else 'Por kWp',
            'Precio': format_cop(item.price),
            'IVA %': item.vat_rate,
            'Total': format_cop(item_total['total']),
            'COP/kWp': format_cop(cop_per_kwp) if cop_per_kwp is not None else "N/A",
            'Paga cliente': 'Sí' if item.client_pays else 'No'
        })
    
    return pd.DataFrame(data)


def render_item_table_readonly(df: pd.DataFrame):
    """Render a read-only item table with right-aligned numbers."""
    column_config = {
        'Código': st.column_config.TextColumn('Código', width='small'),
        'Ítem': st.column_config.TextColumn('Ítem', width='medium'),
        'Cantidad': st.column_config.NumberColumn('Cantidad', format='%.2f', width='small'),
        'Unidad': st.column_config.TextColumn('Unidad', width='small'),
        'Modo precio': st.column_config.TextColumn('Modo', width='small'),
        'Precio': st.column_config.TextColumn('Precio', width='medium'),
        'IVA %': st.column_config.NumberColumn('IVA %', format='%.1f', width='small'),
        'Total': st.column_config.TextColumn('Total', width='medium'),
        'COP/kWp': st.column_config.TextColumn('COP/kWp', width='medium'),
        'Paga cliente': st.column_config.TextColumn('Paga cliente', width='small')
    }
    
    st.dataframe(
        df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True
    )


def render_commercial_details_drawer(item: ScenarioItem, key_prefix: str = ""):
    """Render commercial details form (no expander - called from container)."""
    col1, col2 = st.columns(2)
    
    with col1:
        incoterm = st.selectbox(
            "Incoterm",
            options=['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'DDP', 'NA'],
            index=['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'DDP', 'NA'].index(item.incoterm) if item.incoterm in ['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'DDP', 'NA'] else 6,
            key=f"{key_prefix}_incoterm"
        )
        includes_installation = st.checkbox(
            "Incluye instalación",
            value=item.includes_installation,
            key=f"{key_prefix}_install"
        )
        includes_transport = st.checkbox(
            "Incluye transporte",
            value=item.includes_transport,
            key=f"{key_prefix}_transport"
        )
    
    with col2:
        delivery_point = st.text_input(
            "Punto de entrega",
            value=item.delivery_point,
            key=f"{key_prefix}_delivery"
        )
        includes_commissioning = st.checkbox(
            "Incluye comisionamiento",
            value=item.includes_commissioning,
            key=f"{key_prefix}_comm"
        )
    
    notes = st.text_area(
        "Notas",
        value=item.notes,
        key=f"{key_prefix}_notes"
    )
    
    return {
        'incoterm': incoterm,
        'includes_installation': includes_installation,
        'includes_transport': includes_transport,
        'delivery_point': delivery_point,
        'includes_commissioning': includes_commissioning,
        'notes': notes
    }


def render_epc_summary(
    direct_epc_total: float,
    direct_epc_vat: float,
    direct_epc_base: float,
    aiu_admin: float,
    aiu_imprev: float,
    aiu_util: float,
    aiu_total: float,
    vat_on_utilidad: float,
    epc_total: float,
    admin_pct: float,
    imprev_pct: float,
    util_pct: float
):
    """
    Render EPC summary with new structure:
    1. Direct Cost line items
    2. AIU breakdown with percentages
    3. EPC calculation summary
    """
    # Section 1: Direct Cost Line Items
    st.markdown("### Costos Directos")
    col1, col2, col3 = st.columns(3)
    with col1:
        kpi_card("Total Costo Directo (Inc. IVA)", format_cop(direct_epc_total))
    with col2:
        kpi_card("Total IVA", format_cop(direct_epc_vat))
    with col3:
        kpi_card("Total Costo Directo (Exc. IVA)", format_cop(direct_epc_base))
    
    st.divider()
    
    # Section 2: AIU Breakdown with Percentages
    if aiu_total > 0:
        st.markdown("### Desglose AIU")
        
        # Calculate percentages as % of Direct Cost (Inc VAT)
        direct_total = direct_epc_total if direct_epc_total > 0 else 1.0
        aiu_admin_pct_of_direct = (aiu_admin / direct_total) * 100
        aiu_imprev_pct_of_direct = (aiu_imprev / direct_total) * 100
        aiu_util_pct_of_direct = (aiu_util / direct_total) * 100
        
        # AIU Rates disclosure
        st.markdown(f"**Tasas AIU:** Administración = {format_percentage(admin_pct, decimals=2)}, Imprevistos = {format_percentage(imprev_pct, decimals=2)}, Utilidad = {format_percentage(util_pct, decimals=2)}")
        
        # AIU Components with percentages
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sub_text = f"{format_percentage(aiu_admin_pct_of_direct, decimals=2)} del Costo Directo"
            kpi_card("Administración", format_cop(aiu_admin), sub_text)
        with col2:
            sub_text = f"{format_percentage(aiu_imprev_pct_of_direct, decimals=2)} del Costo Directo"
            kpi_card("Imprevistos", format_cop(aiu_imprev), sub_text)
        with col3:
            sub_text = f"{format_percentage(aiu_util_pct_of_direct, decimals=2)} del Costo Directo"
            kpi_card("Utilidad", format_cop(aiu_util), sub_text)
        with col4:
            kpi_card("Total AIU", format_cop(aiu_total))
        
        if vat_on_utilidad > 0:
            st.markdown("**IVA sobre Utilidad:**")
            kpi_card("IVA Utilidad", format_cop(vat_on_utilidad))
        
        st.divider()
    
    # Section 3: EPC Calculation Summary (Prominent)
    st.markdown("### Resumen EPC")
    
    # Calculate Total VAT over EPC
    total_vat_over_epc = direct_epc_vat + vat_on_utilidad
    
    # Display as equation: Direct Cost + AIU + VAT = EPC Total
    # Use a more prominent layout with better visual hierarchy
    col1, col2 = st.columns([1.5, 2])
    with col1:
        st.markdown("")
        st.markdown("**A) Total Costo Directo (Inc. IVA)**")
        st.markdown("")
        st.markdown("**B) Total AIU**")
        st.markdown("")
        st.markdown("**C) Total IVA sobre EPC**")
        st.markdown("")
        st.markdown("---")
        st.markdown("")
        st.markdown("**= Total Valor EPC**")
    with col2:
        kpi_card("", format_cop(direct_epc_total))
        kpi_card("", format_cop(aiu_total))
        kpi_card("", format_cop(total_vat_over_epc))
        st.markdown("---")
        # Use larger, more prominent styling for final total
        kpi_card("Total EPC", format_cop(epc_total), "")


def render_aiu_breakdown(
    aiu_admin: float,
    aiu_imprev: float,
    aiu_util: float,
    aiu_total: float,
    vat_on_utilidad: float,
    base_a: float,
    base_i: float,
    base_u: float
):
    """Render AIU breakdown with bases and components (legacy function, kept for backward compatibility)."""
    st.subheader("Desglose AIU")
    
    # Bases row
    st.markdown("**Bases de Cálculo:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        kpi_card("Base Admin", format_cop(base_a))
    with col2:
        kpi_card("Base Imprev", format_cop(base_i))
    with col3:
        kpi_card("Base Util", format_cop(base_u))
    
    # Components row
    st.markdown("**Componentes AIU:**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card("Administración", format_cop(aiu_admin))
    with col2:
        kpi_card("Imprevistos", format_cop(aiu_imprev))
    with col3:
        kpi_card("Utilidad", format_cop(aiu_util))
    with col4:
        kpi_card("Total AIU", format_cop(aiu_total))
    
    # VAT on Utilidad if enabled
    if vat_on_utilidad > 0:
        st.markdown("**IVA sobre Utilidad:**")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            kpi_card("IVA Utilidad", format_cop(vat_on_utilidad))
