import {build} from 'esbuild';
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const sources=['DashboardContent.jsx','visuals.jsx','model.mjs','ui.jsx','main.jsx'];
const hash=createHash('sha256');
sources.forEach(path=>hash.update(readFileSync(new URL(path,import.meta.url))));
const result=await build({entryPoints:[new URL('main.jsx',import.meta.url).pathname],bundle:true,minify:true,write:false,format:'iife',target:'es2020',define:{'process.env.NODE_ENV':'"production"'},legalComments:'eof'});
writeFileSync(new URL('../sp500.js',import.meta.url),'// Source SHA-256: '+hash.digest('hex')+'\n'+result.outputFiles[0].text);
