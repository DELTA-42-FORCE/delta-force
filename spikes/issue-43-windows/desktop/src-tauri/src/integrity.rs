//! Synthetic sidecar integrity proof for issue #43.
//!
//! This module only verifies a tree. It never starts the verified executable.

use std::collections::{BTreeMap, HashSet};
use std::fmt;
use std::fs::{self, File, Metadata};
use std::io::Read;
use std::path::{Component, Path};

use ed25519_dalek::{Signature, VerifyingKey};
use serde::Deserialize;
use sha2::{Digest, Sha256};

const MANIFEST_NAME: &str = "manifest.json";
const SIGNATURE_NAME: &str = "manifest.sig";
const SIDECAR_NAME: &str = "crm-api-poc.exe";
const RUNTIME_DIRECTORY: &str = "api-runtime";
const SIGNATURE_LENGTH: usize = 64;
const MAX_MANIFEST_BYTES: u64 = 1024 * 1024;
const MAX_MANIFEST_ENTRIES: usize = 4096;
const MAX_RUNTIME_DEPTH: usize = 16;

// RFC 8032 test vector public key. This is deliberately public, synthetic,
// and forbidden for production signing or trust decisions.
const SYNTHETIC_SPIKE_PUBLIC_KEY: [u8; 32] = [
    0xd7, 0x5a, 0x98, 0x01, 0x82, 0xb1, 0x0a, 0xb7, 0xd5, 0x4b, 0xfe, 0xd3, 0xc9, 0x64, 0x07, 0x3a,
    0x0e, 0xe1, 0x72, 0xf3, 0xda, 0xa6, 0x23, 0x25, 0xaf, 0x02, 0x1a, 0x68, 0xf7, 0x07, 0x51, 0x1a,
];

#[derive(Debug, PartialEq, Eq)]
pub enum IntegrityError {
    Io(&'static str),
    InvalidEmbeddedKey,
    InvalidSignature,
    InvalidManifest(&'static str),
    UnsafePath(String),
    UnexpectedPath(String),
    DuplicatePath(String),
    UnsortedEntries,
    InvalidHash(String),
    ReparsePoint(String),
    UnsupportedFileType(String),
    MissingFile(String),
    ExtraFile(String),
    SizeMismatch(String),
    HashMismatch(String),
}

impl fmt::Display for IntegrityError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(stage) => write!(formatter, "integrity I/O failure at {stage}"),
            Self::InvalidEmbeddedKey => formatter.write_str("invalid embedded test key"),
            Self::InvalidSignature => formatter.write_str("invalid manifest signature"),
            Self::InvalidManifest(reason) => {
                write!(formatter, "invalid manifest: {reason}")
            }
            Self::UnsafePath(path) => write!(formatter, "unsafe manifest path: {path}"),
            Self::UnexpectedPath(path) => {
                write!(formatter, "path is outside the sidecar layout: {path}")
            }
            Self::DuplicatePath(path) => write!(formatter, "duplicate manifest path: {path}"),
            Self::UnsortedEntries => formatter.write_str("manifest entries are not sorted"),
            Self::InvalidHash(path) => write!(formatter, "invalid SHA-256 for: {path}"),
            Self::ReparsePoint(path) => write!(formatter, "reparse point rejected: {path}"),
            Self::UnsupportedFileType(path) => {
                write!(formatter, "unsupported file type: {path}")
            }
            Self::MissingFile(path) => write!(formatter, "missing sidecar file: {path}"),
            Self::ExtraFile(path) => write!(formatter, "extra sidecar file: {path}"),
            Self::SizeMismatch(path) => write!(formatter, "size mismatch: {path}"),
            Self::HashMismatch(path) => write!(formatter, "hash mismatch: {path}"),
        }
    }
}

impl std::error::Error for IntegrityError {}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    schema: u32,
    entries: Vec<ManifestEntry>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ManifestEntry {
    path: String,
    size: u64,
    sha256: String,
}

#[derive(Debug)]
struct ExpectedFile {
    size: u64,
    sha256: [u8; 32],
}

#[derive(Debug)]
struct ActualFile {
    size: u64,
    sha256: [u8; 32],
}

