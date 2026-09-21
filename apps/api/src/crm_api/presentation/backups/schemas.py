from datetime import datetime

from pydantic import BaseModel, Field, SecretStr


class CreateBackupRequest(BaseModel):
    destination_directory: str = Field(min_length=1, max_length=32_767)
    passphrase: SecretStr = Field(min_length=12, max_length=1024)


class BackupCreationResponse(BaseModel):
    filename: str
    created_at: datetime
    byte_size: int
    document_count: int


class BackupStatusResponse(BaseModel):
    last_successful_at: datetime | None
    reminder_due: bool


class StageRestoreRequest(BaseModel):
    source_file: str = Field(min_length=1, max_length=32_767)
    passphrase: SecretStr = Field(min_length=12, max_length=1024)
    replace_existing: bool = False
    confirmation: str | None = Field(default=None, max_length=64)


class RestoreStagingResponse(BaseModel):
    backup_created_at: str
    document_count: int
    requires_restart: bool
