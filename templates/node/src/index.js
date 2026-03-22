'use strict';

/**
 * {{PROJECT_NAME}} — {{DESCRIPTION}}
 * Autor: {{AUTHOR}}, {{YEAR}}
 */

async function main() {
  console.log('{{PROJECT_NAME}} v0.1.0');
  console.log('{{DESCRIPTION}}');
}

main().catch((err) => {
  console.error('[ERROR]', err.message);
  process.exit(1);
});