/// Verify the complete `sidecar/` tree without executing any of its files.
pub fn verify_sidecar_integrity(sidecar_root: &Path) -> Result<(), IntegrityError> {
    validate_root(sidecar_root)?;

    let manifest_bytes = read_control_file(sidecar_root, MANIFEST_NAME, MAX_MANIFEST_BYTES)?;
    let signature_bytes = read_control_file(sidecar_root, SIGNATURE_NAME, SIGNATURE_LENGTH as u64)?;
    verify_manifest_signature(&manifest_bytes, &signature_bytes)?;

    let manifest: Manifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|_| IntegrityError::InvalidManifest("strict JSON parse"))?;
    let expected = validate_manifest(manifest)?;

    let mut actual = BTreeMap::new();
    let mut runtime_directory_seen = false;
    scan_directory(
        sidecar_root,
        sidecar_root,
        &expected,
        &mut actual,
        &mut runtime_directory_seen,
        0,
    )?;

    if !runtime_directory_seen {
        return Err(IntegrityError::MissingFile(RUNTIME_DIRECTORY.to_owned()));
    }

    compare_entries(expected, actual)
}

fn validate_root(sidecar_root: &Path) -> Result<(), IntegrityError> {
    let metadata = fs::symlink_metadata(sidecar_root)
        .map_err(|_| IntegrityError::Io("sidecar root metadata"))?;
    if metadata.file_type().is_symlink() || has_reparse_point(&metadata) {
        return Err(IntegrityError::ReparsePoint(".".to_owned()));
    }
    if !metadata.is_dir() {
        return Err(IntegrityError::UnsupportedFileType(".".to_owned()));
    }
    Ok(())
}

fn read_control_file(
    sidecar_root: &Path,
    file_name: &'static str,
    max_bytes: u64,
) -> Result<Vec<u8>, IntegrityError> {
    let path = sidecar_root.join(file_name);
    let metadata = match fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Err(IntegrityError::MissingFile(file_name.to_owned()));
        }
        Err(_) => return Err(IntegrityError::Io("control file metadata")),
    };
    if metadata.file_type().is_symlink() || has_reparse_point(&metadata) {
        return Err(IntegrityError::ReparsePoint(file_name.to_owned()));
    }
    if !metadata.is_file() {
        return Err(IntegrityError::UnsupportedFileType(file_name.to_owned()));
    }
    if metadata.len() > max_bytes {
        return Err(IntegrityError::InvalidManifest("control file size limit"));
    }

    let file = File::open(path).map_err(|_| IntegrityError::Io("control file open"))?;
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    file.take(max_bytes + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| IntegrityError::Io("control file read"))?;
    if bytes.len() as u64 > max_bytes {
        return Err(IntegrityError::InvalidManifest("control file size limit"));
    }
    Ok(bytes)
}

fn verify_manifest_signature(
    manifest_bytes: &[u8],
    signature_bytes: &[u8],
) -> Result<(), IntegrityError> {
    let signature_array: &[u8; SIGNATURE_LENGTH] = signature_bytes
        .try_into()
        .map_err(|_| IntegrityError::InvalidSignature)?;
    let signature = Signature::from_bytes(signature_array);
    let verifying_key = VerifyingKey::from_bytes(&SYNTHETIC_SPIKE_PUBLIC_KEY)
        .map_err(|_| IntegrityError::InvalidEmbeddedKey)?;

    verifying_key
        .verify_strict(manifest_bytes, &signature)
        .map_err(|_| IntegrityError::InvalidSignature)
}

fn validate_manifest(manifest: Manifest) -> Result<BTreeMap<String, ExpectedFile>, IntegrityError> {
    if manifest.schema != 1 {
        return Err(IntegrityError::InvalidManifest("unsupported schema"));
    }
    if manifest.entries.len() > MAX_MANIFEST_ENTRIES {
        return Err(IntegrityError::InvalidManifest("entry count limit"));
    }

    let mut expected = BTreeMap::new();
    let mut seen = HashSet::new();
    let mut previous_path: Option<&str> = None;

    for entry in &manifest.entries {
        validate_payload_path(&entry.path)?;
        if !seen.insert(entry.path.as_str()) {
            return Err(IntegrityError::DuplicatePath(entry.path.clone()));
        }
        if previous_path.is_some_and(|previous| previous >= entry.path.as_str()) {
            return Err(IntegrityError::UnsortedEntries);
        }
        previous_path = Some(entry.path.as_str());

        expected.insert(
            entry.path.clone(),
            ExpectedFile {
                size: entry.size,
                sha256: decode_sha256(&entry.path, &entry.sha256)?,
            },
        );
    }

    if !expected.contains_key(SIDECAR_NAME) {
        return Err(IntegrityError::MissingFile(SIDECAR_NAME.to_owned()));
    }
    Ok(expected)
}

fn validate_payload_path(path: &str) -> Result<(), IntegrityError> {
    if path.is_empty()
        || path.contains('\\')
        || path.contains('\0')
        || path.contains(':')
        || path.starts_with('/')
        || Path::new(path).is_absolute()
    {
        return Err(IntegrityError::UnsafePath(path.to_owned()));
    }

    if path
        .split('/')
        .any(|component| component.is_empty() || component == "." || component == "..")
    {
        return Err(IntegrityError::UnsafePath(path.to_owned()));
    }

    if path != SIDECAR_NAME
        && !path
            .strip_prefix("api-runtime/")
            .is_some_and(|suffix| !suffix.is_empty())
    {
        return Err(IntegrityError::UnexpectedPath(path.to_owned()));
    }
    Ok(())
}

fn decode_sha256(path: &str, encoded: &str) -> Result<[u8; 32], IntegrityError> {
    if encoded.len() != 64
        || !encoded
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(IntegrityError::InvalidHash(path.to_owned()));
    }

    let decoded = hex::decode(encoded).map_err(|_| IntegrityError::InvalidHash(path.to_owned()))?;
    decoded
        .try_into()
        .map_err(|_| IntegrityError::InvalidHash(path.to_owned()))
}

fn scan_directory(
    sidecar_root: &Path,
    current_directory: &Path,
    expected: &BTreeMap<String, ExpectedFile>,
    actual: &mut BTreeMap<String, ActualFile>,
    runtime_directory_seen: &mut bool,
    depth: usize,
) -> Result<(), IntegrityError> {
    if depth > MAX_RUNTIME_DEPTH {
        return Err(IntegrityError::InvalidManifest("runtime depth limit"));
    }

    let entries = fs::read_dir(current_directory)
        .map_err(|_| IntegrityError::Io("sidecar directory read"))?;

    for entry in entries {
        let entry = entry.map_err(|_| IntegrityError::Io("sidecar directory entry"))?;
        let path = entry.path();
        let relative_path = manifest_path(sidecar_root, &path)?;
        let metadata =
            fs::symlink_metadata(&path).map_err(|_| IntegrityError::Io("payload metadata"))?;

        if metadata.file_type().is_symlink() || has_reparse_point(&metadata) {
            return Err(IntegrityError::ReparsePoint(relative_path));
        }

        if metadata.is_dir() {
            if relative_path == RUNTIME_DIRECTORY {
                *runtime_directory_seen = true;
            } else if !relative_path.starts_with("api-runtime/") {
                return Err(IntegrityError::ExtraFile(relative_path));
            }
            let child_prefix = format!("{relative_path}/");
            if !expected
                .keys()
                .any(|expected_path| expected_path.starts_with(&child_prefix))
            {
                return Err(IntegrityError::ExtraFile(relative_path));
            }
            scan_directory(
                sidecar_root,
                &path,
                expected,
                actual,
                runtime_directory_seen,
                depth + 1,
            )?;
        } else if metadata.is_file() {
            if relative_path == MANIFEST_NAME || relative_path == SIGNATURE_NAME {
                continue;
            }
            validate_payload_path(&relative_path)?;
            let expected_file = expected
                .get(&relative_path)
                .ok_or_else(|| IntegrityError::ExtraFile(relative_path.clone()))?;
            if metadata.len() != expected_file.size {
                return Err(IntegrityError::SizeMismatch(relative_path));
            }
            let facts = hash_file(&path, &metadata, expected_file.size)?;
            if actual.insert(relative_path.clone(), facts).is_some() {
                return Err(IntegrityError::DuplicatePath(relative_path));
            }
        } else {
            return Err(IntegrityError::UnsupportedFileType(relative_path));
        }
    }
    Ok(())
}

