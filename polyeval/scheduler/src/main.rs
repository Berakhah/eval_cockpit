//! PolyEval scheduler — Slice 1: Redis Streams consumer + Docker runner dispatcher.
//! Reads from `eval:queue`, runs all trials per submission, bundles results,
//! writes to `trial_results`. Spec §5, §7.2, §7.3.

use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::Arc,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{anyhow, Context};
use axum::{extract::State as AxumState, routing::get, Json, Router};
use prometheus::{
    Histogram, HistogramOpts, HistogramVec, IntCounter, IntCounterVec, IntGauge, Opts, Registry,
    TextEncoder,
};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use tokio::{net::TcpListener, signal, sync::Semaphore, time};
use tracing::{error, info, instrument, warn};

const SERVICE_NAME: &str = "polyeval-scheduler";
const EVAL_QUEUE: &str = "eval:queue";
const TRIAL_RESULTS: &str = "trial_results";
const EVAL_DLQ: &str = "eval:dlq";
const CONSUMER_GROUP: &str = "schedulers";
// Field name used by both the API (producer) and aggregator (consumer).
const STREAM_FIELD: &str = "data";

// ─── Config ───────────────────────────────────────────────────────────────────

#[derive(Clone)]
struct Config {
    redis_url: String,
    bind: SocketAddr,
    runner_runtime: String,
    max_concurrent: usize,
    consumer_name: String,
    version: &'static str,
}

impl Config {
    fn from_env() -> anyhow::Result<Self> {
        let bind: SocketAddr = std::env::var("POLYEVAL_SCHEDULER_BIND")
            .unwrap_or_else(|_| "0.0.0.0:8001".to_string())
            .parse()
            .context("POLYEVAL_SCHEDULER_BIND must be a valid socket address")?;
        let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| "scheduler".to_string());
        Ok(Self {
            redis_url: std::env::var("POLYEVAL_REDIS_URL")
                .unwrap_or_else(|_| "redis://redis:6379/0".to_string()),
            bind,
            runner_runtime: std::env::var("POLYEVAL_RUNNER_RUNTIME")
                .unwrap_or_else(|_| "runc".to_string()),
            max_concurrent: std::env::var("POLYEVAL_MAX_CONCURRENT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(4),
            consumer_name: format!("scheduler-{hostname}"),
            version: env!("CARGO_PKG_VERSION"),
        })
    }
}

// ─── Metrics ──────────────────────────────────────────────────────────────────

#[derive(Clone)]
struct Metrics {
    registry: Arc<Registry>,
    jobs_dispatched: IntCounter,
    jobs_failed: IntCounter,
    jobs_active: IntGauge,
    trial_wall_seconds: HistogramVec,
    sandbox_violations: IntCounterVec,
}

impl Metrics {
    fn new() -> anyhow::Result<Self> {
        let registry = Registry::new();
        let jobs_dispatched = IntCounter::new(
            "scheduler_jobs_dispatched_total",
            "Total submission jobs dispatched",
        )?;
        let jobs_failed =
            IntCounter::new("scheduler_jobs_failed_total", "Total submission jobs failed (DLQ)")?;
        let jobs_active = IntGauge::new("scheduler_jobs_active", "Currently running jobs")?;

        let buckets = vec![0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0];
        let trial_wall_seconds = HistogramVec::new(
            HistogramOpts::new(
                "scheduler_trial_wall_seconds",
                "External wall time per trial measured by scheduler",
            )
            .buckets(buckets),
            &["language"],
        )?;

        let sandbox_violations = IntCounterVec::new(
            Opts::new(
                "scheduler_sandbox_violations_total",
                "Trials that triggered seccomp KILL (exit 159) by language",
            ),
            &["language"],
        )?;

        registry.register(Box::new(jobs_dispatched.clone()))?;
        registry.register(Box::new(jobs_failed.clone()))?;
        registry.register(Box::new(jobs_active.clone()))?;
        registry.register(Box::new(trial_wall_seconds.clone()))?;
        registry.register(Box::new(sandbox_violations.clone()))?;
        Ok(Self {
            registry: Arc::new(registry),
            jobs_dispatched,
            jobs_failed,
            jobs_active,
            trial_wall_seconds,
            sandbox_violations,
        })
    }
}

