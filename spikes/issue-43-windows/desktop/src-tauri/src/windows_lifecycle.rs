//! Windows-only lifecycle primitives for the disposable issue #43 spike.
//!
//! The runtime must spawn the sidecar while it is blocked waiting for its
//! bootstrap line on stdin, assign that process to [`KillOnCloseJob`], and only
//! then write the secret. This ordering closes the useful race window: the
//! sidecar cannot bind a listener or create descendants before job assignment.

use std::{error::Error, ffi::c_void, fmt, mem::size_of, ptr};

use windows::{
    Win32::{
        Foundation::{CloseHandle, ERROR_ALREADY_EXISTS, GetLastError, HANDLE},
        System::{
            JobObjects::{
                AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
                JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObjectExtendedLimitInformation,
                SetInformationJobObject,
            },
            Threading::{CreateMutexW, OpenProcess, PROCESS_SET_QUOTA, PROCESS_TERMINATE},
        },
    },
    core::{Error as WindowsError, PCWSTR},
};

/// Failures are intentionally coarse so callers never expose OS details to the
/// WebView. `AlreadyRunning` remains distinct so a second instance can exit
/// normally before it creates a window, listener, or child process.
#[derive(Debug)]
pub enum LifecycleError {
    AlreadyRunning,
    InvalidMutexName,
    InvalidProcessId,
    Windows {
        operation: &'static str,
        source: WindowsError,
    },
}

impl LifecycleError {
    fn windows(operation: &'static str, source: WindowsError) -> Self {
        Self::Windows { operation, source }
    }
}

impl fmt::Display for LifecycleError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AlreadyRunning => formatter.write_str("another instance is running"),
            Self::InvalidMutexName => formatter.write_str("invalid local mutex name"),
            Self::InvalidProcessId => formatter.write_str("invalid process id"),
            Self::Windows { operation, .. } => {
                write!(formatter, "Windows lifecycle operation failed: {operation}")
            }
        }
    }
}

impl Error for LifecycleError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Windows { source, .. } => Some(source),
            _ => None,
        }
    }
}

type LifecycleResult<T> = Result<T, LifecycleError>;

/// Sole owner of a process-wide Windows handle.
struct OwnedHandle(HANDLE);

impl OwnedHandle {
    fn new(handle: HANDLE) -> Self {
        Self(handle)
    }

    fn raw(&self) -> HANDLE {
        self.0
    }
}

impl Drop for OwnedHandle {
    fn drop(&mut self) {
        // SAFETY: `OwnedHandle` is constructed only from a successful Win32
        // call and owns exactly one handle. Drop runs at most once.
        let _ = unsafe { CloseHandle(self.0) };
    }
}

// Windows kernel handles are process-wide. Moving or sharing this immutable
// owner between threads is safe; Rust ownership prevents CloseHandle while a
// borrowed operation is running.
unsafe impl Send for OwnedHandle {}
unsafe impl Sync for OwnedHandle {}

/// Holds a `Local\` named mutex for the lifetime of the first app instance.
///
/// `Local\` is scoped to the current Windows session and needs no global-object
/// privilege. The default security descriptor comes from the current token.
pub struct SingleInstanceGuard {
    _mutex: OwnedHandle,
}

impl SingleInstanceGuard {
    pub fn acquire(name: &str) -> LifecycleResult<Self> {
        if !valid_local_mutex_name(name) {
            return Err(LifecycleError::InvalidMutexName);
        }

        let wide_name = wide_null_terminated(name);

        // SAFETY: the security-attributes pointer is null, the name is a
        // NUL-terminated UTF-16 buffer alive for the entire call, and initial
        // ownership is not requested.
        let raw = unsafe { CreateMutexW(None, false, PCWSTR(wide_name.as_ptr())) }
            .map_err(|source| LifecycleError::windows("CreateMutexW", source))?;

        // GetLastError must be observed immediately after the successful call:
        // CreateMutexW returns a valid handle even when the name already exists.
        let already_exists = unsafe { GetLastError() } == ERROR_ALREADY_EXISTS;
        let mutex = OwnedHandle::new(raw);

        if already_exists {
            drop(mutex);
            return Err(LifecycleError::AlreadyRunning);
        }

        Ok(Self { _mutex: mutex })
    }
}

