import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { generateProjectRetentionAudit } from './result-store.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const report = await generateProjectRetentionAudit({ rootDir, keepCount: 3 });
console.log(JSON.stringify({
  status: report.status,
  audit_path: report.audit_path,
  project_count: report.audit.project_count,
  kept: report.kept,
  pending_delete_count: report.pending_deletion.length,
}, null, 2));
