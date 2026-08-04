FROM node:20-alpine AS build
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY web/ ./
RUN VITE_AT_API_BASE_URL=/api npm run build

FROM nginx:alpine
COPY --from=build /build/dist /usr/share/nginx/html
COPY deploy/docker/nginx.conf.template /etc/nginx/conf.d/default.conf
