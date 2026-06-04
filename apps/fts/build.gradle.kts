plugins {
    id("java")
    id("application")
    id("com.google.osdetector") version "1.7.3"
    id("com.diffplug.spotless") version "6.25.0"
    id("jacoco")
    id("org.openjfx.javafxplugin") version "0.1.0"
}

group = "com.flicenjoyer"
version = "0.1.0"

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(26))
    }
}

javafx {
    version = "26"
    modules("javafx.controls", "javafx.fxml", "javafx.media", "javafx.swing")
}

repositories {
    mavenCentral()
    mavenLocal()
}

sourceSets {
    create("integrationTest") {
        compileClasspath += sourceSets.main.get().output
        runtimeClasspath += sourceSets.main.get().output
    }
}

configurations["integrationTestImplementation"].extendsFrom(configurations.implementation.get())
configurations["integrationTestRuntimeOnly"].extendsFrom(configurations.runtimeOnly.get())

dependencies {
    implementation("io.valkey:valkey-glide:2.4.1:${osdetector.classifier}")
    implementation("org.yaml:snakeyaml:2.3")
    implementation("org.postgresql:postgresql:42.7.4")
    implementation("com.zaxxer:HikariCP:6.2.1")

    testImplementation("org.junit.jupiter:junit-jupiter:5.11.3")
    testImplementation("org.mockito:mockito-core:5.14.2")
    testImplementation("org.mockito:mockito-junit-jupiter:5.14.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")

    "integrationTestImplementation"("org.junit.jupiter:junit-jupiter:5.11.3")
    "integrationTestImplementation"("org.testcontainers:testcontainers:1.21.0") {
        exclude(group = "com.google.protobuf")
    }
    "integrationTestImplementation"("org.testcontainers:junit-jupiter:1.21.0")
    "integrationTestImplementation"("com.github.docker-java:docker-java-api:3.4.1")
    "integrationTestImplementation"("com.github.docker-java:docker-java-transport-zerodep:3.4.1")
    "integrationTestRuntimeOnly"("org.junit.platform:junit-platform-launcher")
    "integrationTestRuntimeOnly"("org.slf4j:slf4j-simple:2.0.16")
}

application {
    mainClass.set("com.flicenjoyer.FlicEnjoyerApp")
}

jacoco {
    toolVersion = "0.8.14"
}

tasks.test {
    useJUnitPlatform()
    jvmArgs(
        "--add-opens", "java.base/java.lang=ALL-UNNAMED",
        "--add-opens", "java.base/java.lang.invoke=ALL-UNNAMED",
        "--add-opens", "java.base/java.util=ALL-UNNAMED",
        "-Dnet.bytebuddy.experimental=true"
    )
    finalizedBy(tasks.jacocoTestReport)
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required.set(true)
        html.required.set(true)
    }
}

tasks.jacocoTestCoverageVerification {
    classDirectories.setFrom(
        files(classDirectories.files.map {
            fileTree(it) {
                exclude(
                    "com/flicenjoyer/ui/**",
                    "com/flicenjoyer/db/**",
                    "com/flicenjoyer/FlicEnjoyerApp*",
                    "com/flicenjoyer/ResetData*"
                )
            }
        })
    )
    violationRules {
        rule {
            limit {
                minimum = "0.70".toBigDecimal()
            }
        }
    }
}

tasks.check {
    dependsOn(tasks.jacocoTestCoverageVerification)
    dependsOn("spotlessCheck")
}

val integrationTest by tasks.registering(Test::class) {
    description = "Runs integration tests against a live Valkey container."
    group = "verification"
    testClassesDirs = sourceSets["integrationTest"].output.classesDirs
    classpath = sourceSets["integrationTest"].runtimeClasspath
    useJUnitPlatform()
    shouldRunAfter(tasks.test)
    environment("DOCKER_HOST", "unix:///var/run/docker.sock")
}

spotless {
    java {
        googleJavaFormat()
    }
}

tasks.register<JavaExec>("resetData") {
    description = "Erases all catalog and watch history data from Valkey and cleans local media files."
    group = "application"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("com.flicenjoyer.ResetData")
}

tasks.register<JavaExec>("seedData") {
    description = "Seeds fake catalog + watch history for demos/benchmarks. Pass catalog count as arg (default 200)."
    group = "application"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("com.flicenjoyer.SeedData")
}

tasks.register<JavaExec>("unseedData") {
    description = "Removes all seeded demo data (bench-* catalog, s* watch history)."
    group = "application"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("com.flicenjoyer.UnseedData")
}

tasks.register<JavaExec>("benchmark") {
    description = "Runs CLI benchmark comparing DB-direct vs Valkey-cached throughput."
    group = "application"
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("com.flicenjoyer.BenchmarkCli")
}

tasks.register<Exec>("dbBackup") {
    description = "Backs up the PostgreSQL database to backups/flicenjoyer.sql"
    group = "application"
    doFirst { mkdir("backups") }
    commandLine("bash", "-c",
        "docker exec flicenjoyer-postgres pg_dump -U flicenjoyer --clean --if-exists flicenjoyer > backups/flicenjoyer.sql")
}

tasks.register<Exec>("dbRestore") {
    description = "Restores the PostgreSQL database from backups/flicenjoyer.sql"
    group = "application"
    commandLine("bash", "-c",
        "docker exec -i flicenjoyer-postgres psql -U flicenjoyer -d flicenjoyer < backups/flicenjoyer.sql")
}


