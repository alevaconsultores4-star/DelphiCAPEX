# CAPEX Builder - Complete Refactor

## Overview

Complete refactor of the CAPEX Builder into a Client → Project → Scenario hierarchy with persistent Library, Excel-like UX, AIU with per-component scaling, VAT on Utilidad, and comprehensive file management.

## New Architecture

### Module Structure

- **models.py** - Data models (Client, Project, Scenario, ScenarioItem, LibraryCategory, LibraryItem, UploadMetadata)
- **storage_new.py** - Data Access Layer (DAL) with migration support
- **library_service.py** - Library CRUD operations and validation
- **capex_engine.py** - CAPEX calculation engine (pricing, AIU, VAT, totals)
- **ui_components.py** - Reusable UI components with right-aligned formatting
- **uploads_service.py** - File upload management
- **compare_service.py** - Scenario comparison logic
- **excel_export.py** - Excel/CSV export with formulas
- **app_new.py** - Main application (refactored)

### Data Storage

```
data/
  clients_index.json
  clients/<client_id>.json
  projects/<project_id>.json
  scenarios/<scenario_id>.json
  library_categories.json
  library_items.json
  uploads/<client_id>/<project_id>/<scenario_id>/(project|scenario|items/<item_id>)/
```

## Key Features

### 1. Client → Project → Scenario Hierarchy
- Full CRUD for all levels
- Double confirmation for client deletion (checkbox + type exact name)
- Project duplication with all scenarios
- Scenario duplication, copy to another project, clone as template

### 2. Library System
- Persistent coded library with fixture files
- Case-insensitive unique item codes
- Add items from library to scenarios
- Save scenario items to library

### 3. CAPEX Builder
- Category-first editing (minimal scrolling)
- Excel-like UX with right-aligned numbers
- Per-item pricing modes (UNIT, PER_KWP)
- Per-item AIU factors (0-100%)
- AIU with per-component scaling
- VAT on Utilidad (optional)
- COP/kWp shown for every line item
- Commercial details drawer (collapsible)

### 4. Scenario Variables
- P50/P90 MWh/year
- AC/DC power (MW/MWp)
- Currency and FX rate
- Always-visible derived metrics (COP/kWp, COP/MWac, COP/MWh)

### 5. File Uploads
- Upload at project/scenario/item level
- Structured storage with metadata
- Attach existing files to items

### 6. Exports
- Excel export with formulas and multiple sheets
- CSV export for items and summary

### 7. Comparison
- Compare scenarios within project or across projects (same client)
- Align by item_code (fallback by name)
- Show deltas by category and item

## Migration

On first run, the app automatically migrates existing data:
- Creates "Default" client
- Moves all existing projects to "Default" client
- Converts legacy scenarios to new format
- Migration is idempotent (safe to run multiple times)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
streamlit run app_new.py
```

## Usage

1. **Select/Create Client** - Use sidebar to select or create a client
2. **Select/Create Project** - Projects belong to clients
3. **Select/Create Scenario** - Scenarios belong to projects
4. **Build CAPEX** - Use the Builder tab to add/edit items by category
5. **Manage Library** - Use Library tab to manage categories and items
6. **Compare** - Use Compare tab to compare scenarios
7. **Export** - Use export buttons to download Excel/CSV

## Data Schema

### Client
- client_id (UUID)
- name (string)
- created_at, updated_at (ISO datetime)

### Project
- project_id (UUID)
- client_id (UUID)
- name (string)
- created_at, updated_at (ISO datetime)

### Scenario
- scenario_id (UUID)
- project_id (UUID)
- name (string)
- variables (ScenarioVariables)
- aiu_config (AIUConfig)
- vat_config (VATConfig)
- items (List[ScenarioItem])
- created_at, updated_at (ISO datetime)

### ScenarioItem
- item_id (UUID)
- item_code (string, unique case-insensitive)
- name, description (string)
- category_code (string, references LibraryCategory)
- qty, unit, price (float, string, float)
- pricing_mode (UNIT or PER_KWP)
- vat_rate (float, percentage)
- client_pays (bool)
- aiu_factors (AIUFactors: admin_factor, imprev_factor, util_factor)
- Commercial details (incoterm, delivery_point, includes_installation, etc.)

## AIU Calculation

AIU is calculated with per-component scaling:

1. For each item (excluding client_pays items by default):
   - Base_A += item_base * (admin_factor / 100)
   - Base_I += item_base * (imprev_factor / 100)
   - Base_U += item_base * (util_factor / 100)

2. Then:
   - Admin = Base_A * (admin_pct / 100)
   - Imprev = Base_I * (imprev_pct / 100)
   - Utilidad = Base_U * (util_pct / 100)
   - AIU_total = Admin + Imprev + Utilidad

3. VAT on Utilidad (if enabled):
   - IVA_utilidad = Utilidad * (vat_rate_utilidad / 100)

## Notes

- All numbers are right-aligned for Excel-like UX
- Category-first editing minimizes scrolling
- Library fixture files are created automatically on first run
- Migration preserves all existing data
