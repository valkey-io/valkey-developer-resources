plugins {
    application
}

dependencies {
    implementation(project(":common"))
    implementation("io.valkey:valkey-glide:2.4.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    implementation("ch.qos.logback:logback-classic:1.4.14")
    implementation("org.slf4j:slf4j-api:2.0.11")
}

application {
    mainClass.set("com.valkey.sports.feeder.MainKt")
}
