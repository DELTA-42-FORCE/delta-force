from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BackupCreationResult:
    filename: str
    created_at: datetime
    byte_size: int
    document_count: int


@dataclass(frozen=True, slots=True)
class RestoreStagingResult:
    created_at: str
    document_count: int
    requires_restart: bool = True