// ─── AppState ─────────────────────────────────────────────────────────────────

#[derive(Clone)]
struct AppState {
    config: Arc<Config>,
    redis: Arc<redis::Client>,
    semaphore: Arc<Semaphore>,
    metrics: Metrics,
}

// ─── Wire types (eval:queue → trial_results) ──────────────────────────────────

/// Matches the JSON the API writes into eval:queue["data"].
#[derive(Debug, Deserialize)]
struct QueueMessage {
    submission_id: String,
    language: String,
    trials: u32,
    timeout_seconds: f64,
    #[serde(default)]
    memory_limit_mb: u64,
    /// Seed for deterministic RNG per spec §7.3.
    #[serde(default = "default_seed")]
    determinism_seed: u64,
    test_suite: serde_json::Value,
    code: String,
}

fn default_seed() -> u64 { 0xCAFEF00D }

/// Single trial result from one docker run.
#[derive(Debug, Deserialize)]
struct RunnerOutput {
    #[allow(dead_code)]
    index: u32,
    mem_kb: u64,
    exit_code: i32,
    framework_passed: bool,
    sandbox_violation: bool,
    stderr_snippet: Option<String>,
}

/// One trial in the bundle written to trial_results.
#[derive(Debug, Serialize)]
struct TrialEntry {
    index: u32,
    wall_ns: u64,
    mem_kb: u64,
    exit_code: i32,
    framework_passed: bool,
    sandbox_violation: bool,
    stderr_snippet: Option<String>,
}

/// Bundle written to trial_results["data"] — aggregator reads this.
#[derive(Debug, Serialize)]
struct TrialBundle {
    submission_id: String,
    runner_image_digest: &'static str,
    scheduler_version: &'static str,
    trials: Vec<TrialEntry>,
}

// ─── Main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing();
    let config = Arc::new(Config::from_env()?);
    let metrics = Metrics::new()?;
    let client = redis::Client::open(config.redis_url.as_str())
        .with_context(|| format!("opening redis at {}", config.redis_url))?;

    let state = AppState {
        redis: Arc::new(client),
        semaphore: Arc::new(Semaphore::new(config.max_concurrent)),
        metrics,
        config: config.clone(),
    };

    ensure_consumer_groups(&state).await?;
    tokio::spawn(recover_pending(state.clone()));
    tokio::spawn(run_consumer(state.clone()));

    let bind = config.bind;
    info!(%bind, service = SERVICE_NAME, version = config.version, "scheduler.listen");
    let listener = TcpListener::bind(bind).await?;
    axum::serve(listener, build_router(state))
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    Ok(())
}

fn build_router(state: AppState) -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .route("/readyz", get(readyz))
        .route("/metrics", get(metrics_handler))
        .with_state(state)
}

// ─── Consumer group bootstrap ─────────────────────────────────────────────────

async fn ensure_consumer_groups(state: &AppState) -> anyhow::Result<()> {
    let mut conn = state.redis.get_multiplexed_async_connection().await?;
    let r: Result<(), redis::RedisError> = redis::cmd("XGROUP")
        .arg("CREATE")
        .arg(EVAL_QUEUE)
        .arg(CONSUMER_GROUP)
        .arg("$")
        .arg("MKSTREAM")
        .query_async(&mut conn)
        .await;
    match r {
        Ok(_) => info!("scheduler.group_created"),
        Err(e) if e.to_string().contains("BUSYGROUP") => info!("scheduler.group_exists"),
        Err(e) => return Err(anyhow!("XGROUP CREATE: {e}")),
    }
    // Ensure aggregator group on trial_results (best-effort).
    let _: Result<(), _> = redis::cmd("XGROUP")
        .arg("CREATE")
        .arg(TRIAL_RESULTS)
        .arg("aggregators")
        .arg("$")
        .arg("MKSTREAM")
        .query_async(&mut conn)
        .await;
    Ok(())
}

// ─── Main consumer loop ───────────────────────────────────────────────────────

async fn run_consumer(state: AppState) {
    let mut backoff = Duration::from_millis(100);
    loop {
        match xread_batch(&state).await {
            Ok(0) => {
                backoff = backoff.min(Duration::from_secs(1));
                time::sleep(backoff).await;
            }
            Ok(n) => {
                backoff = Duration::from_millis(100);
                info!(count = n, "scheduler.batch_dispatched");
            }
            Err(e) => {
                error!(error = %e, "scheduler.consumer_error");
                time::sleep(backoff).await;
                backoff = (backoff * 2).min(Duration::from_secs(30));
            }
        }
    }
}

async fn xread_batch(state: &AppState) -> anyhow::Result<usize> {
    let mut conn = state.redis.get_multiplexed_async_connection().await?;
    let reply: redis::Value = redis::cmd("XREADGROUP")
        .arg("GROUP")
        .arg(CONSUMER_GROUP)
        .arg(&state.config.consumer_name)
        .arg("COUNT")
        .arg(4)
        .arg("BLOCK")
        .arg(2000)
        .arg("STREAMS")
        .arg(EVAL_QUEUE)
        .arg(">")
        .query_async(&mut conn)
        .await?;

    let messages = parse_xreadgroup_reply(reply);
    let count = messages.len();
    for (msg_id, fields) in messages {
        let permit = state.semaphore.clone().acquire_owned().await?;
        let st = state.clone();
        tokio::spawn(async move {
            let _permit = permit;
            process_message(st, msg_id, fields).await;
        });
    }
    Ok(count)
}

// ─── Crash recovery ───────────────────────────────────────────────────────────

async fn recover_pending(state: AppState) {
    time::sleep(Duration::from_secs(5)).await;
    loop {
        if let Err(e) = xautoclaim_once(&state).await {
            warn!(error = %e, "scheduler.recover_error");
        }
        time::sleep(Duration::from_secs(60)).await;
    }
}

async fn xautoclaim_once(state: &AppState) -> anyhow::Result<()> {
    let mut conn = state.redis.get_multiplexed_async_connection().await?;
    let reply: redis::Value = redis::cmd("XAUTOCLAIM")
        .arg(EVAL_QUEUE)
        .arg(CONSUMER_GROUP)
        .arg(&state.config.consumer_name)
        .arg(120_000u64) // 2-min idle threshold
        .arg("0-0")
        .arg("COUNT")
        .arg(4)
        .query_async(&mut conn)
        .await?;

    let messages = parse_xautoclaim_reply(reply);
    if !messages.is_empty() {
        info!(count = messages.len(), "scheduler.recover_claimed");
        for (msg_id, fields) in messages {
            let permit = state.semaphore.clone().acquire_owned().await?;
            let st = state.clone();
            tokio::spawn(async move {
                let _permit = permit;
                process_message(st, msg_id, fields).await;
            });
        }
    }
    Ok(())
}

// ─── Message processor ────────────────────────────────────────────────────────

