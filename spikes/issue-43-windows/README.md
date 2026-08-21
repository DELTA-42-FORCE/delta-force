# Spike arquitetural Windows da issue #43

Este diretório contém um protótipo **descartável**, **não distribuível** e feito
somente com dados sintéticos. Ele existe para produzir as evidências técnicas
necessárias à decisão da ADR 0002; não é uma implementação do CRM.

## Limites

- não usar dados, documentos, credenciais ou segredos reais;
- não alterar dependências nem lockfiles em `apps/` ou na raiz do repositório;
- não implementar cadastro, documentos, e-mail, backup, instalador final,
  atualização automática ou assinatura real;
- não substituir silenciosamente Tauri, PyInstaller `onedir`, SQLite, loopback
  dinâmico ou Job Object por outra arquitetura;
- parar e registrar a falha se um critério de segurança não puder ser provado.

## Provas deste spike

1. Abrir o build React existente em uma janela Tauri 2 sem shell arbitrário na
   WebView.
2. Iniciar pelo núcleo Rust uma API FastAPI sintética empacotada pelo PyInstaller
   em modo `onedir`.
3. Reservar `127.0.0.1:0` no próprio sidecar, publicar somente dados técnicos da
   porta pelo pipe e comprovar que não há listener externo.
4. Trocar um segredo aleatório de uso único, recebido por `stdin`, por uma
   capability efêmera e rejeitar Host, Origin, bootstrap ou capability inválidos.
5. Encerrar o sidecar no fechamento normal e no hard-kill do shell com Windows
   Job Object `KILL_ON_JOB_CLOSE`.
6. Validar SQLite fora dos binários com journaling, `synchronous=FULL`, foreign
   keys, reabertura, rollback e `integrity_check`.
7. Rejeitar alteração do manifesto ou da árvore `onedir` usando somente chave e
   artefatos sintéticos.
8. Gerar um resumo sanitizado de versões, processos, listener, hashes e
   resultados, sem segredo, capability ou dado real.

## Isolamento

- `api-poc/`: runtime e testes Python, com `pyproject.toml` e `uv.lock` próprios.
- `desktop/`: shell Tauri/Rust, com manifestos e lockfiles próprios.
- `scripts/`: automação PowerShell do build e das verificações.
- `evidence/`: somente o relatório sanitizado e revisável; saídas brutas ficam
  ignoradas.
- `build/`: artefatos gerados localmente e nunca versionados.

O notebook atual é apenas uma máquina de referência. A instalação limpa,
NSIS/WebView2 offline, assinatura, atualização, desinstalação e aceite no
notebook definitivo pertencem às issues posteriores documentadas na ADR.

## Pré-requisitos locais

- Windows 11 Pro x64;
- Node.js 22 e npm;
- Python 3.12 gerenciado isoladamente por `uv`;
- Rust estável com target `x86_64-pc-windows-msvc`;
- Microsoft C++ Build Tools com **Desktop development with C++**;
- Microsoft Edge WebView2 Runtime.

## Comandos reproduzíveis

Na raiz do repositório, a fatia Python/PyInstaller pode ser reconstruída e
verificada com:

```powershell
.\spikes\issue-43-windows\scripts\build_api_poc.ps1
```

O script usa somente o ambiente e os locks sob `spikes/`, testa o executável
empacotado e prepara `build/sidecar/` com manifesto e assinatura sintéticos.
Depois de instalar o Microsoft C++ Build Tools, validar o núcleo Rust com:

```powershell
.\spikes\issue-43-windows\scripts\build_desktop_poc.ps1
```

Esse segundo script recompila as provas, constrói o React/Tauri e abre duas
janelas sintéticas em sequência para verificar fechamento gracioso, instância
única e hard-kill. A verificação exige que o marcador acessível do React esteja
visível e termina imprimindo um digest determinístico dos fontes testados. Ele
encerra somente os processos que criou.

O resultado sanitizado da execução de referência está em
`evidence/first-spike-report.md`; binários e saídas brutas continuam ignorados.

Este primeiro spike prova o lifecycle do sidecar sintético cooperativo e a
recusa estática de adulteração. DACL e eliminação de TOCTOU por handles são
provas posteriores da #21; o protótipo não deve ser tratado como fronteira de
confiança pronta para produção.

## Retomada por outro Codex

Em outra tarefa ou computador, use a mesma branch publicada e comece pela raiz
do repositório:

```powershell
Get-Content .\AGENTS.md
git switch chore/43-windows-spike
git status --short --branch
Get-Content .\docs\adr\0002-aplicativo-local-windows.md
Get-Content .\spikes\issue-43-windows\evidence\first-spike-report.md
.\spikes\issue-43-windows\scripts\build_desktop_poc.ps1
```

Arquivos gerados em `build/`, `.venv/`, `node_modules/`, `target/` e `gen/` são
locais e devem continuar ignorados. Preserve qualquer alteração alheia existente
no checkout. O PR documental é o #48 e a ADR permanece **Proposta**: pedir
autorização explícita antes de stage, commit, push, criação de issue, aceite da
ADR ou merge. Depois de um gate verde, o próximo passo é revisar o escopo
versionável e preparar a branch de evidências para revisão.
