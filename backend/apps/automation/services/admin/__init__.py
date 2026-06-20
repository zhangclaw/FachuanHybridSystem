"""
Automation Admin Services
提供Admin层的复杂业务逻辑服务
"""

from .court_document_admin_service import CourtDocumentAdminService
from .token_acquisition_history_admin_service import TokenAcquisitionHistoryAdminService

# PreservationQuoteAdminService 已迁移到 plugin
try:
    from plugins.court_automation.preservation_quote.admin_service import PreservationQuoteAdminService
except ImportError:
    pass

__all__ = [
    "TokenAcquisitionHistoryAdminService",
    "CourtDocumentAdminService",
    "PreservationQuoteAdminService",
]
