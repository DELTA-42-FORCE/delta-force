use std::{
    fs,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{mpsc, Mutex},
    time::{Duration, Instant},
};

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, State, WindowEvent};
use thiserror::Error;
use zeroize::Zeroizing;

const PRODUCTION_ORIGIN: &str = "http://tauri.localhost";
const DEVELOPMENT_ORIGIN: &str = "http://127.0.0.1:5173";
const SIDECAR_READY_TIMEOUT: Duration = Duration::from_secs(10);
const SIDECAR_GRACEFUL_STOP_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Error)]
enum DesktopError {
    #[error("desktop sidecar could not start")]
    SidecarStart,
    #[error("desktop sidecar did not become ready")]
    SidecarNotReady,
    #[error("desktop bootstrap was denied")]
    BootstrapDenied,
    #[error("desktop resources could not be resolved")]
    ResourcesUnavailable,
    #[error("desktop document could not be opened")]
    DocumentOpenFailed,
}

#[derive(Debug, Deserialize)]
struct SidecarReady {
    event: String,
    port: u16,
}

#[derive(Debug, Deserialize)]
struct BootstrapResponse {
    capability: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopConnection {
    api_base_url: String,
    capability: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct OpenDocumentRequest {
    client_id: String,
    document_id: String,
    filename: String,
    session_token: String,
}

const OPEN_CACHE_DIRECTORY: &str = "open-cache";
const ALLOWED_OPEN_EXTENSIONS: [&str; 3] = ["pdf", "jpg", "jpeg"];

struct SidecarProcess {
    child: Mutex<Option<Child>>,
    stdin: Mutex<Option<ChildStdin>>,
    #[cfg(windows)]
    _job: WindowsProcessJob,
}

#[derive(Debug, PartialEq, Eq)]
enum SidecarStop {
    Graceful,
    Forced,
    AlreadyStopped,
}

impl SidecarProcess {
    fn stop(&self) -> SidecarStop {
        // O sidecar observa EOF no stdin depois do bootstrap. Soltar o pipe
        // pede que o Uvicorn encerre após concluir as requisições em curso.
        if let Ok(mut stdin) = self.stdin.lock() {
            stdin.take();
        }

        let Some(mut process) = self.child.lock().ok().and_then(|mut child| child.take()) else {
            return SidecarStop::AlreadyStopped;
        };

        if wait_for_child_exit(&mut process, SIDECAR_GRACEFUL_STOP_TIMEOUT) {
            SidecarStop::Graceful
        } else {
            terminate_child(&mut process);
            SidecarStop::Forced
        }
    }
}

fn wait_for_child_exit(child: &mut Child, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return true,
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(25)),
            Ok(None) | Err(_) => return false,
        }
    }
}

fn terminate_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

impl Drop for SidecarProcess {
    fn drop(&mut self) {
        self.stop();
    }
}

struct DesktopRuntime {
    connection: DesktopConnection,
    connection_delivered: Mutex<bool>,
    open_cache_directory: PathBuf,
    sidecar: SidecarProcess,
}

impl DesktopRuntime {
    fn start(app: &AppHandle) -> Result<Self, DesktopError> {
        let origin = desktop_origin();
        let data_directory = app
            .path()
            .app_local_data_dir()
            .map_err(|_| DesktopError::ResourcesUnavailable)?;
        let open_cache_directory = prepare_open_cache_directory(&data_directory)?;
        let sidecar_path = sidecar_path(app)?;
        let secret = Zeroizing::new(generate_secret()?);

        let mut child = Command::new(sidecar_path)
            .env("DELTA_FORCE_DATA_DIR", data_directory)
            .env("DELTA_FORCE_DESKTOP_ORIGIN", origin)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| DesktopError::SidecarStart)?;