#[instrument(skip(state, fields), fields(submission_id = tracing::field::Empty))]
async fn process_message(state: AppState, msg_id: String, fields: HashMap<String, String>) {
    let payload_str = match fields.get(STREAM_FIELD) {
        Some(s) => s.clone(),
        None => {
            error!(%msg_id, "scheduler.missing_data_field");
            dlq(&state, &msg_id, &fields, "missing 'data' field").await;
            return;
        }
    };

    let msg: QueueMessage = match serde_json::from_str(&payload_str) {
        Ok(m) => m,
        Err(e) => {
            error!(%msg_id, error = %e, "scheduler.bad_payload");
            dlq(&state, &msg_id, &fields, &format!("json parse: {e}")).await;
            return;
        }
    };

    tracing::Span::current().record("submission_id", msg.submission_id.as_str());

    state.metrics.jobs_dispatched.inc();
    state.metrics.jobs_active.inc();
    let result = run_all_trials(&state, &msg).await;
    state.metrics.jobs_active.dec();

    match result {
        Ok(bundle) => {
            if let Err(e) = xadd_bundle(&state, &bundle).await {
                error!(error = %e, submission_id = %msg.submission_id, "scheduler.xadd_failed");
                state.metrics.jobs_failed.inc();
                dlq(&state, &msg_id, &fields, &format!("xadd trial_results: {e}")).await;
                return;
            }
            xack(&state, &msg_id).await;
            let passed = bundle.trials.iter().filter(|t| t.framework_passed).count();
            info!(
                submission_id = %bundle.submission_id,
                total = bundle.trials.len(),
                passed,
                "scheduler.bundle_complete"
            );
        }
        Err(e) => {
            state.metrics.jobs_failed.inc();
            error!(error = %e, submission_id = %msg.submission_id, "scheduler.run_failed");
            dlq(&state, &msg_id, &fields, &format!("run: {e}")).await;
        }
    }
}

// ─── Trial execution ──────────────────────────────────────────────────────────

async fn run_all_trials(state: &AppState, msg: &QueueMessage) -> anyhow::Result<TrialBundle> {
    let image = runner_image(&msg.language)?;
    let timeout_s = (msg.timeout_seconds as u64).max(5).min(60);
    let memory_mb = msg.memory_limit_mb.max(32).min(1024);

    // Languages with a separate untimed compile phase before running trials.
    if matches!(msg.language.as_str(), "rust" | "java" | "cpp") {
        return run_all_trials_two_phase(state, msg, image, timeout_s, memory_mb).await;
    }

    let mut entries = Vec::with_capacity(msg.trials as usize);
    for trial_index in 0..msg.trials {
        // Per-trial seed: XOR base seed with trial index for determinism (spec §7.3).
        let seed = format!("{:016x}", msg.determinism_seed ^ (trial_index as u64));
        let entry = run_one_trial(state, msg, image, trial_index, &seed, timeout_s, memory_mb)
            .await
            .unwrap_or_else(|e| {
                warn!(
                    submission_id = %msg.submission_id,
                    trial_index,
                    error = %e,
                    "scheduler.trial_error"
                );
                TrialEntry {
                    index: trial_index,
                    wall_ns: 0,
                    mem_kb: 0,
                    exit_code: 1,
                    framework_passed: false,
                    sandbox_violation: false,
                    stderr_snippet: Some(format!("runner error: {e}")),
                }
            });
        record_trial_metrics(&state.metrics, &msg.language, &entry);
        entries.push(entry);
    }

    Ok(TrialBundle {
        submission_id: msg.submission_id.clone(),
        runner_image_digest: "sha256:dev",
        scheduler_version: state.config.version,
        trials: entries,
    })
}

fn record_trial_metrics(metrics: &Metrics, language: &str, entry: &TrialEntry) {
    metrics
        .trial_wall_seconds
        .with_label_values(&[language])
        .observe(entry.wall_ns as f64 / 1e9);
    if entry.sandbox_violation {
        metrics.sandbox_violations.with_label_values(&[language]).inc();
    }
}

