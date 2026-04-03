import http from 'k6/http';
import { check, sleep } from 'k6';

const baseUrl = __ENV.BASE_URL || 'https://127.0.0.1:8443';
const vus = Number(__ENV.VUS || 20);
const durationSeconds = Number(__ENV.DURATION_SECONDS || 30);
const pauseMs = Number(__ENV.PAUSE_MS || 200);

const endpoints = [
  '/api/health',
  '/api/cid4/conformer/1',
  '/api/cid4/structure/2d',
  '/api/cid4/compound',
  '/api/algorithms/pathway',
  '/api/algorithms/bioactivity',
  '/api/algorithms/taxonomy',
];

export const options = {
  vus,
  duration: `${durationSeconds}s`,
  insecureSkipTLSVerify: true,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
  },
};

export default function () {
  const endpoint = endpoints[__ITER % endpoints.length];
  const response = http.get(`${baseUrl}${endpoint}`, {
    headers: {
      Accept: 'application/json',
    },
    tags: {
      endpoint,
      backend: 'crow',
    },
  });

  check(response, {
    'status is 200': (reply) => reply.status === 200,
    'content type is json': (reply) => String(reply.headers['Content-Type'] || '').includes('application/json'),
  });

  sleep(pauseMs / 1000);
}
