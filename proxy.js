import http from 'http';
import httpProxy from 'http-proxy';

const proxy = httpProxy.createProxyServer({});

const server = http.createServer((req, res) => {
    if (req.url.startsWith('/api')) {
        // Forward to backend
        proxy.web(req, res, { target: 'http://localhost:8000' });
    } else {
        // Forward to frontend
        proxy.web(req, res, { target: 'http://localhost:5173' });
    }
});

console.log('Proxy listening on port 9000');
server.listen(9000);
