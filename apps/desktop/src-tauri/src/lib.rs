use std::{
    io::{BufRead, BufReader, Write},
    path::PathBuf,
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

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopConnection {
    api_base_url: String,
    capability: String,
}

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
    connection: Mutex<Option<DesktopConnection>>,
    sidecar: SidecarProcess,
}

impl DesktopRuntime {
    fn start(app: &AppHandle) -> Result<Self, DesktopError> {
        let origin = desktop_origin();
        let data_directory = app
            .path()
            .app_local_data_dir()
            .map_err(|_| DesktopError::ResourcesUnavailable)?;
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
            connection: Mutex::new(Some(DesktopConnection {
                api_base_url: format!("http://127.0.0.1:{port}"),
                capability,
            })),
            sidecar: SidecarProcess {
                child: Mutex::new(Some(child)),
                stdin: Mutex::new(Some(stdin)),
                #[cfg(windows)]
                _job: job,
            },
        })
    }

    fn take_connection(&self) -> Result<DesktopConnection, DesktopError> {
        self.connection
            .lock()
            .map_err(|_| DesktopError::BootstrapDenied)?
            .take()
            .ok_or(DesktopError::BootstrapDenied)
    }
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
        .invoke_handler(tauri::generate_handler![desktop_connection])
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