/// Two-phase execution: compile once (untimed), then run N trials (timed externally).
/// Used for rust, java, and cpp.
async fn run_all_trials_two_phase(
    state: &AppState,
    msg: &QueueMessage,
    image: &str,
    timeout_s: u64,
    memory_mb: u64,
) -> anyhow::Result<TrialBundle> {
    // Shared build directory: both compile and run containers bind-mount it.
    let build_dir = tempfile::tempdir().context("creating Rust build dir")?;

    // Make world-writable so UID 65534 inside the container can write to it.
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(
            build_dir.path(),
            std::fs::Permissions::from_mode(0o777),
        )
        .context("chmod 777 build dir")?;
    }

    let build_path = build_dir
        .path()
        .to_str()
        .ok_or_else(|| anyhow!("non-UTF8 build dir path"))?
        .to_string();

    // Write manifest.json to the shared dir.
    let manifest = serde_json::json!({
        "code": msg.code,
        "test_suite": msg.test_suite,
        "trial_index": 0,
    });
    std::fs::write(
        build_dir.path().join("manifest.json"),
        serde_json::to_string(&manifest)?,
    )
    .context("writing Rust manifest.json")?;

    // Phase 1: compile (untimed). Allow up to 2× run timeout for compilation.
    let compile_timeout_s = (timeout_s * 2).max(120);
    run_compile_container(state, msg, image, &build_path, compile_timeout_s, memory_mb)
        .await
        .context("compile phase")?;

    info!(
        submission_id = %msg.submission_id,
        language = %msg.language,
        "scheduler.compiled"
    );

    // Phase 2: run N trials (timed externally).
    let mut entries = Vec::with_capacity(msg.trials as usize);
    for trial_index in 0..msg.trials {
        let seed = format!("{:016x}", msg.determinism_seed ^ (trial_index as u64));

        // Overwrite trial_index in manifest.json for this trial.
        let trial_manifest = serde_json::json!({
            "code": msg.code,
            "test_suite": msg.test_suite,
            "trial_index": trial_index,
        });
        let _ = std::fs::write(
            build_dir.path().join("manifest.json"),
            serde_json::to_string(&trial_manifest)?,
        );

        let entry = run_one_trial_two_phase(state, msg, image, trial_index, &seed, timeout_s, memory_mb, &build_path)
            .await
            .unwrap_or_else(|e| {
                warn!(
                    submission_id = %msg.submission_id,
                    trial_index,
                    error = %e,
                    "scheduler.trial_error"
                );
                TrialEntry {
                    index: trial_index,
                    wall_ns: 0,
                    mem_kb: 0,
                    exit_code: 1,
                    framework_passed: false,
                    sandbox_violation: false,
                    stderr_snippet: Some(format!("runner error: {e}")),
                }
            });
        record_trial_metrics(&state.metrics, &msg.language, &entry);
        entries.push(entry);
    }

    Ok(TrialBundle {
        submission_id: msg.submission_id.clone(),
        runner_image_digest: "sha256:dev",
        scheduler_version: state.config.version,
        trials: entries,
    })
}

/// Run the compile container (untimed). Returns Ok(()) on exit code 0.
async fn run_compile_container(
    state: &AppState,
    msg: &QueueMessage,
    image: &str,
    build_path: &str,
    compile_timeout_s: u64,
    memory_mb: u64,
) -> anyhow::Result<()> {
    // Rust/cargo needs large /tmp for incremental build artifacts.
    let tmpfs_size = if msg.language == "rust" { "512m" } else { "64m" };

    let mut cmd = tokio::process::Command::new("docker");
    cmd.args([
        "run", "--rm",
        "--runtime", &state.config.runner_runtime,
        "--cap-drop=ALL",
        "--network", "none",
        "--user", "65534:65534",
        "--memory", &format!("{memory_mb}m"),
        "--memory-swap", &format!("{memory_mb}m"),
        "--cpus", "1",
        "--tmpfs", &format!("/tmp:size={tmpfs_size}"),
        "-v", &format!("{build_path}:/work:rw"),
        "-e", "POLYEVAL_PHASE=compile",
        "-e", &format!("POLYEVAL_COMPILE_TIMEOUT_S={compile_timeout_s}"),
        image,
    ]);

    let output = time::timeout(
        Duration::from_secs(compile_timeout_s + 30),
        cmd.output(),
    )
    .await
    .with_context(|| format!("compile container timed out after {compile_timeout_s}s"))?
    .context("docker run compile")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let stdout = String::from_utf8_lossy(&output.stdout);
        return Err(anyhow!(
            "compile failed (exit {}): stderr={} stdout={}",
            output.status,
            &stderr[..stderr.len().min(512)],
            &stdout[..stdout.len().min(512)],
        ));
    }
    Ok(())
}