        #[cfg(windows)]
        let job = match WindowsProcessJob::attach(&child) {
            Ok(job) => job,
            Err(error) => {
                // `Child` não encerra o processo ao ser descartado. Se o Job
                // Object não puder protegê-lo, a inicialização falha fechando
                // explicitamente o sidecar já criado.
                terminate_child(&mut child);
                return Err(error);
            }
        };

        let startup_result = (|| {
            let mut stdin = child.stdin.take().ok_or(DesktopError::SidecarStart)?;
            stdin
                .write_all(secret.as_bytes())
                .and_then(|()| stdin.write_all(b"\n"))
                .and_then(|()| stdin.flush())
                .map_err(|_| DesktopError::SidecarStart)?;

            let stdout = child.stdout.take().ok_or(DesktopError::SidecarStart)?;
            let ready = read_ready(stdout)?;
            if ready.event != "ready" || ready.port == 0 {
                return Err(DesktopError::SidecarNotReady);
            }
            let capability = bootstrap_capability(ready.port, origin, secret.as_str())?;
            Ok((ready.port, capability, stdin))
        })();

        let (port, capability, stdin) = match startup_result {
            Ok(result) => result,
            Err(error) => {
                terminate_child(&mut child);
                return Err(error);
            }
        };

        Ok(Self {
            connection: DesktopConnection {
                api_base_url: format!("http://127.0.0.1:{port}"),
                capability,
            },
            connection_delivered: Mutex::new(false),
            open_cache_directory,
            sidecar: SidecarProcess {
                child: Mutex::new(Some(child)),
                stdin: Mutex::new(Some(stdin)),
                #[cfg(windows)]
                _job: job,
            },
        })
    }

    fn take_connection(&self) -> Result<DesktopConnection, DesktopError> {
        let mut delivered = self
            .connection_delivered
            .lock()
            .map_err(|_| DesktopError::BootstrapDenied)?;
        if *delivered {
            return Err(DesktopError::BootstrapDenied);
        }
        *delivered = true;
        Ok(self.connection.clone())
    }
}

fn prepare_open_cache_directory(data_directory: &Path) -> Result<PathBuf, DesktopError> {
    let cache_root = data_directory.join(OPEN_CACHE_DIRECTORY);
    // Cada execução começa com uma área nova. Arquivos de consultas encerradas
    // ou de uma execução interrompida são removidos na próxima abertura, sem
    // tocar no armazenamento privado dos documentos do CRM.
    if cache_root.exists() {
        fs::remove_dir_all(&cache_root).map_err(|_| DesktopError::DocumentOpenFailed)?;
    }
    fs::create_dir_all(&cache_root).map_err(|_| DesktopError::DocumentOpenFailed)?;

    let mut nonce = [0_u8; 16];
    getrandom::fill(&mut nonce).map_err(|_| DesktopError::DocumentOpenFailed)?;
    let run_directory = cache_root.join(URL_SAFE_NO_PAD.encode(nonce));
    fs::create_dir(&run_directory).map_err(|_| DesktopError::DocumentOpenFailed)?;
    Ok(run_directory)
}

fn desktop_origin() -> &'static str {
    if cfg!(debug_assertions) {
        DEVELOPMENT_ORIGIN
    } else {
        PRODUCTION_ORIGIN
    }
}

fn sidecar_path(app: &AppHandle) -> Result<PathBuf, DesktopError> {
    let resource_directory = app
        .path()
        .resource_dir()
        .map_err(|_| DesktopError::ResourcesUnavailable)?;
    let executable = if cfg!(windows) {
        "delta-force-api.exe"
    } else {
        "delta-force-api"
    };
    Ok(resource_directory
        .join("api-sidecar")
        .join("delta-force-api")
        .join(executable))
}

fn generate_secret() -> Result<String, DesktopError> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes).map_err(|_| DesktopError::SidecarStart)?;
    Ok(URL_SAFE_NO_PAD.encode(bytes))
}

