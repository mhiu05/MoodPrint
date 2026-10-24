FROM node:22.16.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html tsconfig*.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build && ! find dist -name '*.map' -print -quit | grep -q .

FROM caddy:2.10.2-alpine
COPY --from=build /app/dist /srv
