"""Exclusão durante restauração inclui streams e limpeza das sessões HTTP."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from crm_api.application.backups.workflow import DesktopBackupWorkflow


class BackupOperationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        workflow = (
            getattr(scope.get("app").state, "backup_workflow", None)
            if scope.get("app")
            else None
        )
        if scope["type"] != "http" or not isinstance(workflow, DesktopBackupWorkflow):
            await self.app(scope, receive, send)
            return
        async with workflow.lock:
            if workflow.recovery_required:
                await JSONResponse(
                    {"detail": "backup_restart_required"}, status_code=503
                )(scope, receive, send)
                return
            if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and not scope[
                "path"
            ].startswith("/backups"):
                workflow.invalidate_previews()
            await self.app(scope, receive, send)
