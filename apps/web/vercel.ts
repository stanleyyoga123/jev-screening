const backendUrl = process.env.BACKEND_URL;
if (!backendUrl) {
  throw new Error('Set BACKEND_URL in the Vercel frontend project to your API deployment origin.');
}

const backend = new URL(backendUrl);
if (backend.protocol !== 'https:' || backend.pathname !== '/' || backend.search || backend.hash || backend.username || backend.password) {
  throw new Error('BACKEND_URL must be an HTTPS origin, such as https://your-api.vercel.app, without /api or credentials.');
}

export const config = {
  framework: 'vite',
  installCommand: 'npm ci',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    { source: '/api/:path*', destination: `${backend.origin}/api/:path*` },
  ],
};
