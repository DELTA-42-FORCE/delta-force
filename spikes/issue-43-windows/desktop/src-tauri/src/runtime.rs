//! Narrow runtime bridge for the disposable Windows architecture spike.
//!
//! The bootstrap secret never leaves anonymous pipes and process memory. The
//! WebView receives only the per-execution capability after the sidecar has
//! been assigned to a kill-on-close Job Object.

use std::fmt;
use std::io::{ErrorKind, Read, Write};
use std::path::Path;
use std::process::{Child, ChildStdout, Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

use base64::Engine as _;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use reqwest::blocking::Client;
use reqwest::redirect::Policy;
use serde::Deserialize;
use zeroize::Zeroizing;

use crate::windows_lifecycle::KillOnCloseJob;

const LOOPBACK_HOST: &str = "127.0.0.1";
const TAURI_ORIGIN: &str = "http://tauri.localhost";
const BOOTSTRAP_PATH: &str = "/runtime/bootstrap";
const SHUTDOWN_PATH: &str = "/runtime/shutdown";
const BOOTSTRAP_HEADER: &str = "x-runtime-bootstrap";
const CAPABILITY_HEADER: &str = "x-runtime-capability";
const GLOBAL_NAME: &str = "__DELTA_FORCE_RUNTIME__";
const SECRET_BYTES: usize = 32;
const MAX_READY_LINE_BYTES: usize = 512;
const MAX_BOOTSTRAP_BODY_BYTES: u64 = 1024;
const MAX_CAPABILITY_BYTES: usize = 256;
const READY_TIMEOUT: Duration = Duration::from_secs(5);
const HTTP_CONNECT_TIMEOUT: Duration = Duration::from_secs(1);
const HTTP_REQUEST_TIMEOUT: Duration = Duration::from_secs(3);
const GRACEFUL_SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(3);
const FALLBACK_WAIT_TIMEOUT: Duration = Duration::from_millis(500);
const WAIT_POLL_INTERVAL: Duration = Duration::from_millis(20);

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Sanitized runtime failure. It deliberately carries no path or credential.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RuntimeError {
    stage: &'static str,
}

impl RuntimeError {
    const fn at(stage: &'static str) -> Self {
        Self { stage }
    }
}

impl fmt::Display for RuntimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "runtime failure at {}", self.stage)
    }
}

impl std::error::Error for RuntimeError {}

/// A narrow wrapper that prevents accidental formatting and zeroizes the
/// owned allocation on every return path.
struct MemorySecret(Zeroizing<Vec<u8>>);

impl MemorySecret {
    fn empty() -> Self {
        Self(Zeroizing::new(Vec::new()))
    }

    fn from_bytes(bytes: Vec<u8>) -> Self {
        Self(Zeroizing::new(bytes))
    }

