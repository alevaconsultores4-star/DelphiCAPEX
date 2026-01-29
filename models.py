"""
Data models for CAPEX Builder application.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid


class PricingMode(str, Enum):
    """Pricing modes for items."""
    UNIT = "UNIT"
    PER_KWP = "PER_KWP"


class DeliveryPoint(str, Enum):
    """Delivery points."""
    PUERTO = "Puesto en puerto"
    BODEGA = "Puesto en bodega"
    OBRA = "Puesto en obra"
    INSTALADO = "Instalado"


class Incoterm(str, Enum):
    """International trade terms."""
    EXW = "EXW"
    FCA = "FCA"
    FOB = "FOB"
    CFR = "CFR"
    CIF = "CIF"
    DDP = "DDP"
    NA = "NA"


@dataclass
class Client:
    """Client entity."""
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Client':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Project:
    """Project entity."""
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str = ""
    name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ScenarioVariables:
    """Scenario variables for energy and power."""
    p50_mwh_per_year: float = 0.0
    p90_mwh_per_year: float = 0.0
    ac_power_mw: float = 0.0  # Can be MW or kW, stored as MW
    dc_power_mwp: float = 0.0  # Stored in kWp (field name kept for backward compatibility)
    currency: str = "COP"
    fx_rate: float = 1.0  # Exchange rate if currency != COP
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScenarioVariables':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AIUConfig:
    """AIU (Administración, Imprevistos, Utilidad) configuration."""
    enabled: bool = False
    admin_pct: float = 0.0  # Administración percentage
    imprev_pct: float = 0.0  # Imprevistos percentage
    util_pct: float = 0.0  # Utilidad percentage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIUConfig':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class VATConfig:
    """VAT configuration."""
    vat_recoverable: bool = True  # IVA recuperable toggle
    vat_on_utilidad_enabled: bool = False  # IVA sobre Utilidad toggle
    vat_rate_utilidad: float = 19.0  # VAT rate for Utilidad
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VATConfig':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AIUFactors:
    """Per-item AIU scaling factors (0-100%)."""
    admin_factor: float = 100.0  # Percentage (0-100)
    imprev_factor: float = 100.0  # Percentage (0-100)
    util_factor: float = 100.0  # Percentage (0-100)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIUFactors':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ScenarioItem:
    """Item in a scenario."""
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    item_code: str = ""  # Must be unique (case-insensitive)
    name: str = ""
    category_code: str = ""  # References LibraryCategory.code
    description: str = ""
    qty: float = 0.0
    unit: str = "UND"
    pricing_mode: str = PricingMode.UNIT
    price: float = 0.0  # Unit price or price per kWp depending on mode
    vat_rate: float = 19.0
    price_includes_vat: bool = False  # Whether the price already includes VAT
    client_pays: bool = False  # "Paga cliente"
    aiu_factors: AIUFactors = field(default_factory=AIUFactors)
    # Commercial details
    incoterm: str = Incoterm.NA
    includes_installation: bool = False
    includes_transport: bool = False
    includes_commissioning: bool = False
    delivery_point: str = DeliveryPoint.OBRA
    notes: str = ""
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['aiu_factors'] = self.aiu_factors.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScenarioItem':
        """Create from dictionary."""
        aiu_factors_data = data.pop('aiu_factors', {})
        item = cls(**data)
        item.aiu_factors = AIUFactors.from_dict(aiu_factors_data) if aiu_factors_data else AIUFactors()
        return item


@dataclass
class Scenario:
    """Scenario entity."""
    scenario_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    variables: ScenarioVariables = field(default_factory=ScenarioVariables)
    aiu_config: AIUConfig = field(default_factory=AIUConfig)
    vat_config: VATConfig = field(default_factory=VATConfig)
    items: List[ScenarioItem] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['variables'] = self.variables.to_dict()
        data['aiu_config'] = self.aiu_config.to_dict()
        data['vat_config'] = self.vat_config.to_dict()
        data['items'] = [item.to_dict() for item in self.items]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Scenario':
        """Create from dictionary."""
        variables_data = data.pop('variables', {})
        aiu_config_data = data.pop('aiu_config', {})
        vat_config_data = data.pop('vat_config', {})
        items_data = data.pop('items', [])
        
        scenario = cls(**data)
        scenario.variables = ScenarioVariables.from_dict(variables_data) if variables_data else ScenarioVariables()
        scenario.aiu_config = AIUConfig.from_dict(aiu_config_data) if aiu_config_data else AIUConfig()
        scenario.vat_config = VATConfig.from_dict(vat_config_data) if vat_config_data else VATConfig()
        scenario.items = [ScenarioItem.from_dict(item_data) for item_data in items_data]
        return scenario


@dataclass
class LibraryCategory:
    """Library category."""
    category_code: str = ""  # Unique code (e.g., "PV-MOD")
    name_es: str = ""
    name_en: str = ""
    ordering: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LibraryCategory':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class LibraryItem:
    """Library item template."""
    item_code: str = ""  # Unique code (case-insensitive)
    name_es: str = ""
    name_en: str = ""
    description: str = ""
    default_unit: str = "UND"
    default_vat_rate: float = 19.0
    aiu_applicable: bool = True
    is_equipment: bool = False
    imported_default: bool = False  # True if from fixture file
    default_category_code: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LibraryItem':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class UploadMetadata:
    """File upload metadata."""
    upload_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = ""
    label: str = ""  # User-friendly label
    tags: List[str] = field(default_factory=list)
    upload_date: str = field(default_factory=lambda: datetime.now().isoformat())
    level: str = ""  # "project", "scenario", or "item"
    linked_item_ids: List[str] = field(default_factory=list)  # For item-level uploads
    supplier: Optional[str] = None
    incoterm: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UploadMetadata':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class User:
    """User account for application access control."""
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str = ""
    password_hash: str = ""  # bcrypt hash
    role: str = "client_viewer"  # e.g. 'delphi_admin' or 'client_viewer'
    client_id: Optional[str] = None  # if role == client_viewer, restrict to this client
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create User from dictionary (tolerant to missing keys)."""
        return cls(
            user_id=data.get("user_id", str(uuid.uuid4())),
            email=data.get("email", ""),
            password_hash=data.get("password_hash", ""),
            role=data.get("role", "client_viewer"),
            client_id=data.get("client_id"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )
