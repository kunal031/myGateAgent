# Dependencies, build, then a runtime carrying neither. The standalone
# output bundles only the files the server actually imports, so the final
# image has no node_modules at all.
FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
# ci rather than install: the lockfile is the input, and a silently
# resolved different version is how a build stops matching local.
RUN npm ci


FROM node:22-alpine AS build

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Baked in at build time, because Next inlines NEXT_PUBLIC_* into the
# client bundle -- setting it at runtime would have no effect.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build


FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN apk add --no-cache curl \
 && addgroup -g 10001 -S app \
 && adduser -u 10001 -S app -G app

WORKDIR /app

# The standalone server, plus the two directories it does not inline.
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public

USER app
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
