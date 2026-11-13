// 检查 B 站深采是否已全部完成。
// 退出码 0 = 全部 finished（调用方应跳过本轮，不启动采集）
// 退出码 1 = 还有未完成账号（正常继续采集）
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..', '..');
const stateFile = path.join(root, '1AMdata', '_state', 'deep_collect.json');

try {
  const j = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
  const accounts = Object.values(j.accounts || {});
  if (!accounts.length) process.exit(1);
  const pending = accounts.filter((a) => a.stage !== 'finished');
  if (pending.length === 0) process.exit(0);
  process.exit(1);
} catch {
  // 状态文件读不到就不要误判，按"继续"处理
  process.exit(1);
}
