use std::env;
use std::fs::OpenOptions;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use tauri::{AppHandle, Manager, Runtime};
use uuid::Uuid;

/// Owns the Sidecar process for the entire desktop lifetime.
struct SidecarProcess {
    child: Mutex<Option<Child>>,
    shutting_down: AtomicBool,
}

impl SidecarProcess {
    fn new() -> Self {
        Self {
            child: Mutex::new(None),
            shutting_down: AtomicBool::new(false),
        }
    }
}

struct DesktopCapabilityToken(String);

const SIDECAR_HOST: &str = "127.0.0.1";
const SIDECAR_PORT: u16 = 8100;
const SIDECAR_RESOURCE_DIR: &str = "sidecar";
const SIDECAR_BUNDLE_DIR: &str = "zhangwen-sidecar";
const SIDECAR_EXE: &str = "zhangwen-sidecar.exe";
const APP_DATA_DIR: &str = "Zhangwen";
const MAX_CONSECUTIVE_SIDECAR_FAILURES: u32 = 6;
const MAX_SIDECAR_LOG_BYTES: u64 = 5 * 1024 * 1024;
const SIDECAR_READY_TIMEOUT_SECS: u32 = 120;

struct SidecarLaunch {
    executable: PathBuf,
    args: Vec<String>,
    working_dir: PathBuf,
    source: &'static str,
}

fn connect_to_sidecar() -> Option<TcpStream> {
    let addr = format!("{SIDECAR_HOST}:{SIDECAR_PORT}");
    TcpStream::connect_timeout(
        &addr.parse().expect("invalid sidecar address"),
        Duration::from_millis(500),
    )
    .ok()
}

fn sidecar_capability_matches(capability_token: &str) -> bool {
    if capability_token
        .bytes()
        .any(|value| value < 0x21 || value > 0x7e)
    {
        return false;
    }
    let Some(mut stream) = connect_to_sidecar() else {
        return false;
    };
    let timeout = Some(Duration::from_millis(750));
    let _ = stream.set_read_timeout(timeout);
    let _ = stream.set_write_timeout(timeout);
    let request = format!(
        "GET /api/health/desktop-capability HTTP/1.1\r\n\
         Host: {SIDECAR_HOST}:{SIDECAR_PORT}\r\n\
         X-Zhangwen-Host: tauri\r\n\
         X-Zhangwen-Capability-Token: {capability_token}\r\n\
         Connection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    response
        .lines()
        .next()
        .is_some_and(|line| line.starts_with("HTTP/1.1 200") || line.starts_with("HTTP/1.0 200"))
}

enum SidecarWaitResult {
    Ready,
    Exited(Option<i32>),
    TimedOut,
}

fn wait_for_sidecar(
    child: &mut Child,
    capability_token: &str,
    timeout_secs: u32,
) -> SidecarWaitResult {
    let attempts = timeout_secs * 2;
    for _ in 0..attempts {
        if sidecar_capability_matches(capability_token) {
            return SidecarWaitResult::Ready;
        }
        if let Ok(Some(status)) = child.try_wait() {
            return SidecarWaitResult::Exited(status.code());
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    SidecarWaitResult::TimedOut
}

fn append_sidecar_log(log: &mut std::fs::File, event: &str) {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or_default();
    let _ = writeln!(log, "launcher:{timestamp}:{event}");
    let _ = log.flush();
}

fn append_supervisor_log<R: Runtime>(app: &AppHandle<R>, event: &str) {
    let Some(data_dir) = sidecar_data_dir(app) else {
        return;
    };
    let log_dir = data_dir.join("logs");
    if std::fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    if let Ok(mut log) = open_sidecar_log(&log_dir) {
        append_sidecar_log(&mut log, event);
    }
}

fn open_sidecar_log(log_dir: &Path) -> Result<std::fs::File, String> {
    std::fs::create_dir_all(log_dir)
        .map_err(|error| format!("Cannot create the Sidecar log directory: {error}"))?;
    let log_path = log_dir.join("sidecar-process.log");
    if log_path
        .metadata()
        .map(|metadata| metadata.len() >= MAX_SIDECAR_LOG_BYTES)
        .unwrap_or(false)
    {
        let archived = log_dir.join("sidecar-process.log.1");
        let _ = std::fs::remove_file(&archived);
        std::fs::rename(&log_path, archived)
            .map_err(|error| format!("Cannot rotate the Sidecar process log: {error}"))?;
    }
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
        .map_err(|error| format!("Cannot open the Sidecar process log: {error}"))
}

fn sidecar_error_code(error: &str) -> &'static str {
    if error.contains("already used") {
        "port-in-use"
    } else if error.contains("runtime are unavailable") {
        "runtime-unavailable"
    } else if error.contains("data directory") {
        "data-directory"
    } else if error.contains("log") {
        "log-unavailable"
    } else if error.contains("exited before") {
        "exited-before-ready"
    } else if error.contains("within 30 seconds") {
        "ready-timeout"
    } else {
        "spawn-failed"
    }
}

fn restart_delay(consecutive_failures: u32) -> Duration {
    let exponent = consecutive_failures.saturating_sub(1).min(5);
    Duration::from_secs((1_u64 << exponent).min(30))
}

fn sleep_until_restart<R: Runtime>(app: &AppHandle<R>, delay: Duration) -> bool {
    let deadline = Instant::now() + delay;
    while Instant::now() < deadline {
        if app
            .try_state::<SidecarProcess>()
            .is_some_and(|state| state.shutting_down.load(Ordering::Acquire))
        {
            return false;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    true
}

fn supervise_sidecar<R: Runtime>(app: AppHandle<R>, capability_token: String) {
    std::thread::spawn(move || {
        let mut consecutive_failures = 0_u32;
        let mut last_started = Instant::now();

        loop {
            std::thread::sleep(Duration::from_secs(2));
            let Some(state) = app.try_state::<SidecarProcess>() else {
                return;
            };
            if state.shutting_down.load(Ordering::Acquire) {
                return;
            }

            let exited = {
                let mut guard = state.child.lock().expect("sidecar state poisoned");
                match guard.as_mut().and_then(|child| child.try_wait().ok()).flatten() {
                    Some(status) => {
                        let pid = guard.as_ref().map(Child::id).unwrap_or_default();
                        *guard = None;
                        Some((pid, status.code()))
                    }
                    None => None,
                }
            };

            let should_start = if let Some((pid, code)) = exited {
                if last_started.elapsed() >= Duration::from_secs(60) {
                    consecutive_failures = 0;
                }
                consecutive_failures = consecutive_failures.saturating_add(1);
                append_supervisor_log(
                    &app,
                    &format!(
                        "unexpected-exit pid={pid} code={code:?} consecutive={consecutive_failures}"
                    ),
                );
                true
            } else {
                let has_child = state
                    .child
                    .lock()
                    .expect("sidecar state poisoned")
                    .is_some();
                !has_child && !sidecar_capability_matches(&capability_token)
            };

            if !should_start {
                continue;
            }

            if consecutive_failures >= MAX_CONSECUTIVE_SIDECAR_FAILURES {
                append_supervisor_log(
                    &app,
                    &format!(
                        "restart-exhausted consecutive={consecutive_failures} action=manual-restart"
                    ),
                );
                return;
            }

            let delay = restart_delay(consecutive_failures.max(1));
            append_supervisor_log(
                &app,
                &format!("restart-scheduled delay_ms={}", delay.as_millis()),
            );
            if !sleep_until_restart(&app, delay) {
                return;
            }

            match start_sidecar(&app, &capability_token) {
                Ok(child) => {
                    let Some(state) = app.try_state::<SidecarProcess>() else {
                        return;
                    };
                    if state.shutting_down.load(Ordering::Acquire) {
                        if let Some(mut child) = child {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                        return;
                    }
                    *state.child.lock().expect("sidecar state poisoned") = child;
                    last_started = Instant::now();
                    append_supervisor_log(&app, "restart-ready");
                }
                Err(error) => {
                    consecutive_failures = consecutive_failures.saturating_add(1);
                    append_supervisor_log(
                        &app,
                        &format!(
                            "restart-failed code={} consecutive={consecutive_failures}",
                            sidecar_error_code(&error)
                        ),
                    );
                }
            }
        }
    });
}

fn packaged_sidecar_path(resource_dir: &Path) -> PathBuf {
    resource_dir
        .join(SIDECAR_RESOURCE_DIR)
        .join(SIDECAR_BUNDLE_DIR)
        .join(SIDECAR_EXE)
}

#[cfg(debug_assertions)]
fn development_sidecar_launch() -> Option<SidecarLaunch> {
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR")).ancestors().nth(3)?;
    let executable = project_root.join(".venv").join("Scripts").join("python.exe");
    let working_dir = project_root.join("services").join("local-api");
    if !executable.is_file() || !working_dir.is_dir() {
        return None;
    }
    Some(SidecarLaunch {
        executable,
        args: vec![
            "-m".to_owned(),
            "uvicorn".to_owned(),
            "zhangwen.main:app".to_owned(),
            "--port".to_owned(),
            SIDECAR_PORT.to_string(),
            "--host".to_owned(),
            SIDECAR_HOST.to_owned(),
        ],
        working_dir,
        source: "development",
    })
}

#[cfg(not(debug_assertions))]
fn development_sidecar_launch() -> Option<SidecarLaunch> {
    None
}

fn resolve_sidecar_launch<R: Runtime>(app: &AppHandle<R>) -> Option<SidecarLaunch> {
    // Development must not pick up a previously packaged 700+ MB bundle copied
    // into target/debug: antivirus scanning that bundle can delay health by tens
    // of seconds. Release builds return None from this helper and use resources.
    if let Some(launch) = development_sidecar_launch() {
        return Some(launch);
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        let executable = packaged_sidecar_path(&resource_dir);
        if executable.is_file() {
            let working_dir = executable.parent()?.to_path_buf();
            return Some(SidecarLaunch {
                executable,
                args: vec!["serve".to_owned()],
                working_dir,
                source: "packaged",
            });
        }
    }
    None
}

#[cfg(debug_assertions)]
fn configured_sidecar_data_dir() -> Option<PathBuf> {
    env::var_os("ZHANGWEN_DATA_DIR")
        .map(PathBuf::from)
        .filter(|path| !path.as_os_str().is_empty())
}

#[cfg(not(debug_assertions))]
fn configured_sidecar_data_dir() -> Option<PathBuf> {
    None
}

fn sidecar_data_dir<R: Runtime>(app: &AppHandle<R>) -> Option<PathBuf> {
    if let Some(configured) = configured_sidecar_data_dir() {
        return Some(configured);
    }
    app.path().local_data_dir().ok().map(|path| path.join(APP_DATA_DIR))
}

fn start_sidecar<R: Runtime>(
    app: &AppHandle<R>,
    capability_token: &str,
) -> Result<Option<Child>, String> {
    if sidecar_capability_matches(capability_token) {
        return Ok(None);
    }
    if connect_to_sidecar().is_some() {
        return Err(format!(
            "Sidecar port {SIDECAR_PORT} is already used by another local process. Close the existing application before starting Zhangwen."
        ));
    }
    let Some(launch) = resolve_sidecar_launch(app) else {
        return Err(
            "Packaged Sidecar and development Python runtime are unavailable.".to_owned(),
        );
    };
    let Some(data_dir) = sidecar_data_dir(app) else {
        return Err("Cannot resolve the user data directory for the Sidecar.".to_owned());
    };
    if let Err(error) = std::fs::create_dir_all(&data_dir) {
        return Err(format!("Cannot create the Sidecar user data directory: {error}"));
    }
    let log_dir = data_dir.join("logs");
    let mut process_log = open_sidecar_log(&log_dir)?;
    let stdout_log = process_log
        .try_clone()
        .map_err(|error| format!("Cannot prepare Sidecar stdout logging: {error}"))?;
    let stderr_log = process_log
        .try_clone()
        .map_err(|error| format!("Cannot prepare Sidecar stderr logging: {error}"))?;
    append_sidecar_log(&mut process_log, &format!("spawn source={}", launch.source));

    match Command::new(&launch.executable)
        .args(&launch.args)
        .current_dir(&launch.working_dir)
        .env("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", capability_token)
        .env("ZHANGWEN_DATA_DIR", &data_dir)
        .env("ZHANGWEN_SIDECAR_PORT", SIDECAR_PORT.to_string())
        .env("PYTHONUTF8", "1")
        .stdout(Stdio::from(stdout_log))
        .stderr(Stdio::from(stderr_log))
        .spawn()
    {
        Ok(mut child) => {
            let pid = child.id();
            append_sidecar_log(&mut process_log, &format!("started pid={pid}"));
            match wait_for_sidecar(
                &mut child,
                capability_token,
                SIDECAR_READY_TIMEOUT_SECS,
            ) {
                SidecarWaitResult::Ready => {
                    append_sidecar_log(&mut process_log, &format!("ready pid={pid}"));
                    Ok(Some(child))
                }
                SidecarWaitResult::Exited(code) => {
                    append_sidecar_log(
                        &mut process_log,
                        &format!("exited-before-ready pid={pid} code={code:?}"),
                    );
                    Err(format!(
                        "Sidecar exited before becoming ready (exit code {code:?}). See the local Sidecar process log."
                    ))
                }
                SidecarWaitResult::TimedOut => {
                    append_sidecar_log(&mut process_log, &format!("ready-timeout pid={pid}"));
                    let _ = child.kill();
                    let _ = child.wait();
                    Err(format!(
                        "Sidecar failed to become ready within {SIDECAR_READY_TIMEOUT_SECS} seconds. See the local Sidecar process log."
                    ))
                }
            }
        }
        Err(error) => {
            append_sidecar_log(&mut process_log, &format!("spawn-failed error={error}"));
            Err(format!("Sidecar failed to start: {error}"))
        }
    }
}

#[tauri::command]
fn get_desktop_capability_token(state: tauri::State<'_, DesktopCapabilityToken>) -> String {
    state.0.clone()
}

#[cfg(debug_assertions)]
fn capability_token() -> String {
    env::var("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| Uuid::new_v4().simple().to_string())
}

#[cfg(not(debug_assertions))]
fn capability_token() -> String {
    Uuid::new_v4().simple().to_string()
}

pub fn run() {
    let capability_token = capability_token();
    let setup_token = capability_token.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .manage(SidecarProcess::new())
        .manage(DesktopCapabilityToken(capability_token))
        .invoke_handler(tauri::generate_handler![get_desktop_capability_token])
        .setup(move |app| {
            if let (Some(window), Some(icon)) = (
                app.get_webview_window("main"),
                app.default_window_icon().cloned(),
            ) {
                window.set_icon(icon)?;
            }
            match start_sidecar(app.handle(), &setup_token) {
                Ok(child) => {
                    if let Some(state) = app.try_state::<SidecarProcess>() {
                        *state.child.lock().expect("sidecar state poisoned") = child;
                    }
                }
                Err(error) => append_supervisor_log(
                    app.handle(),
                    &format!("initial-start-failed code={}", sidecar_error_code(&error)),
                ),
            }
            supervise_sidecar(app.handle().clone(), setup_token.clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let app = window.app_handle();
                if let Some(state) = app.try_state::<SidecarProcess>() {
                    state.shutting_down.store(true, Ordering::Release);
                    if let Some(mut child) = state.child.lock().unwrap().take() {
                        let _ = child.kill();
                        let _ = child.wait();
                        eprintln!("Sidecar: process killed on window close.");
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("failed to start Zhangwen desktop app");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packaged_sidecar_path_stays_inside_resource_directory() {
        let resource_dir = Path::new("C:/Program Files/Zhangwen");
        assert_eq!(
            packaged_sidecar_path(resource_dir),
            resource_dir
                .join("sidecar")
                .join("zhangwen-sidecar")
                .join("zhangwen-sidecar.exe")
        );
    }

    #[test]
    fn capability_token_rejects_header_injection() {
        assert!(!sidecar_capability_matches("token\r\nInjected: yes"));
    }

    #[test]
    fn restart_delay_is_bounded() {
        assert_eq!(restart_delay(1), Duration::from_secs(1));
        assert_eq!(restart_delay(3), Duration::from_secs(4));
        assert_eq!(restart_delay(50), Duration::from_secs(30));
    }

    #[test]
    fn restart_budget_is_finite() {
        assert_eq!(MAX_CONSECUTIVE_SIDECAR_FAILURES, 6);
        assert!(MAX_CONSECUTIVE_SIDECAR_FAILURES < u32::MAX);
        assert_eq!(SIDECAR_READY_TIMEOUT_SECS, 120);
    }

    #[test]
    fn sidecar_errors_are_logged_as_redacted_codes() {
        assert_eq!(
            sidecar_error_code("Sidecar port 8100 is already used by another local process."),
            "port-in-use"
        );
        assert_eq!(
            sidecar_error_code("Packaged Sidecar and development Python runtime are unavailable."),
            "runtime-unavailable"
        );
    }
}
