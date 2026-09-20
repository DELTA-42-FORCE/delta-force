"""Erros de domínio e aplicação do fluxo de contratos."""


class ContractNotFoundError(Exception):
    """O contrato não existe para o cliente informado."""


class InstallmentNotFoundError(Exception):
    """A parcela não pertence ao contrato informado."""


class InstallmentAlreadyPaidError(Exception):
    """A parcela já possui pagamento registrado."""


class ContractNotActiveError(Exception):
    """A alteração não é permitida fora do estado ativo."""
