import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

test('mudar somente o ícone renova a versão do cache offline',()=>{
  const root=mkdtempSync(join(tmpdir(),'tato-sw-'));
  const generator=fileURLToPath(new URL('./service-worker.mjs',import.meta.url));
  try {
    mkdirSync(join(root,'public'));
    mkdirSync(join(root,'out','icons'),{recursive:true});
    writeFileSync(join(root,'public','offline.html'),'Orientação offline');
    writeFileSync(join(root,'out','manifest.webmanifest'),'{}');
    for(const size of [192,512])writeFileSync(join(root,'out','icons',`${size}.png`),'ícone original');
    execFileSync(process.execPath,[generator],{cwd:root});
    let previous=readFileSync(join(root,'out','sw.js'),'utf8');
    execFileSync(process.execPath,[generator],{cwd:root});
    assert.equal(readFileSync(join(root,'out','sw.js'),'utf8'),previous);
    for(const size of [192,512]) {
      writeFileSync(join(root,'out','icons',`${size}.png`),'ícone atualizado');
      execFileSync(process.execPath,[generator],{cwd:root});
      const updated=readFileSync(join(root,'out','sw.js'),'utf8');
      assert.notEqual(updated,previous);
      previous=updated;
    }
  } finally {
    assert.equal(dirname(resolve(root)),resolve(tmpdir()));
    rmSync(root,{recursive:true,force:true});
  }
});
