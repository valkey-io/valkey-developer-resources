plugins {
    id("org.jetbrains.kotlin.plugin.spring")
    id("org.springframework.boot")
    id("io.spring.dependency-management")
}

dependencies {
    implementation(project(":common"))
    implementation("io.valkey:valkey-glide:2.4.0")
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-thymeleaf")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
}
