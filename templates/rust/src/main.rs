//! {{PROJECT_NAME}} — {{DESCRIPTION}}
//! Autor: {{AUTHOR}}, {{YEAR}}

use std::process;

fn run() -> Result<(), Box<dyn std::error::Error>> {
    println!("{{PROJECT_NAME}} v0.1.0");
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("[ERROR] {}", e);
        process::exit(1);
    }
}