/// Run one execution trial for a two-phase language (timed externally).
async fn run_one_trial_two_phase(
    state: &AppState,
    msg: &QueueMessage,
    image: &str,
    trial_index: u32,
    seed: &str,
    timeout_s: u64,
    memory_mb: u64,
    build_path: &str,
) -> anyhow::Result<TrialEntry> {
    let mut cmd = tokio::process::Command::new("docker");
    cmd.args([
        "run", "--rm",
        "--runtime", &state.config.runner_runtime,
        "--cap-drop=ALL",
        "--network", "none",
        "--user", "65534:65534",
        "--memory", &format!("{memory_mb}m"),
        "--memory-swap", &format!("{memory_mb}m"),
        "--cpus", "1",
        "--read-only",
        "--tmpfs", "/tmp:size=32m",
        "-v", &format!("{build_path}:/work:ro"),
        "-e", "POLYEVAL_PHASE=run",
        "-e", &format!("POLYEVAL_SEED={seed}"),
        "-e", &format!("POLYEVAL_TIMEOUT_S={timeout_s}"),
        image,
    ]);

    let t0 = Instant::now();
    let output = time::timeout(
        Duration::from_secs(timeout_s + 10),
        cmd.output(),
    )
    .await
    .with_context(|| format!("docker run timed out after {}s", timeout_s + 10))?
    .context("docker run two-phase trial")?;
    let wall_ns = t0.elapsed().as_nanos() as u64;

    parse_trial_output(output, trial_index, wall_ns)
}

async fn run_one_trial(
    state: &AppState,
    msg: &QueueMessage,
    image: &str,
    trial_index: u32,
    seed: &str,
    timeout_s: u64,
    memory_mb: u64,
) -> anyhow::Result<TrialEntry> {
    // Build manifest for this trial.
    let manifest = serde_json::json!({
        "code": msg.code,
        "test_suite": msg.test_suite,
        "trial_index": trial_index,
    });

    let work_dir = tempfile::tempdir().context("creating tempdir")?;
    std::fs::write(
        work_dir.path().join("manifest.json"),
        serde_json::to_string(&manifest)?,
    )
    .context("writing manifest.json")?;
    let work_path = work_dir
        .path()
        .to_str()
        .ok_or_else(|| anyhow!("non-UTF8 tempdir path"))?
        .to_string();

    let mut cmd = tokio::process::Command::new("docker");
    cmd.args([
        "run",
        "--rm",
        "--runtime",
        &state.config.runner_runtime,
        "--cap-drop=ALL",
        "--network",
        "none",
        "--user",
        "65534:65534",
        "--memory",
        &format!("{memory_mb}m"),
        "--memory-swap",
        &format!("{memory_mb}m"),
        "--cpus",
        "1",
        "--read-only",
        "--tmpfs",
        "/tmp:size=32m",
        "-v",
        &format!("{work_path}:/work:rw"),
        "-e",
        &format!("POLYEVAL_SEED={seed}"),
        "-e",
        &format!("POLYEVAL_TIMEOUT_S={timeout_s}"),
        image,
    ]);

    // External wallclock — authoritative per spec §7.3.
    let t0 = Instant::now();
    let output = time::timeout(
        Duration::from_secs(timeout_s + 10),
        cmd.output(),
    )
    .await
    .with_context(|| format!("docker timed out after {}s", timeout_s + 10))?
    .context("docker run")?;
    let wall_ns = t0.elapsed().as_nanos() as u64;

    parse_trial_output(output, trial_index, wall_ns)
}

