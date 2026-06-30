FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

# Install dependencies in container
RUN npm install

# Copy source files
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