fn read_ready(stdout: impl std::io::Read + Send + 'static) -> Result<SidecarReady, DesktopError> {
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut line = String::new();
        let result = BufReader::new(stdout)
            .read_line(&mut line)
            .map_err(|_| DesktopError::SidecarNotReady)
            .and_then(|_| serde_json::from_str(&line).map_err(|_| DesktopError::SidecarNotReady));
        let _ = sender.send(result);
    });
    receiver
        .recv_timeout(SIDECAR_READY_TIMEOUT)
        .map_err(|_| DesktopError::SidecarNotReady)?
}

fn bootstrap_capability(port: u16, origin: &str, secret: &str) -> Result<String, DesktopError> {
    let endpoint = format!("http://127.0.0.1:{port}/_desktop/bootstrap");
    let response = reqwest::blocking::Client::builder()
        .no_proxy()
        .build()
        .map_err(|_| DesktopError::BootstrapDenied)?
        .post(endpoint)
        .header("Origin", origin)
        .header("X-Delta-Desktop-Secret", secret)
        .send()
        .map_err(|_| DesktopError::BootstrapDenied)?;
    if !response.status().is_success() {
        return Err(DesktopError::BootstrapDenied);
    }
    let payload: BootstrapResponse = response.json().map_err(|_| DesktopError::BootstrapDenied)?;
    if payload.capability.is_empty() || !payload.capability.is_ascii() {
        return Err(DesktopError::BootstrapDenied);
    }
    Ok(payload.capability)
}

#[tauri::command]
fn desktop_connection(state: State<'_, DesktopRuntime>) -> Result<DesktopConnection, String> {
    state
        .take_connection()
        .map_err(|_| "desktop connection is unavailable".to_owned())
}

#[tauri::command]
fn open_document(
    state: State<'_, DesktopRuntime>,
    request: OpenDocumentRequest,
) -> Result<(), String> {
    open_remote_document(&state, request).map_err(|_| "the document could not be opened".to_owned())
}

fn open_remote_document(
    runtime: &DesktopRuntime,
    request: OpenDocumentRequest,
) -> Result<(), DesktopError> {
    // Não transportamos o arquivo pelo WebView: Base64/Blob duplicariam o uso
    // de memória e inviabilizariam documentos grandes. A sessão só é recebida
    // nesta chamada IPC, não é persistida nem registrada em logs; o shell a
    // usa para buscar a cópia autorizada e gravá-la por streaming.
    let OpenDocumentRequest {
        client_id,
        document_id,
        filename,
        session_token,
    } = request;
    let client_id = safe_identifier(&client_id)?;
    let document_id = safe_identifier(&document_id)?;
    let filename = safe_open_filename(&filename)?;
    let session_token = Zeroizing::new(session_token);
    if session_token.is_empty() || !session_token.is_ascii() {
        return Err(DesktopError::DocumentOpenFailed);
    }

    let endpoint = format!(
        "{}/clients/{client_id}/documents/{document_id}/content",
        runtime.connection.api_base_url
    );
    let mut response = reqwest::blocking::Client::builder()
        .no_proxy()
        .build()
        .map_err(|_| DesktopError::DocumentOpenFailed)?
        .get(endpoint)
        .header("Origin", desktop_origin())
        .header("X-Delta-Desktop-Capability", &runtime.connection.capability)
        .bearer_auth(session_token.as_str())
        .send()
        .map_err(|_| DesktopError::DocumentOpenFailed)?;
    if !response.status().is_success() {
        return Err(DesktopError::DocumentOpenFailed);
    }

    let destination = unique_open_destination(&runtime.open_cache_directory, &filename)?;
    let temporary = destination.with_extension("partial");
    let mut output = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)
        .map_err(|_| DesktopError::DocumentOpenFailed)?;
    if std::io::copy(&mut response, &mut output).is_err() || output.flush().is_err() {
        let _ = fs::remove_file(&temporary);
        return Err(DesktopError::DocumentOpenFailed);
    }
    drop(output);
    if fs::rename(&temporary, &destination).is_err() {
        let _ = fs::remove_file(&temporary);
        return Err(DesktopError::DocumentOpenFailed);
    }
    launch_with_default_application(&destination)
}

