# runners/rust

Rust 1.83 runner. Slice 4. Framework: `cargo test --no-fail-fast --message-format=json`.

Distinct from `polyeval/scheduler` (also Rust) — this image runs untrusted user code
inside the sandbox; the scheduler is a trusted long-lived service.