/// Parse docker output into a TrialEntry.
/// Exit 159 = SIGSYS from seccomp SCMP_ACT_KILL — treated as sandbox_violation.
fn parse_trial_output(
    output: std::process::Output,
    trial_index: u32,
    wall_ns: u64,
) -> anyhow::Result<TrialEntry> {
    let exit_code = output.status.code().unwrap_or(1);

    // SIGSYS (signal 31, exit 159 = 128+31) means seccomp blocked a dangerous syscall.
    if exit_code == 159 {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Ok(TrialEntry {
            index: trial_index,
            wall_ns,
            mem_kb: 0,
            exit_code: 159,
            framework_passed: false,
            sandbox_violation: true,
            stderr_snippet: Some(format!("seccomp_kill: {}", &stderr[..stderr.len().min(256)])),
        });
    }

    if !output.status.success() && output.stdout.is_empty() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("docker exit {}: {}", output.status, &stderr[..stderr.len().min(256)]));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let runner: RunnerOutput = serde_json::from_str(stdout.trim())
        .with_context(|| format!("parse stdout: {:?}", &stdout[..stdout.len().min(200)]))?;

    Ok(TrialEntry {
        index: trial_index,
        wall_ns,
        mem_kb: runner.mem_kb,
        exit_code: runner.exit_code,
        // Merge: runner may self-report sandbox_violation; also catch SIGSYS from seccomp.
        framework_passed: runner.framework_passed && !runner.sandbox_violation,
        sandbox_violation: runner.sandbox_violation,
        stderr_snippet: runner.stderr_snippet,
    })
}

fn runner_image(language: &str) -> anyhow::Result<&'static str> {
    match language {
        "python" => Ok("polyeval/runner-python:latest"),
        "javascript" => Ok("polyeval/runner-javascript:latest"),
        "java" => Ok("polyeval/runner-java:latest"),
        "cpp" => Ok("polyeval/runner-cpp:latest"),
        "rust" => Ok("polyeval/runner-rust:latest"),
        other => Err(anyhow!("unknown language: {other}")),
    }
}

// ─── Redis helpers ────────────────────────────────────────────────────────────

async fn xadd_bundle(state: &AppState, bundle: &TrialBundle) -> anyhow::Result<()> {
    let mut conn = state.redis.get_multiplexed_async_connection().await?;
    let payload = serde_json::to_string(bundle)?;
    redis::cmd("XADD")
        .arg(TRIAL_RESULTS)
        .arg("*")
        .arg(STREAM_FIELD)
        .arg(&payload)
        .query_async::<_, String>(&mut conn)
        .await
        .context("XADD trial_results")?;
    Ok(())
}

async fn xack(state: &AppState, msg_id: &str) {
    if let Ok(mut conn) = state.redis.get_multiplexed_async_connection().await {
        let _: Result<(), _> = redis::cmd("XACK")
            .arg(EVAL_QUEUE)
            .arg(CONSUMER_GROUP)
            .arg(msg_id)
            .query_async(&mut conn)
            .await;
    }
}

async fn dlq(state: &AppState, msg_id: &str, fields: &HashMap<String, String>, reason: &str) {
    state.metrics.jobs_failed.inc();
    if let Ok(mut conn) = state.redis.get_multiplexed_async_connection().await {
        let v = serde_json::json!({
            "original_id": msg_id,
            "fields": fields,
            "reason": reason,
            "ts": unix_ms_now(),
        });
        let _: Result<(), _> = redis::cmd("XADD")
            .arg(EVAL_DLQ)
            .arg("*")
            .arg(STREAM_FIELD)
            .arg(v.to_string())
            .query_async(&mut conn)
            .await;
        let _: Result<(), _> = redis::cmd("XACK")
            .arg(EVAL_QUEUE)
            .arg(CONSUMER_GROUP)
            .arg(msg_id)
            .query_async(&mut conn)
            .await;
    }
}

// ─── Redis reply parsers ──────────────────────────────────────────────────────