fn manifest_path(sidecar_root: &Path, path: &Path) -> Result<String, IntegrityError> {
    let relative = path
        .strip_prefix(sidecar_root)
        .map_err(|_| IntegrityError::UnsafePath("<outside-root>".to_owned()))?;
    let mut components = Vec::new();

    for component in relative.components() {
        match component {
            Component::Normal(value) => components.push(
                value
                    .to_str()
                    .ok_or_else(|| IntegrityError::UnsafePath("<non-utf8>".to_owned()))?,
            ),
            _ => return Err(IntegrityError::UnsafePath("<invalid-component>".to_owned())),
        }
    }

    Ok(components.join("/"))
}

fn hash_file(
    path: &Path,
    initial_metadata: &Metadata,
    expected_size: u64,
) -> Result<ActualFile, IntegrityError> {
    let mut file = File::open(path).map_err(|_| IntegrityError::Io("payload open"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    let mut bytes_read = 0_u64;
    let read_limit = expected_size
        .checked_add(1)
        .ok_or(IntegrityError::Io("payload length"))?;
    let mut bounded_file = (&mut file).take(read_limit);

    loop {
        let count = bounded_file
            .read(&mut buffer)
            .map_err(|_| IntegrityError::Io("payload read"))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
        bytes_read = bytes_read
            .checked_add(count as u64)
            .ok_or(IntegrityError::Io("payload length"))?;
    }
    drop(bounded_file);

    let final_metadata = file
        .metadata()
        .map_err(|_| IntegrityError::Io("payload final metadata"))?;
    if bytes_read != expected_size
        || initial_metadata.len() != bytes_read
        || final_metadata.len() != bytes_read
    {
        return Err(IntegrityError::Io("payload changed during verification"));
    }

    Ok(ActualFile {
        size: bytes_read,
        sha256: hasher.finalize().into(),
    })
}

fn compare_entries(
    expected: BTreeMap<String, ExpectedFile>,
    mut actual: BTreeMap<String, ActualFile>,
) -> Result<(), IntegrityError> {
    for (path, expected_file) in expected {
        let actual_file = actual
            .remove(&path)
            .ok_or_else(|| IntegrityError::MissingFile(path.clone()))?;
        if actual_file.size != expected_file.size {
            return Err(IntegrityError::SizeMismatch(path));
        }
        if actual_file.sha256 != expected_file.sha256 {
            return Err(IntegrityError::HashMismatch(path));
        }
    }

    if let Some(path) = actual.into_keys().next() {
        return Err(IntegrityError::ExtraFile(path));
    }
    Ok(())
}

#[cfg(windows)]
fn has_reparse_point(metadata: &Metadata) -> bool {
    use std::os::windows::fs::MetadataExt;

    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0400;
    metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
}

#[cfg(not(windows))]
fn has_reparse_point(_metadata: &Metadata) -> bool {
    false
}

#[cfg(test)]
mod tests {
    use std::fs;

    use ed25519_dalek::{Signer, SigningKey};
    use serde_json::{Value, json};
    use tempfile::TempDir;

    use super::*;

    // RFC 8032 test vector seed. Test-only and never valid for production use.
    const SYNTHETIC_TEST_SIGNING_KEY: [u8; 32] = [
        0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a, 0xf4, 0x92, 0xec, 0x2c,
        0xc4, 0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32, 0x69, 0x19, 0x70, 0x3b, 0xac, 0x03, 0x1c, 0xae,
        0x7f, 0x60,
    ];

    fn create_fixture() -> TempDir {
        let temporary = tempfile::tempdir().expect("create synthetic fixture");
        let root = temporary.path().join("sidecar");
        fs::create_dir_all(root.join(RUNTIME_DIRECTORY)).expect("create runtime tree");
        fs::write(root.join(SIDECAR_NAME), b"synthetic executable")
            .expect("write synthetic executable");
        fs::write(
            root.join(RUNTIME_DIRECTORY).join("runtime.bin"),
            b"synthetic runtime A",
        )
        .expect("write synthetic runtime");
        write_signed_manifest(&root, default_entries(&root));
        temporary
    }

    fn default_entries(root: &Path) -> Vec<Value> {
        let mut entries = vec![
            manifest_entry(root, "api-runtime/runtime.bin"),
            manifest_entry(root, SIDECAR_NAME),
        ];
        entries.sort_by(|left, right| {
            left["path"]
                .as_str()
                .expect("entry path")
                .cmp(right["path"].as_str().expect("entry path"))
        });
        entries
    }

    fn manifest_entry(root: &Path, relative_path: &str) -> Value {
        let bytes = fs::read(root.join(relative_path)).expect("read synthetic payload");
        json!({
            "path": relative_path,
            "size": bytes.len(),
            "sha256": hex::encode(Sha256::digest(&bytes)),
        })
    }

    fn write_signed_manifest(root: &Path, entries: Vec<Value>) {
        let manifest_bytes = serde_json::to_vec(&json!({
            "schema": 1,
            "entries": entries,
        }))
        .expect("serialize synthetic manifest");
        let signing_key = SigningKey::from_bytes(&SYNTHETIC_TEST_SIGNING_KEY);
        let signature: Signature = signing_key.sign(&manifest_bytes);

        fs::write(root.join(MANIFEST_NAME), manifest_bytes).expect("write manifest");
        fs::write(root.join(SIGNATURE_NAME), signature.to_bytes()).expect("write signature");
    }

    #[test]
    fn accepts_an_intact_signed_tree() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");

        assert_eq!(verify_sidecar_integrity(&root), Ok(()));
    }

    #[test]
    fn rejects_a_modified_manifest() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        let mut manifest = fs::read(root.join(MANIFEST_NAME)).expect("read manifest");
        manifest.push(b'\n');
        fs::write(root.join(MANIFEST_NAME), manifest).expect("tamper manifest");

        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::InvalidSignature)
        );
    }

    #[test]
    fn rejects_a_modified_signature() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        let mut signature = fs::read(root.join(SIGNATURE_NAME)).expect("read signature");
        signature[0] ^= 0x01;
        fs::write(root.join(SIGNATURE_NAME), signature).expect("tamper signature");

        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::InvalidSignature)
        );
    }

    #[test]
    fn rejects_an_oversized_control_file_before_allocating_it() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        let manifest = File::create(root.join(MANIFEST_NAME)).expect("replace manifest");
        manifest
            .set_len(MAX_MANIFEST_BYTES + 1)
            .expect("extend manifest");

        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::InvalidManifest("control file size limit"))
        );
    }

    #[test]
    fn rejects_a_modified_payload_with_the_same_size() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        fs::write(
            root.join(RUNTIME_DIRECTORY).join("runtime.bin"),
            b"synthetic runtime B",
        )
        .expect("tamper payload");

        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::HashMismatch(
                "api-runtime/runtime.bin".to_owned()
            ))
        );
    }

    #[test]
    fn rejects_a_missing_payload() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        fs::remove_file(root.join(RUNTIME_DIRECTORY).join("runtime.bin")).expect("remove payload");

        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::MissingFile(
                "api-runtime/runtime.bin".to_owned()
            ))
        );
    }

    #[test]
    fn rejects_an_extra_payload() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        fs::write(
            root.join(RUNTIME_DIRECTORY).join("extra.bin"),
            b"synthetic extra",
        )
        .expect("write extra payload");

        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::ExtraFile(
                "api-runtime/extra.bin".to_owned()
            ))
        );
    }

    #[test]
    fn rejects_unsafe_duplicate_and_unsorted_manifest_paths() {
        let fixture = create_fixture();
        let root = fixture.path().join("sidecar");
        let valid = manifest_entry(&root, SIDECAR_NAME);

        for unsafe_path in [
            "C:/absolute.exe",
            "../escape.exe",
            "api-runtime\\runtime.bin",
        ] {
            let mut entry = valid.clone();
            entry["path"] = Value::String(unsafe_path.to_owned());
            write_signed_manifest(&root, vec![entry]);
            assert!(matches!(
                verify_sidecar_integrity(&root),
                Err(IntegrityError::UnsafePath(_))
            ));
        }

        write_signed_manifest(&root, vec![valid.clone(), valid.clone()]);
        assert!(matches!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::DuplicatePath(_))
        ));

        write_signed_manifest(
            &root,
            vec![
                manifest_entry(&root, SIDECAR_NAME),
                manifest_entry(&root, "api-runtime/runtime.bin"),
            ],
        );
        assert_eq!(
            verify_sidecar_integrity(&root),
            Err(IntegrityError::UnsortedEntries)
        );
    }
}
