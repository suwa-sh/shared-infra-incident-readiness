#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import process from "node:process";
import mermaid from "mermaid";

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("usage: node scripts/check_mermaid.mjs <markdown> [...]");
  process.exit(2);
}

let failures = 0;
let diagrams = 0;
const fence = /```mermaid\s*\n([\s\S]*?)\n```/g;

for (const file of files) {
  const markdown = await readFile(file, "utf8");
  for (const match of markdown.matchAll(fence)) {
    diagrams += 1;
    const line = markdown.slice(0, match.index).split("\n").length;
    try {
      await mermaid.parse(match[1], { suppressErrors: true });
    } catch (error) {
      failures += 1;
      console.error(`${file}:${line}: ${error.message ?? String(error)}`);
    }
  }
}

if (failures > 0) {
  console.error(`[NG] ${failures} invalid Mermaid diagram(s)`);
  process.exit(1);
}
console.log(`[OK] ${diagrams} Mermaid diagram(s) in ${files.length} file(s)`);
