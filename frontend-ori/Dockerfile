# Production image for the OneInvoice frontend (Vite + React SPA) on Cloud Run.
#
# Two stages: build the static bundle with Node, then serve it with nginx on
# the port Cloud Run provides ($PORT, default 8080).
#
# Build (context = frontend-ori/):
#   docker build -t oneinvoice-frontend \
#     --build-arg VITE_API_BASE_URL=https://invoice-backend-xxxx.run.app ./frontend-ori

# ---- Build stage ----------------------------------------------------------
# node:22 (glibc) ships a fixed npm (10.9.x). The older npm 10.8.2 bundled with
# node:20-slim crashes with "Exit handler never called!" during install.
FROM node:22-bookworm-slim AS build

WORKDIR /app

# The backend API base URL is baked into the static bundle at build time.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    npm_config_update_notifier=false \
    npm_config_fund=false \
    npm_config_audit=false

COPY package.json package-lock.json ./
# Use `npm install` (not `npm ci`): the lockfile is generated on Windows and
# `npm ci` fails to install the Linux-specific Rollup optional binary, which
# would break `vite build`. `npm install` reconciles platform optional deps.
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ---- Runtime stage --------------------------------------------------------
FROM nginx:1.27-alpine

# SPA-aware nginx config with a runtime $PORT (Cloud Run) via envsubst template.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

ENV PORT=8080
EXPOSE 8080

# nginx:alpine auto-runs envsubst on /etc/nginx/templates/*.template at startup.
CMD ["nginx", "-g", "daemon off;"]