    fn expose(&self) -> &[u8] {
        &self.0
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ReadyMessage {
    event: String,
    host: String,
    pid: u32,
    port: u16,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct BootstrapResponse {
    capability: Zeroizing<String>,
}

/// Running sidecar plus its fail-closed lifecycle guard.
pub struct RuntimeProcess {
    child: Child,
    job: Option<KillOnCloseJob>,
    client: Client,
    endpoint: String,
    capability: MemorySecret,
}

impl RuntimeProcess {
    /// Start the verified sidecar and complete the one-shot bootstrap exchange.
    pub fn start(
        executable: &Path,
        data_dir: &Path,
        job: KillOnCloseJob,
    ) -> Result<Self, RuntimeError> {
        let client = build_http_client()?;
        let mut command = Command::new(executable);
        command
            .arg("--data-dir")
            .arg(data_dir)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;

            command.creation_flags(CREATE_NO_WINDOW);
        }

        let mut child = command
            .spawn()
            .map_err(|_| RuntimeError::at("sidecar spawn"))?;
        let child_id = child.id();

        // The child blocks on stdin, so it cannot bind or serve before the Job
        // owns it. If assignment fails, it is not protected by the Job yet and
        // must be terminated directly.
        if job.assign_process(child_id).is_err() {
            terminate_unassigned_child(&mut child);
            return Err(RuntimeError::at("job assignment"));
        }

        let mut runtime = Self {
            child,
            job: Some(job),
            client,
            endpoint: String::new(),
            capability: MemorySecret::empty(),
        };

        let bootstrap_secret = generate_bootstrap_secret()?;
        runtime.send_bootstrap_secret(&bootstrap_secret)?;

        let stdout = runtime
            .child
            .stdout
            .take()
            .ok_or_else(|| RuntimeError::at("readiness pipe acquisition"))?;
        let ready = read_readiness_with_timeout(stdout, child_id)?;
        runtime.endpoint = format!("http://{LOOPBACK_HOST}:{}", ready.port);
        runtime.capability = runtime.exchange_bootstrap(&bootstrap_secret)?;

        Ok(runtime)
    }

    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }

    /// Build the only WebView-visible runtime state. The bootstrap secret is
    /// never interpolated, and the global/value are immutable and hidden from
    /// enumeration.
    pub fn initialization_script(&self) -> Result<String, RuntimeError> {
        build_initialization_script(&self.endpoint, self.capability.expose())
    }

    /// Ask the sidecar to stop, then close the Job as a bounded fallback.
    pub fn shutdown(mut self) -> Result<(), RuntimeError> {
        let graceful_result = self.request_graceful_shutdown();
        if graceful_result.is_err() {
            self.fail_closed();
            return graceful_result;
        }

        match wait_for_child(&mut self.child, GRACEFUL_SHUTDOWN_TIMEOUT)? {
            Some(status) if status.success() => {
                self.job.take();
                Ok(())
            }
            Some(_) => {
                self.fail_closed();
                Err(RuntimeError::at("graceful shutdown exit status"))
            }
            None => {
                self.fail_closed();
                let _ = wait_for_child(&mut self.child, FALLBACK_WAIT_TIMEOUT);
                Err(RuntimeError::at("graceful shutdown timeout"))
            }
        }
    }

    fn send_bootstrap_secret(&mut self, secret: &MemorySecret) -> Result<(), RuntimeError> {
        let mut stdin = self
            .child
            .stdin
            .take()
            .ok_or_else(|| RuntimeError::at("bootstrap pipe acquisition"))?;
        stdin
            .write_all(secret.expose())
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|_| RuntimeError::at("bootstrap pipe write"))?;
        drop(stdin);
        Ok(())
    }

    fn exchange_bootstrap(
        &self,
        bootstrap_secret: &MemorySecret,
    ) -> Result<MemorySecret, RuntimeError> {
        let bootstrap_header = reqwest::header::HeaderValue::from_bytes(bootstrap_secret.expose())
            .map_err(|_| RuntimeError::at("bootstrap header construction"))?;
        let response = self
            .client
            .post(format!("{}{}", self.endpoint, BOOTSTRAP_PATH))
            .header("Origin", TAURI_ORIGIN)
            .header(BOOTSTRAP_HEADER, bootstrap_header)
            .send()
            .map_err(|_| RuntimeError::at("bootstrap request"))?;

        if response.status() != reqwest::StatusCode::OK {
            return Err(RuntimeError::at("bootstrap response status"));
        }

        let body = Zeroizing::new(read_bounded_response(response, "bootstrap response body")?);
        let parsed: BootstrapResponse = serde_json::from_slice(&body)
            .map_err(|_| RuntimeError::at("bootstrap response JSON"))?;
        validate_capability(parsed.capability.as_str())
    }

    fn request_graceful_shutdown(&self) -> Result<(), RuntimeError> {
        let capability_header = reqwest::header::HeaderValue::from_bytes(self.capability.expose())
            .map_err(|_| RuntimeError::at("shutdown header construction"))?;
        let response = self
            .client
            .post(format!("{}{}", self.endpoint, SHUTDOWN_PATH))
            .header("Origin", TAURI_ORIGIN)
            .header(CAPABILITY_HEADER, capability_header)
            .send()
            .map_err(|_| RuntimeError::at("shutdown request"))?;

        if response.status() != reqwest::StatusCode::ACCEPTED {
            return Err(RuntimeError::at("shutdown response status"));
        }
        Ok(())
    }

    fn fail_closed(&mut self) {
        // Closing the Job is the primary kill path. `Child::kill` is a silent
        // secondary fallback and targets the already-open process handle.
        self.job.take();
        let _ = self.child.kill();
        let _ = self.child.try_wait();
    }
}

impl Drop for RuntimeProcess {
    fn drop(&mut self) {
        self.fail_closed();
    }
}

