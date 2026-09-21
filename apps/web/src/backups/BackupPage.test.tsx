import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BackupPage } from './BackupPage'
import { RestoreBackupPanel } from './RestoreBackupPanel'

describe('backup and restore interface', () => {
  afterEach(cleanup)

  it('warns when due and creates a protected backup after confirmation', async () => {
    const createBackup = vi.fn().mockResolvedValue({
      filename: 'delta-force-crm-synthetic.dfcrmbak',
      created_at: '2026-09-19T20:00:00Z',
      byte_size: 1234,
      document_count: 2,
    })
    const user = userEvent.setup()
    render(
      <BackupPage
        loadStatus={() =>
          Promise.resolve({ last_successful_at: null, reminder_due: true })
        }
        createBackup={createBackup}
        stageRestore={vi.fn()}
        onBack={() => undefined}
      />,
    )

    expect(
      await screen.findByText(/está na hora de criar um backup/i),
    ).toBeVisible()
    await user.type(
      screen.getByLabelText('Pasta no HD externo'),
      String.raw`E:\Backups`,
    )
    await user.type(
      screen.getByLabelText('Senha exclusiva do backup'),
      'senha sintetica forte',
    )
    await user.type(
      screen.getByLabelText('Confirmar senha do backup'),
      'senha sintetica forte',
    )
    await user.click(
      screen.getByRole('button', { name: 'Criar backup criptografado' }),
    )

    expect(createBackup).toHaveBeenCalledWith({
      destination_directory: String.raw`E:\Backups`,
      passphrase: 'senha sintetica forte',
    })
    expect(
      await screen.findByText(/backup concluído e verificado/i),
    ).toBeVisible()
  })

  it('stages a restore before account creation and never asks to overwrite data', async () => {
    const stageRestore = vi.fn().mockResolvedValue({
      backup_created_at: '2026-09-19T20:00:00Z',
      document_count: 2,
      requires_restart: true,
    })
    const onStaged = vi.fn()
    const user = userEvent.setup()
    render(
      <RestoreBackupPanel stageRestore={stageRestore} onStaged={onStaged} />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Restaurar pelo HD externo' }),
    )
    await user.type(
      screen.getByLabelText('Arquivo de backup'),
      String.raw`E:\Backups\synthetic.dfcrmbak`,
    )
    await user.type(
      screen.getByLabelText('Senha do backup'),
      'senha sintetica forte',
    )
    await user.click(
      screen.getByRole('button', { name: 'Validar e preparar restauração' }),
    )

    expect(stageRestore).toHaveBeenCalledWith({
      source_file: String.raw`E:\Backups\synthetic.dfcrmbak`,
      passphrase: 'senha sintetica forte',
      replace_existing: false,
      confirmation: null,
    })
    expect(onStaged).toHaveBeenCalledOnce()
    expect(screen.queryByText(/substituir dados/i)).not.toBeInTheDocument()
  })

  it('requires reinforced confirmation before replacing local data', async () => {
    const stageRestore = vi.fn().mockResolvedValue({
      backup_created_at: '2026-09-19T20:00:00Z',
      document_count: 2,
      requires_restart: true,
    })
    const user = userEvent.setup()
    render(
      <RestoreBackupPanel
        stageRestore={stageRestore}
        onStaged={() => undefined}
        replaceExisting
      />,
    )

    await user.click(
      screen.getByRole('button', { name: 'Restaurar pelo HD externo' }),
    )
    await user.type(
      screen.getByLabelText('Arquivo de backup'),
      String.raw`E:\Backups\synthetic.dfcrmbak`,
    )
    await user.type(
      screen.getByLabelText('Senha do backup'),
      'senha sintetica forte',
    )
    await user.type(
      screen.getByLabelText('Digite SUBSTITUIR DADOS'),
      'SUBSTITUIR DADOS',
    )
    await user.click(
      screen.getByRole('button', { name: 'Validar e preparar restauração' }),
    )

    expect(stageRestore).toHaveBeenCalledWith({
      source_file: String.raw`E:\Backups\synthetic.dfcrmbak`,
      passphrase: 'senha sintetica forte',
      replace_existing: true,
      confirmation: 'SUBSTITUIR DADOS',
    })
  })
})
