import http from 'http';
import jwt from 'jsonwebtoken';

const ALLOW = {
  calendar_freebusy: { apps: new Set([process.env.SCHEDULER_APPID || '' ]), purpose: 'meeting_scheduling' },
  project_info_share: { apps: new Set([process.env.PMO_APPID || '' ]), purpose: 'project_collab' }
};

function getCallerAppId(authz) {
  if (!authz || !authz.startsWith('Bearer ')) throw new Error('Missing Authorization');
  const token = authz.slice(7);
  const claims = jwt.decode(token) || {};
  return claims.appid || claims.azp;
}

function enforce(tool, callerAppId, purpose) {
  const c = ALLOW[tool];
  if (!c) throw new Error('Unknown tool');
  if (!c.apps.has(callerAppId)) throw new Error('Caller not allowed');
  if (c.purpose !== purpose) throw new Error('Purpose mismatch');
}

const srv = http.createServer(async (req, res) => {
  if (req.method !== 'POST') { res.statusCode = 405; return res.end(); }
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', async () => {
    try {
      const input = JSON.parse(body || '{}');
      const purpose = req.headers['x-purpose'] || '';
      const callerAppId = getCallerAppId(req.headers['authorization']);
      const tool = input.tool;
      enforce(tool, callerAppId, purpose);
      res.setHeader('Content-Type','application/json');
      res.end(JSON.stringify({ allowed:true, tool, purpose, minimized:true }));
    } catch (e) {
      res.statusCode = 403;
      res.setHeader('Content-Type','application/json');
      res.end(JSON.stringify({ allowed:false, reason: e.message || 'Denied' }));
    }
  });
});
srv.listen(8080, () => console.log('MCP-like server on :8080'));