fn parse_xreadgroup_reply(reply: redis::Value) -> Vec<(String, HashMap<String, String>)> {
    let mut out = Vec::new();
    if let redis::Value::Array(streams) = reply {
        for stream in streams {
            if let redis::Value::Array(mut sd) = stream {
                if sd.len() < 2 { continue; }
                if let redis::Value::Array(msgs) = sd.remove(1) {
                    for msg in msgs {
                        if let redis::Value::Array(mut parts) = msg {
                            if parts.len() < 2 { continue; }
                            let id = val_str(parts.remove(0));
                            let fields = val_fields(parts.remove(0));
                            out.push((id, fields));
                        }
                    }
                }
            }
        }
    }
    out
}

fn parse_xautoclaim_reply(reply: redis::Value) -> Vec<(String, HashMap<String, String>)> {
    let mut out = Vec::new();
    if let redis::Value::Array(parts) = reply {
        if parts.len() < 2 { return out; }
        if let redis::Value::Array(msgs) = &parts[1] {
            for msg in msgs {
                if let redis::Value::Array(mp) = msg {
                    if mp.len() < 2 { continue; }
                    let id = val_str(mp[0].clone());
                    let fields = val_fields(mp[1].clone());
                    out.push((id, fields));
                }
            }
        }
    }
    out
}

fn val_fields(val: redis::Value) -> HashMap<String, String> {
    let mut map = HashMap::new();
    if let redis::Value::Array(pairs) = val {
        let mut it = pairs.into_iter();
        while let (Some(k), Some(v)) = (it.next(), it.next()) {
            map.insert(val_str(k), val_str(v));
        }
    }
    map
}

fn val_str(val: redis::Value) -> String {
    match val {
        redis::Value::BulkString(b) => String::from_utf8_lossy(&b).into_owned(),
        redis::Value::SimpleString(s) => s,
        redis::Value::Int(n) => n.to_string(),
        _ => String::new(),
    }
}

// ─── HTTP handlers ────────────────────────────────────────────────────────────

#[derive(Serialize)]
struct Health {
    status: &'static str,
    service: &'static str,
    version: &'static str,
}

async fn healthz() -> Json<Health> {
    Json(Health { status: "ok", service: SERVICE_NAME, version: env!("CARGO_PKG_VERSION") })
}

async fn readyz(AxumState(state): AxumState<AppState>) -> Json<serde_json::Value> {
    let redis_ok = match state.redis.get_multiplexed_async_connection().await {
        Ok(mut c) => redis::cmd("PING").query_async::<_, String>(&mut c).await.is_ok(),
        Err(_) => false,
    };
    Json(serde_json::json!({
        "status": if redis_ok { "ok" } else { "degraded" },
        "service": SERVICE_NAME,
        "checks": { "redis": if redis_ok { "ok" } else { "fail" } },
    }))
}

async fn metrics_handler(AxumState(state): AxumState<AppState>) -> String {
    let encoder = TextEncoder::new();
    let mfs = state.metrics.registry.gather();
    encoder.encode_to_string(&mfs).unwrap_or_default()
}

// ─── Utilities ────────────────────────────────────────────────────────────────

fn init_tracing() {
    use tracing_subscriber::{fmt, prelude::*, EnvFilter};
    let filter = EnvFilter::try_from_default_env()
        .or_else(|_| EnvFilter::try_new("info"))
        .unwrap();
    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer().json().with_current_span(true))
        .init();
}

async fn shutdown_signal() {
    let ctrl_c = async { let _ = signal::ctrl_c().await; };
    #[cfg(unix)]
    let term = async {
        use signal::unix::{signal, SignalKind};
        let mut s = signal(SignalKind::terminate()).expect("SIGTERM handler");
        s.recv().await;
    };
    #[cfg(not(unix))]
    let term = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {},
        _ = term => {},
    }
    info!("scheduler.shutdown");
}

fn unix_ms_now() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as u64
}
