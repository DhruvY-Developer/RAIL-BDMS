"""
Rail-BDMS: Abstract Base Source Adapter
Provides uniform interface for all operational and maintenance data adapters.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

from backend.app.schemas.integration import IntegrationSourceStatus, ConnectionModeEnum

class BaseSourceAdapter(ABC):
    def __init__(self, source_id: str, source_name: str, department: str, description: str):
        self.source_id = source_id
        self.source_name = source_name
        self.department = department
        self.description = description
        self.connection_mode = ConnectionModeEnum.SIMULATED_PROTOTYPE
        self.last_sync = datetime.now(timezone.utc).isoformat()
        self.raw_records: List[Dict[str, Any]] = []
        self.normalized_records: List[Any] = []
        self.validation_issues: List[Dict[str, Any]] = []

    @abstractmethod
    def fetch_raw(self) -> List[Dict[str, Any]]:
        """
        Extracts or polls raw payload from source system or mock simulation endpoint.
        """
        pass

    @abstractmethod
    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[Any]:
        """
        Transforms raw source-specific schema into canonical Rail-BDMS model.
        """
        pass

    @abstractmethod
    def validate(self, normalized_records: List[Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        Validates completeness, business constraints, and data quality.
        Returns: (valid_records, validation_issues)
        """
        pass

    def sync(self) -> List[Any]:
        """
        Executes end-to-end extraction, normalization, and validation pipeline.
        """
        self.raw_records = self.fetch_raw()
        all_normalized = self.normalize(self.raw_records)
        valid_records, issues = self.validate(all_normalized)
        self.normalized_records = valid_records
        self.validation_issues = issues
        self.last_sync = datetime.now(timezone.utc).isoformat()
        return self.normalized_records

    def get_status(self) -> IntegrationSourceStatus:
        valid_count = len(self.normalized_records)
        issues_count = len(self.validation_issues)
        total_count = valid_count + issues_count
        
        return IntegrationSourceStatus(
            source_id=self.source_id,
            source_name=self.source_name,
            department=self.department,
            connection_mode=self.connection_mode,
            status="OPERATIONAL" if issues_count == 0 else "WARNING_ISSUES_DETECTED",
            total_records=total_count,
            valid_records=valid_count,
            needs_review_records=issues_count,
            last_sync=self.last_sync,
            data_freshness_seconds=0,
            description=self.description
        )
