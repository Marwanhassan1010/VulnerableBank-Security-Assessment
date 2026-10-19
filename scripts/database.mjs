import EmbeddedPostgres from 'embedded-postgres';
import {existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {randomBytes} from 'node:crypto';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const runtime=path.join(root,'.runtime');mkdirSync(runtime,{recursive:true});
const configPath=path.join(runtime,'local.json');
let config;
if(existsSync(configPath))config=JSON.parse(readFileSync(configPath));
else{const password=randomBytes(24).toString('hex');config={dbPassword:password,databaseUrl:`postgresql+psycopg://vblab:${password}@127.0.0.1:55432/vulnerablebank`};writeFileSync(configPath,JSON.stringify(config,null,2));}
const pg=new EmbeddedPostgres({databaseDir:path.join(root,'data','postgres'),user:'vblab',password:config.dbPassword,port:55432,persistent:true,authMethod:'scram-sha-256',initdbFlags:['--encoding=UTF8','--locale=C'],postgresFlags:['-h','127.0.0.1','-c','max_connections=50'],onLog:msg=>process.stderr.write(String(msg)),onError:msg=>process.stderr.write(String(msg)+'\n')});
if(!existsSync(path.join(root,'data','postgres','PG_VERSION')))await pg.initialise();
await pg.start();
const client=pg.getPgClient();await client.connect();
const found=await client.query("SELECT 1 FROM pg_database WHERE datname = 'vulnerablebank'");
if(!found.rowCount)await client.query('CREATE DATABASE vulnerablebank');
await client.end();
writeFileSync(path.join(runtime,'database-ready'),String(process.pid));
console.log('PostgreSQL ready on 127.0.0.1:55432');
async function stop(){await pg.stop();process.exit(0);}
process.on('SIGINT',stop);process.on('SIGTERM',stop);
setInterval(()=>{},60000);