fn safe_identifier(identifier: &str) -> Result<&str, DesktopError> {
    if identifier.len() != 36
        || !identifier
            .bytes()
            .enumerate()
            .all(|(index, byte)| match index {
                8 | 13 | 18 | 23 => byte == b'-',
                _ => byte.is_ascii_hexdigit(),
            })
    {
        return Err(DesktopError::DocumentOpenFailed);
    }
    Ok(identifier)
}

fn unique_open_destination(
    cache_directory: &Path,
    filename: &str,
) -> Result<PathBuf, DesktopError> {
    let mut nonce = [0_u8; 16];
    getrandom::fill(&mut nonce).map_err(|_| DesktopError::DocumentOpenFailed)?;
    Ok(cache_directory.join(format!("{}-{filename}", URL_SAFE_NO_PAD.encode(nonce))))
}

fn safe_open_filename(filename: &str) -> Result<String, DesktopError> {
    // Só o nome do arquivo é aceito: qualquer componente de diretório é
    // descartado para que a cópia nunca escape do cache de abertura, e apenas
    // os formatos previstos pela #22 podem ser gravados.
    let name = Path::new(filename)
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or(DesktopError::DocumentOpenFailed)?;
    let extension = Path::new(name)
        .extension()
        .and_then(|value| value.to_str())
        .map(str::to_ascii_lowercase)
        .unwrap_or_default();
    if !ALLOWED_OPEN_EXTENSIONS.contains(&extension.as_str()) {
        return Err(DesktopError::DocumentOpenFailed);
    }
    Ok(name.to_owned())
}

#[cfg(windows)]
fn launch_with_default_application(path: &Path) -> Result<(), DesktopError> {
    // `rundll32 ShellExec_RunDLL` abre o arquivo no programa associado do
    // Windows sem passar por um shell que reinterprete o caminho.
    Command::new("rundll32.exe")
        .arg("shell32.dll,ShellExec_RunDLL")
        .arg(path)
        .spawn()
        .map(|_| ())
        .map_err(|_| DesktopError::DocumentOpenFailed)
}

#[cfg(not(windows))]
fn launch_with_default_application(path: &Path) -> Result<(), DesktopError> {
    Command::new("xdg-open")
        .arg(path)
        .spawn()
        .map(|_| ())
        .map_err(|_| DesktopError::DocumentOpenFailed)
}

#[cfg(test)]
mod document_open_tests {
    use super::{safe_identifier, unique_open_destination};
    use std::path::Path;

    #[test]
    fn only_accepts_canonical_identifiers_for_the_local_api_path() {
        assert!(safe_identifier("00000000-0000-0000-0000-000000000001").is_ok());
        assert!(safe_identifier("../../documents").is_err());
        assert!(safe_identifier("000000000000-0000-0000-000000000001").is_err());
    }

    #[test]
    fn creates_distinct_cache_paths_for_documents_with_the_same_name() {
        let cache = Path::new("C:/synthetic-open-cache");
        let first = unique_open_destination(cache, "RG.pdf").expect("random path");
        let second = unique_open_destination(cache, "RG.pdf").expect("random path");

        assert_ne!(first, second);
        assert_eq!(first.parent(), Some(cache));
        assert_eq!(second.parent(), Some(cache));
        assert!(first
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name.ends_with("-RG.pdf")));
    }
}

pub fn run() {
    let mut builder = tauri::Builder::default();
    #[cfg(windows)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(
            |app, _arguments, _working_directory| {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            },
        ));
    }
    builder
        .setup(|app| {
            let runtime =
                DesktopRuntime::start(app.handle()).map_err(|_| DesktopError::SidecarStart)?;
            app.manage(runtime);
            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let _ = window.state::<DesktopRuntime>().sidecar.stop();
            }
        })
        .invoke_handler(tauri::generate_handler![desktop_connection, open_document])
        .run(tauri::generate_context!())
        .expect("failed to run Delta Force CRM desktop shell");
}

