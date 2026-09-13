import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {Miniflare, convertV4MiniflareOptions} from 'miniflare';

export async function installationFixture(directory) {
  const config = JSON.parse(await readFile(path.join(directory,'wrangler.generated.json'),'utf8'));
  if (!config.vars.HISTORY_ORIGIN.endsWith('.example.invalid')) throw Error('Only a synthetic installation is permitted');
  const mf = new Miniflare(convertV4MiniflareOptions({
    cf:false,
    modulesRoot:directory,
    modules:['worker.js','hosted.js','security.js','history-reader.js','player-data.js','report-stream.js','support.js','report-ref.json','b50.webp'].map(name=>({
      type:name.endsWith('.json')?'Text':name.endsWith('.webp')?'Data':'ESModule',path:path.join(directory,name),
    })),
    compatibilityDate:config.compatibility_date,
    d1Databases:{HISTORY_DB:'synthetic-installation'},r2Buckets:['HISTORY_OBJECTS'],bindings:config.vars,
  }));
  try {
  const db = await mf.getD1Database('HISTORY_DB');
  const statements = JSON.parse(await readFile(path.join(directory,'../schema.json'),'utf8'));
  for (const statement of statements) await db.prepare(statement).run();
  const ref=JSON.parse(await readFile(path.join(directory,'report-ref.json'),'utf8'));
  const bucket=await mf.getR2Bucket('HISTORY_OBJECTS');
  await bucket.put(ref.key,await readFile(path.join(directory,'report.html')),{customMetadata:{sha256:ref.sha256,'report-flags':JSON.stringify(ref.flags)}});
  return {mf,db,config};
  } catch(error) {await mf.dispose();throw error;}
}
