#!/usr/bin/env node
import fs from 'fs';
import { run } from './engine.js';

function parseArgs(argv){
  const args = { mode:'dialog', input:'-' };
  for (let i=2;i<argv.length;i++){
    const a = argv[i];
    if (a === '--mode' && argv[i+1]) { args.mode = argv[++i]; continue; }
    if (!a.startsWith('-')) { args.input = a; continue; }
  }
  return args;
}

async function main(){
  const args = parseArgs(process.argv);
  const raw = args.input === '-' ? fs.readFileSync(0,'utf8') : fs.readFileSync(args.input,'utf8');
  const json = JSON.parse(raw);
  const out = run(json, { mode: args.mode });
  process.stdout.write(JSON.stringify(out, null, 2));
}

main().catch(err => { console.error(err.stack||String(err)); process.exit(1); });


