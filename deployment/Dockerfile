FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS backend
WORKDIR /src
COPY dotnet/ dotnet/
RUN dotnet restore dotnet/AetherGrid.Server/AetherGrid.Server.csproj --locked-mode
RUN dotnet publish dotnet/AetherGrid.Server/AetherGrid.Server.csproj -c Release -o /app --no-restore
COPY --from=frontend /src/frontend/dist/ /app/wwwroot/
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=backend /app/ ./
USER app
ENV ASPNETCORE_HTTP_PORTS=8080 AETHER_DB=/data/aethergrid.db AETHER_PRODUCTION=true
EXPOSE 8080
ENTRYPOINT ["dotnet","AetherGrid.Server.dll"]
