FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

ARG VITE_API_BASE_URL=
ARG VITE_PARTGRAPH_WORKBENCH_ENABLED=false
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_PARTGRAPH_WORKBENCH_ENABLED=${VITE_PARTGRAPH_WORKBENCH_ENABLED}

RUN npm run build

FROM nginx:1.29-alpine

ENV PARTGRAPH_API_UPSTREAM=http://api:8000

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1