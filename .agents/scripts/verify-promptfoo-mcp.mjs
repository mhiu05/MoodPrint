import { spawn } from 'node:child_process';

const command = process.platform === 'win32' ? 'cmd.exe' : 'npx';
const args = process.platform === 'win32'
  ? ['/d', '/s', '/c', 'npx.cmd --yes promptfoo@0.125.1 mcp --transport stdio']
  : ['--yes', 'promptfoo@0.125.1', 'mcp', '--transport', 'stdio'];
const child = spawn(command, args, {
  cwd: process.cwd(),
  windowsHide: true,
  stdio: ['pipe', 'pipe', 'pipe'],
});

let stdoutBuffer = '';
let stderrBuffer = '';
let nextId = 0;
const pending = new Map();

child.stdout.setEncoding('utf8');
child.stderr.setEncoding('utf8');
child.stdout.on('data', (chunk) => {
  stdoutBuffer += chunk;
  let newline = stdoutBuffer.indexOf('\n');
  while (newline >= 0) {
    const line = stdoutBuffer.slice(0, newline).trim();
    stdoutBuffer = stdoutBuffer.slice(newline + 1);
    newline = stdoutBuffer.indexOf('\n');
    if (!line) continue;
    try {
      const message = JSON.parse(line);
      const waiter = pending.get(message.id);
      if (waiter) {
        clearTimeout(waiter.timer);
        pending.delete(message.id);
        waiter.resolve(message);
      }
    } catch {
      // Ignore non-protocol output; the CLI writes diagnostics to stderr.
    }
  }
});
child.stderr.on('data', (chunk) => {
  stderrBuffer += chunk;
});

function request(method, params) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timed out waiting for MCP ${method} response`));
    }, 20000);
    pending.set(id, { resolve, reject, timer });
    child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
  });
}

async function closeServer() {
  const exited = new Promise((resolve) => {
    if (child.exitCode !== null) resolve(child.exitCode);
    else child.once('exit', resolve);
  });
  child.stdin.end(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/exit' })}\n`);
  const timeout = setTimeout(() => child.kill(), 5000);
  await exited;
  clearTimeout(timeout);
}

try {
  const initialize = await request('initialize', {
    protocolVersion: '2025-06-18',
    capabilities: {},
    clientInfo: { name: 'moodprint-promptfoo-smoke', version: '1.0.0' },
  });
  if (initialize.error) throw new Error('Promptfoo MCP initialization failed');
  child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);

  const discovery = await request('tools/list', {});
  const tools = discovery.result?.tools ?? [];
  const names = tools.map((tool) => tool.name);
  if (!names.includes('list_evaluations')) {
    throw new Error('Promptfoo MCP did not expose the read-only list_evaluations tool');
  }

  const smoke = await request('tools/call', {
    name: 'list_evaluations',
    arguments: {},
  });
  if (smoke.error || smoke.result?.isError) {
    throw new Error('Promptfoo MCP read-only tool call failed');
  }

  console.log(JSON.stringify({
    initialized: true,
    discoveredToolCount: tools.length,
    readOnlyTool: 'list_evaluations',
    readOnlyCall: 'passed',
  }));
} catch (error) {
  console.error(JSON.stringify({
    error: error.message,
    stderrBytes: Buffer.byteLength(stderrBuffer),
  }));
  process.exitCode = 1;
} finally {
  await closeServer();
}
