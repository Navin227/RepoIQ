FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_DEMO_API_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_DEMO_API_URL=$VITE_DEMO_API_URL

RUN npm run build

FROM node:22-alpine

WORKDIR /app

COPY --from=build /app/package*.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]