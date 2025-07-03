# Stage 1: Install dependencies
FROM node:18-alpine AS deps
WORKDIR /usr/src/app

# Copy only package manifests and install
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: Build your React app for production
FROM deps AS build
WORKDIR /usr/src/app
# Copy the rest of the source
COPY . .
# Expose any needed build-time args (e.g. environment variables)
ARG REACT_APP_FIREBASE_API_KEY
ARG REACT_APP_FIREBASE_AUTH_DOMAIN
ARG REACT_APP_FIREBASE_PROJECT_ID
ARG REACT_APP_API_BASE_URL
ENV REACT_APP_FIREBASE_API_KEY=${REACT_APP_FIREBASE_API_KEY}
ENV REACT_APP_FIREBASE_AUTH_DOMAIN=${REACT_APP_FIREBASE_AUTH_DOMAIN}
ENV REACT_APP_FIREBASE_PROJECT_ID=${REACT_APP_FIREBASE_PROJECT_ID}
ENV REACT_APP_API_BASE_URL=${REACT_APP_API_BASE_URL}

# Run the production build
RUN npm run build

# Stage 3: Production server using nginx
FROM nginx:stable-alpine AS prod
COPY --from=build /usr/src/app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# Stage 4: Development server with hot reload
FROM deps AS dev
WORKDIR /usr/src/app
# Source files will be mounted in at runtime, so no COPY here
EXPOSE 3000
# Start CRA dev server
CMD ["npm", "start"]