#[cfg(windows)]
struct WindowsProcessJob(std::os::windows::io::OwnedHandle);

#[cfg(windows)]
impl WindowsProcessJob {
    fn attach(child: &Child) -> Result<Self, DesktopError> {
        use std::{
            mem::zeroed,
            os::windows::io::{AsRawHandle, FromRawHandle},
        };
        use windows_sys::Win32::{
            Foundation::HANDLE,
            System::JobObjects::{
                AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
                SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
            },
        };

        let job = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
        if job.is_null() {
            return Err(DesktopError::SidecarStart);
        }
        let mut information: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { zeroed() };
        information.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let configured = unsafe {
            SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                &information as *const _ as *const std::ffi::c_void,
                std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        };
        let assigned = unsafe { AssignProcessToJobObject(job, child.as_raw_handle() as HANDLE) };
        if configured == 0 || assigned == 0 {
            unsafe { windows_sys::Win32::Foundation::CloseHandle(job) };
            return Err(DesktopError::SidecarStart);
        }
        let owned = unsafe { std::os::windows::io::OwnedHandle::from_raw_handle(job as _) };
        Ok(Self(owned))
    }
}

#[cfg(all(test, windows))]
mod windows_lifecycle_tests {
    use std::{
        process::{Command, Stdio},
        thread,
        time::Duration,
    };

    use super::{SidecarProcess, SidecarStop, WindowsProcessJob};

    fn long_running_child() -> std::process::Child {
        Command::new("cmd")
            .args(["/C", "ping -n 30 127.0.0.1 > NUL"])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("the Windows test child should start")
    }

    fn stdin_bound_child() -> std::process::Child {
        Command::new("cmd")
            .args(["/C", "more > NUL"])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("the Windows test child should start")
    }

    #[test]
    fn normal_shutdown_reaps_the_sidecar() {
        let mut child = stdin_bound_child();
        let job = WindowsProcessJob::attach(&child).expect("job assignment should work");
        let stdin = child
            .stdin
            .take()
            .expect("normal child stdin should be piped");
        let process = SidecarProcess {
            child: std::sync::Mutex::new(Some(child)),
            stdin: std::sync::Mutex::new(Some(stdin)),
            _job: job,
        };

        assert_eq!(process.stop(), SidecarStop::Graceful);

        assert!(process
            .child
            .lock()
            .expect("test mutex should not be poisoned")
            .is_none());
    }

    #[test]
    fn shutdown_falls_back_to_kill_when_the_sidecar_does_not_exit() {
        let mut child = long_running_child();
        let job = WindowsProcessJob::attach(&child).expect("job assignment should work");
        let stdin = child
            .stdin
            .take()
            .expect("fallback child stdin should be piped");
        let process = SidecarProcess {
            child: std::sync::Mutex::new(Some(child)),
            stdin: std::sync::Mutex::new(Some(stdin)),
            _job: job,
        };

        assert_eq!(process.stop(), SidecarStop::Forced);
        assert!(process
            .child
            .lock()
            .expect("test mutex should not be poisoned")
            .is_none());
    }

    #[test]
    fn job_object_reaps_the_sidecar_after_forced_shell_termination() {
        let mut child = long_running_child();
        let job = WindowsProcessJob::attach(&child).expect("job assignment should work");

        drop(job);

        for _ in 0..20 {
            if child
                .try_wait()
                .expect("child status should be readable")
                .is_some()
            {
                return;
            }
            thread::sleep(Duration::from_millis(100));
        }
        let _ = child.kill();
        let _ = child.wait();
        panic!("dropping the Job Object must terminate the sidecar");
    }
}
