# Stage 1: Build the Vite React App
FROM node:20-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve the App
FROM node:20-alpine
WORKDIR /app

# Install 'serve' globally to host the static files
RUN npm install -g serve

# Copy the built 'dist' directory from the previous stage
COPY --from=build /app/dist ./dist

# Cloud Run automatically sets the PORT environment variable (default 8080)
ENV PORT=8080
EXPOSE 8080

# Run the serve command, pointing to the dist folder and listening on PORT
CMD ["sh", "-c", "serve -s dist -l tcp://0.0.0.0:$PORT"]
