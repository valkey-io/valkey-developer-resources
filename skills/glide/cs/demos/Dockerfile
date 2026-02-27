FROM mcr.microsoft.com/dotnet/sdk:8.0
ARG DEMO
WORKDIR /app
COPY ${DEMO}.csproj ./demo.csproj
COPY ${DEMO}.cs ./Program.cs
RUN dotnet restore demo.csproj
CMD ["dotnet", "run", "--project", "demo.csproj"]
