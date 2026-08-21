//! Disposable Tauri shell for the issue #43 Windows architecture spike.
//!
//! This crate deliberately exposes no Tauri commands or shell plugin. The
//! WebView is created only after the packaged sidecar has passed integrity
//! verification and completed its private bootstrap exchange.

mod integrity;

#[cfg(windows)]
mod runtime;
#[cfg(windows)]
mod windows_lifecycle;

use std::fmt;

#[cfg(windows)]
use std::{
    fs,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
};

#[cfg(windows)]
use tauri::{
    Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent, webview::NewWindowResponse,
};

#[cfg(windows)]
use crate::{
    integrity::verify_sidecar_integrity,
    runtime::RuntimeProcess,
    windows_lifecycle::{KillOnCloseJob, LifecycleError, SingleInstanceGuard},
};

#[cfg(windows)]
const INSTANCE_MUTEX_NAME: &str = "Local\\DeltaForce-Issue43-Architecture-Spike";
#[cfg(windows)]
const SIDECAR_DIRECTORY: &str = "sidecar";
#[cfg(windows)]
const SIDECAR_EXECUTABLE: &str = "crm-api-poc.exe";
#[cfg(windows)]
const DATA_DIRECTORY: &str = "issue-43-spike";
#[cfg(windows)]
const MAIN_WINDOW_LABEL: &str = "main";
#[cfg(windows)]
const LOCAL_WEBVIEW_ORIGIN: &str = "http://tauri.localhost";
#[cfg(windows)]
const STARTUP_FAILURE_EXIT_CODE: i32 = 1;

/// Sanitized launcher failure. No underlying OS, filesystem, or secret data is
/// retained because this value is the only startup error printed by `main`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StartupError;

impl fmt::Display for StartupError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("Delta Force architecture spike could not start")
    }
}

impl std::error::Error for StartupError {}

#[cfg(windows)]
struct RuntimeState(Mutex<Option<RuntimeProcess>>);

/// Start the synthetic desktop spike.
///
/// A second process is an expected no-op and therefore returns success. All
/// other failures are collapsed into [`StartupError`].
#[cfg(windows)]
pub fn run() -> Result<(), StartupError> {
    let _single_instance = match SingleInstanceGuard::acquire(INSTANCE_MUTEX_NAME) {
        Ok(guard) => guard,
        Err(LifecycleError::AlreadyRunning) => return Ok(()),
        Err(_) => return Err(StartupError),
    };

    let setup_failed = Arc::new(AtomicBool::new(false));
    let setup_failed_in_hook = Arc::clone(&setup_failed);

    let app = tauri::Builder::default()
        .setup(move |app| {
            if setup_windows(app).is_err() {
                setup_failed_in_hook.store(true, Ordering::Release);
                app.handle().exit(STARTUP_FAILURE_EXIT_CODE);
            }

            // Never propagate setup details into Tauri's panic message.
            Ok(())
        })
        .build(tauri::generate_context!())
        .map_err(|_| StartupError)?;

    let exit_code = app.run_return(handle_run_event);
    if setup_failed.load(Ordering::Acquire) || exit_code != 0 {
        Err(StartupError)
    } else {
        Ok(())
    }
}

#[cfg(windows)]
fn setup_windows(app: &mut tauri::App) -> Result<(), StartupError> {
    let sidecar_root = app
        .path()
        .resource_dir()
        .map_err(|_| StartupError)?
        .join(SIDECAR_DIRECTORY);

    // Verification must finish before the executable path is passed to the
    // process launcher. The integrity module also rejects extra/reparse files.
    verify_sidecar_integrity(&sidecar_root).map_err(|_| StartupError)?;
    let executable = sidecar_root.join(SIDECAR_EXECUTABLE);

    let data_directory = app
        .path()
        .app_local_data_dir()
        .map_err(|_| StartupError)?
        .join(DATA_DIRECTORY);
    fs::create_dir_all(&data_directory).map_err(|_| StartupError)?;

    let job = KillOnCloseJob::new().map_err(|_| StartupError)?;
    let runtime =
        RuntimeProcess::start(&executable, &data_directory, job).map_err(|_| StartupError)?;
    let initialization_script = runtime.initialization_script().map_err(|_| StartupError)?;

    // Keep the window hidden until its shutdown owner is registered. The
    // runtime bootstrap is already complete before this builder is created.
    let window =
        WebviewWindowBuilder::new(app, MAIN_WINDOW_LABEL, WebviewUrl::App("index.html".into()))
            .title("Delta Force CRM — Architecture Spike")
            .visible(false)
            .initialization_script(initialization_script)
            .on_navigation(|url| url.origin().ascii_serialization() == LOCAL_WEBVIEW_ORIGIN)
            .on_new_window(|_, _| NewWindowResponse::Deny)
            .build()
            .map_err(|_| StartupError)?;

    if !app.manage(RuntimeState(Mutex::new(Some(runtime)))) {
        return Err(StartupError);
    }

    let shutdown_handle = app.handle().clone();
    window.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            shutdown_runtime(&shutdown_handle);
            shutdown_handle.exit(0);
        }
    });

    window.show().map_err(|_| StartupError)
}

#[cfg(windows)]
fn handle_run_event(app: &tauri::AppHandle, event: RunEvent) {
    match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => shutdown_runtime(app),
        _ => {}
    }
}

#[cfg(windows)]
fn shutdown_runtime(app: &tauri::AppHandle) {
    let Some(state) = app.try_state::<RuntimeState>() else {
        return;
    };

    let runtime = {
        let mut guard = match state.0.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        guard.take()
    };

    if let Some(runtime) = runtime {
        // A failed graceful request is intentionally silent. RuntimeProcess
        // closes its Job Object and kills the child as a bounded fallback.
        let _ = runtime.shutdown();
    }
}

/// Keep accidental non-Windows builds compilable while refusing to start this
/// explicitly Windows-only architecture spike.
#[cfg(not(windows))]
pub fn run() -> Result<(), StartupError> {
    Err(StartupError)
}
