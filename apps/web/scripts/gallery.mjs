import { mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const output=fileURLToPath(new URL('../../../test-results/ui-gallery/',import.meta.url));
// Diretório fixo exclusivo das capturas; nunca recebe caminho do usuário.
rmSync(output,{recursive:true,force:true});
mkdirSync(output,{recursive:true});
const require=createRequire(import.meta.url);
const result=spawnSync(process.execPath,[require.resolve('@playwright/test/cli'),'test','--config','playwright.gallery.config.ts'],{stdio:'inherit'});
process.exit(result.status??1);