fn build_http_client() -> Result<Client, RuntimeError> {
    Client::builder()
        .no_proxy()
        .redirect(Policy::none())
        .connect_timeout(HTTP_CONNECT_TIMEOUT)
        .timeout(HTTP_REQUEST_TIMEOUT)
        .build()
        .map_err(|_| RuntimeError::at("HTTP client construction"))
}

fn generate_bootstrap_secret() -> Result<MemorySecret, RuntimeError> {
    let mut random = Zeroizing::new([0_u8; SECRET_BYTES]);
    getrandom::fill(&mut *random).map_err(|_| RuntimeError::at("bootstrap randomness"))?;
    let encoded = Zeroizing::new(URL_SAFE_NO_PAD.encode(&*random));
    Ok(MemorySecret::from_bytes(encoded.as_bytes().to_vec()))
}

fn read_readiness_with_timeout(
    stdout: ChildStdout,
    expected_pid: u32,
) -> Result<ReadyMessage, RuntimeError> {
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::Builder::new()
        .name("runtime-readiness".to_owned())
        .spawn(move || {
            let result =
                read_ready_line(stdout).and_then(|line| parse_readiness(&line, expected_pid));
            let _ = sender.send(result);
        })
        .map_err(|_| RuntimeError::at("readiness reader spawn"))?;

    receiver
        .recv_timeout(READY_TIMEOUT)
        .map_err(|_| RuntimeError::at("readiness timeout"))?
}

fn read_ready_line(mut stdout: ChildStdout) -> Result<Vec<u8>, RuntimeError> {
    let mut line = Vec::with_capacity(128);
    let mut byte = [0_u8; 1];

    while line.len() < MAX_READY_LINE_BYTES {
        match stdout.read(&mut byte) {
            Ok(0) => return Err(RuntimeError::at("readiness pipe EOF")),
            Ok(_) if byte[0] == b'\n' => {
                if line.last() == Some(&b'\r') {
                    line.pop();
                }
                return Ok(line);
            }
            Ok(_) => line.push(byte[0]),
            Err(error) if error.kind() == ErrorKind::Interrupted => continue,
            Err(_) => return Err(RuntimeError::at("readiness pipe read")),
        }
    }

    Err(RuntimeError::at("readiness line limit"))
}

fn parse_readiness(line: &[u8], expected_pid: u32) -> Result<ReadyMessage, RuntimeError> {
    let ready: ReadyMessage =
        serde_json::from_slice(line).map_err(|_| RuntimeError::at("readiness JSON"))?;
    if ready.event != "runtime-ready" {
        return Err(RuntimeError::at("readiness event"));
    }
    if ready.host != LOOPBACK_HOST {
        return Err(RuntimeError::at("readiness host"));
    }
    if ready.pid != expected_pid || ready.pid == 0 {
        return Err(RuntimeError::at("readiness process"));
    }
    if ready.port == 0 {
        return Err(RuntimeError::at("readiness port"));
    }
    Ok(ready)
}

fn read_bounded_response(
    response: reqwest::blocking::Response,
    stage: &'static str,
) -> Result<Vec<u8>, RuntimeError> {
    let mut body = Vec::new();
    response
        .take(MAX_BOOTSTRAP_BODY_BYTES + 1)
        .read_to_end(&mut body)
        .map_err(|_| RuntimeError::at(stage))?;
    if body.len() as u64 > MAX_BOOTSTRAP_BODY_BYTES {
        return Err(RuntimeError::at(stage));
    }
    Ok(body)
}

fn validate_capability(encoded: &str) -> Result<MemorySecret, RuntimeError> {
    if encoded.is_empty()
        || encoded.len() > MAX_CAPABILITY_BYTES
        || !encoded
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_')
    {
        return Err(RuntimeError::at("capability encoding"));
    }

    let decoded = URL_SAFE_NO_PAD
        .decode(encoded)
        .map_err(|_| RuntimeError::at("capability encoding"))?;
    if decoded.len() < SECRET_BYTES || URL_SAFE_NO_PAD.encode(decoded) != encoded {
        return Err(RuntimeError::at("capability length"));
    }

    Ok(MemorySecret::from_bytes(encoded.as_bytes().to_vec()))
}

