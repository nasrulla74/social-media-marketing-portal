FROM node:22-alpine
WORKDIR /app
COPY package.json /app/package.json
RUN npm install
COPY app /app/app
COPY next.config.mjs /app/next.config.mjs
COPY tsconfig.json /app/tsconfig.json
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
