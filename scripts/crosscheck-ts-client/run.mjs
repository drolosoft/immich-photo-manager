// Cross-implementation check: the TypeScript MCP SDK v2 client against this
// Python server, over stdio and Streamable HTTP, in legacy / auto / pinned
// 2026-07-28 modes. See README.md in this folder.
import { Client, StreamableHTTPClientTransport } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';

import { fileURLToPath } from 'node:url';
import path from 'node:path';
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const PY = process.env.PYTHON || REPO + '/.venv/bin/python';
const env = { ...process.env, PYTHONPATH: REPO + '/src', IMMICH_BASE_URL: process.env.IMMICH_BASE_URL || process.env.FAKE_IMMICH, IMMICH_API_KEY: process.env.IMMICH_API_KEY || 'fake-immich-key-0123456789abcdef' };
const modes = [ 'legacy', 'auto', { pin: '2026-07-28' } ];

async function exercise(label, mkTransport, mode) {
  const client = new Client({ name: 'ts-v2-crosscheck', version: '1.0.0' }, { versionNegotiation: { mode } });
  await client.connect(mkTransport());
  const tools = await client.listTools();
  const info = await client.callTool({ name: 'get_connection_info', arguments: {} });
  const batch = await client.callTool({ name: 'get_thumbnails_batch', arguments: { asset_ids: ['a1','a2'] } });
  const parsed = JSON.parse(batch.content.find(b => b.type === 'text').text);
  const b64ok = parsed.thumbnails.length === 2 && parsed.thumbnails.every(t => t.data === process.env.PNG_B64 && t.originalFileName && t.fileCreatedAt);
  const img = await client.callTool({ name: 'get_asset_image', arguments: { asset_id: 'a1' } });
  const imgok = img.content.some(b => b.type === 'image' && b.mimeType === 'image/png');
  console.log(`  ${label.padEnd(6)} mode=${JSON.stringify(mode).padEnd(20)} -> negotiated=${client.getNegotiatedProtocolVersion()} tools=${tools.tools.length} info=${JSON.parse(info.content[0].text).base_url ? 'ok' : 'FAIL'} b64batch=${b64ok?'ok':'FAIL'} imageblock=${imgok?'ok':'FAIL'}`);
  await client.close();
}

for (const mode of modes) {
  await exercise('stdio', () => new StdioClientTransport({ command: PY, args: ['-m','immich_mcp_server','--transport','stdio'], env, stderr: 'ignore' }), mode);
}
for (const mode of modes) {
  await exercise('http', () => new StreamableHTTPClientTransport(new URL(process.env.MCP_URL)), mode);
}
