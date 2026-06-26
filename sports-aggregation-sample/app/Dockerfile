# Multi-stage build for the Kotlin app modules
FROM eclipse-temurin:17-jdk AS builder

WORKDIR /app
COPY gradle gradle
COPY gradlew settings.gradle.kts build.gradle.kts ./
COPY common common
COPY feeder feeder
COPY webapp webapp

# Build all modules (valkey-glide 2.3.1 downloaded from Maven Central)
RUN ./gradlew :feeder:installDist :webapp:bootJar --no-daemon

# --- Feeder runtime ---
FROM eclipse-temurin:17-jre AS feeder
COPY --from=builder /app/feeder/build/install/feeder /app
WORKDIR /app
CMD ["bin/feeder"]

# --- Webapp runtime ---
FROM eclipse-temurin:17-jre AS webapp
COPY --from=builder /app/webapp/build/libs/*.jar /app/app.jar
WORKDIR /app
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
