# Production image for the OneInvoice frontend (Vite + React SPA) on Cloud Run.
#
# Two stages: build the static bundle with Node, then serve it with nginx on
# the port Cloud Run provides ($PORT, default 8080).
#
# Build (context = frontend-ori/):
#   docker build -t oneinvoice-frontend \
#     --build-arg VITE_API_BASE_URL=https://invoice-backend-xxxx.run.app ./frontend-ori

# ---- Build stage ----------------------------------------------------------
# Build with Yarn (via Corepack). npm crashes with "Exit handler never called!"
# in the Cloud Build environment regardless of Node/npm version; Yarn installs
# reliably and resolves the Linux-specific Rollup optional binary that Vite needs.
FROM node:22-bookworm-slim AS build

WORKDIR /app

# The backend API base URL is baked into the static bundle at build time.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Enable the Yarn shim bundled with Node.
RUN corepack enable

# Copy only package.json (Yarn resolves fresh; the committed package-lock.json
# is npm-specific and generated on Windows).
COPY package.json ./
RUN yarn install --network-timeout 600000

COPY . .
RUN yarn build

# ---- Runtime stage --------------------------------------------------------
FROM nginx:1.27-alpine

# SPA-aware nginx config with a runtime $PORT (Cloud Run) via envsubst template.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

ENV PORT=8080
EXPOSE 8080

# nginx:alpine auto-runs envsubst on /etc/nginx/templates/*.template at startup.
CMD ["nginx", "-g", "daemon off;"]
