FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npx prisma generate --schema prisma/postgres/schema.prisma
RUN npm run build
RUN npm prune --omit=dev && npm cache clean --force
RUN npx prisma generate --schema prisma/postgres/schema.prisma

FROM node:22-alpine AS runtime

RUN apk add --no-cache openssl \
    && addgroup -S app \
    && adduser -S app -G app

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=8080

COPY --from=builder --chown=app:app /app/package.json ./package.json
COPY --from=builder --chown=app:app /app/node_modules ./node_modules
COPY --from=builder --chown=app:app /app/build ./build

USER app
EXPOSE 8080
CMD ["npm", "run", "start"]
