# Frontend image: build the Vue app, then serve the static files with nginx.
# Build context is ./frontend.

FROM node:22-alpine AS build

WORKDIR /app

# Lock file first, so code changes do not invalidate the npm layer.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# `npm run build` = vue-tsc type check + vite build -> /app/dist
RUN npm run build


FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