fn build_initialization_script(endpoint: &str, capability: &[u8]) -> Result<String, RuntimeError> {
    let capability = std::str::from_utf8(capability)
        .map_err(|_| RuntimeError::at("initialization capability encoding"))?;
    let origin_json = serde_json::to_string(TAURI_ORIGIN)
        .map_err(|_| RuntimeError::at("initialization origin serialization"))?;
    let global_json = serde_json::to_string(GLOBAL_NAME)
        .map_err(|_| RuntimeError::at("initialization name serialization"))?;
    let endpoint_json = serde_json::to_string(endpoint)
        .map_err(|_| RuntimeError::at("initialization endpoint serialization"))?;
    let capability_json = serde_json::to_string(capability)
        .map_err(|_| RuntimeError::at("initialization capability serialization"))?;

    Ok(format!(
        "(()=>{{'use strict';if(window.location.origin!=={origin_json})return;\
         const value=Object.create(null);Object.defineProperties(value,{{\
         endpoint:{{value:{endpoint_json},enumerable:false,writable:false,configurable:false}},\
         capability:{{value:{capability_json},enumerable:false,writable:false,configurable:false}}\
         }});Object.freeze(value);Object.defineProperty(globalThis,{global_json},{{\
         value,enumerable:false,writable:false,configurable:false}});}})();"
    ))
}

fn wait_for_child(
    child: &mut Child,
    timeout: Duration,
) -> Result<Option<std::process::ExitStatus>, RuntimeError> {
    let deadline = Instant::now() + timeout;
    loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|_| RuntimeError::at("sidecar wait"))?
        {
            return Ok(Some(status));
        }
        if Instant::now() >= deadline {
            return Ok(None);
        }
        thread::sleep(WAIT_POLL_INTERVAL);
    }
}

fn terminate_unassigned_child(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(test)]
mod tests {
    use super::*;

    fn synthetic_capability(fill: u8) -> String {
        URL_SAFE_NO_PAD.encode([fill; SECRET_BYTES])
    }

    #[test]
    fn readiness_parser_accepts_only_the_expected_process_and_listener() {
        let valid = br#"{"event":"runtime-ready","host":"127.0.0.1","pid":73,"port":43123}"#;
        let ready = parse_readiness(valid, 73).expect("parse synthetic readiness");
        assert_eq!(ready.port, 43123);

        let wrong_pid = br#"{"event":"runtime-ready","host":"127.0.0.1","pid":74,"port":43123}"#;
        let wildcard = br#"{"event":"runtime-ready","host":"0.0.0.0","pid":73,"port":43123}"#;
        let zero_port = br#"{"event":"runtime-ready","host":"127.0.0.1","pid":73,"port":0}"#;
        assert!(parse_readiness(wrong_pid, 73).is_err());
        assert!(parse_readiness(wildcard, 73).is_err());
        assert!(parse_readiness(zero_port, 73).is_err());
    }

    #[test]
    fn readiness_parser_rejects_unknown_fields_and_trailing_data() {
        let unknown = br#"{"event":"runtime-ready","host":"127.0.0.1","pid":73,"port":43123,"secret":"forbidden"}"#;
        let trailing = br#"{"event":"runtime-ready","host":"127.0.0.1","pid":73,"port":43123}{}"#;
        assert!(parse_readiness(unknown, 73).is_err());
        assert!(parse_readiness(trailing, 73).is_err());
    }

    #[test]
    fn capability_requires_canonical_base64url_with_256_bits() {
        let valid = synthetic_capability(0x5a);
        let parsed = validate_capability(&valid).expect("validate synthetic capability");
        assert_eq!(parsed.expose().len(), valid.len());

        let short = URL_SAFE_NO_PAD.encode([0x5a; SECRET_BYTES - 1]);
        let padded = format!("{valid}=");
        assert!(validate_capability(&short).is_err());
        assert!(validate_capability(&padded).is_err());
        assert!(validate_capability("not+base64url").is_err());
    }

    #[test]
    fn initialization_script_is_origin_bound_frozen_and_non_enumerable() {
        let capability = synthetic_capability(0xa5);
        let script = build_initialization_script("http://127.0.0.1:43123", capability.as_bytes())
            .expect("build synthetic initialization script");

        assert!(script.contains("window.location.origin!==\"http://tauri.localhost\""));
        assert!(script.contains("Object.freeze(value)"));
        assert!(script.contains("Object.defineProperty(globalThis"));
        assert!(script.contains("enumerable:false"));
        assert!(!script.to_ascii_lowercase().contains("bootstrap"));
        assert!(
            script
                .as_bytes()
                .windows(capability.len())
                .any(|window| window == capability.as_bytes()),
            "initialization script omitted the synthetic capability"
        );
    }
}