/// A job whose processes are terminated when the launcher dies or drops the
/// final job handle.
pub struct KillOnCloseJob {
    job: OwnedHandle,
}

impl KillOnCloseJob {
    pub fn new() -> LifecycleResult<Self> {
        // SAFETY: null security attributes and a null name request an anonymous
        // job with the caller's default security descriptor.
        let raw = unsafe { CreateJobObjectW(None, PCWSTR::null()) }
            .map_err(|source| LifecycleError::windows("CreateJobObjectW", source))?;
        let job = OwnedHandle::new(raw);

        let information = kill_on_close_information();

        // SAFETY: `information` has the exact layout and size required by
        // JobObjectExtendedLimitInformation and remains alive during the call.
        unsafe {
            SetInformationJobObject(
                job.raw(),
                JobObjectExtendedLimitInformation,
                ptr::from_ref(&information).cast::<c_void>(),
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            )
        }
        .map_err(|source| LifecycleError::windows("SetInformationJobObject", source))?;

        Ok(Self { job })
    }

    /// Assign an already spawned, still-bootstrap-blocked sidecar to this job.
    pub fn assign_process(&self, pid: u32) -> LifecycleResult<()> {
        if pid == 0 {
            return Err(LifecycleError::InvalidProcessId);
        }

        // PROCESS_SET_QUOTA and PROCESS_TERMINATE are the documented minimum
        // rights needed by AssignProcessToJobObject.
        let access = PROCESS_SET_QUOTA | PROCESS_TERMINATE;

        // SAFETY: `pid` identifies the child just spawned by the runtime; the
        // returned handle is immediately wrapped in RAII and is not inheritable.
        let raw_process = unsafe { OpenProcess(access, false, pid) }
            .map_err(|source| LifecycleError::windows("OpenProcess", source))?;
        let process = OwnedHandle::new(raw_process);

        // SAFETY: both handles are valid for the duration of the call. The
        // process handle is closed afterwards; job membership remains active.
        unsafe { AssignProcessToJobObject(self.job.raw(), process.raw()) }
            .map_err(|source| LifecycleError::windows("AssignProcessToJobObject", source))?;

        Ok(())
    }
}

fn valid_local_mutex_name(name: &str) -> bool {
    let suffix = name.strip_prefix("Local\\");
    matches!(suffix, Some(value) if !value.is_empty() && !value.contains('\0'))
}

fn wide_null_terminated(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}

fn kill_on_close_information() -> JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
    let mut information = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
    information.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    information
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicU64, Ordering};

    use super::*;

    static UNIQUE_NAME: AtomicU64 = AtomicU64::new(1);

    fn test_mutex_name() -> String {
        format!(
            "Local\\DeltaForce-Issue43-Test-{}-{}",
            std::process::id(),
            UNIQUE_NAME.fetch_add(1, Ordering::Relaxed)
        )
    }

    #[test]
    fn mutex_rejects_non_local_names() {
        assert!(matches!(
            SingleInstanceGuard::acquire("Global\\DeltaForce-Issue43"),
            Err(LifecycleError::InvalidMutexName)
        ));
    }

    #[test]
    fn second_mutex_is_rejected_and_name_can_be_reopened_after_drop() {
        let name = test_mutex_name();
        let first = SingleInstanceGuard::acquire(&name).expect("first mutex");

        assert!(matches!(
            SingleInstanceGuard::acquire(&name),
            Err(LifecycleError::AlreadyRunning)
        ));

        drop(first);
        let reopened = SingleInstanceGuard::acquire(&name).expect("reopened mutex");
        drop(reopened);
    }

    #[test]
    fn job_configuration_enables_kill_on_close_only() {
        let information = kill_on_close_information();
        assert_eq!(
            information.BasicLimitInformation.LimitFlags,
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        );
    }

    #[test]
    fn empty_job_can_be_created_and_closed_safely() {
        let job = KillOnCloseJob::new().expect("anonymous job");
        drop(job);
    }

    #[test]
    fn zero_is_not_a_valid_child_process_id() {
        let job = KillOnCloseJob::new().expect("anonymous job");
        assert!(matches!(
            job.assign_process(0),
            Err(LifecycleError::InvalidProcessId)
        ));
    }
}
