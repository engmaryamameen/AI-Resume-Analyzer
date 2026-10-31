FROM node:22-slim AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN --mount=type=cache,id=margin-npm,target=/root/.npm npm ci --ignore-scripts --prefer-offline --fetch-timeout=30000 --fetch-retries=2
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 BACKEND_URL=http://api:8000
RUN npm run build
FROM node:22-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
