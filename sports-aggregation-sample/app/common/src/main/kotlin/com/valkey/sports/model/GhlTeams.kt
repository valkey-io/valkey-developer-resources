package com.valkey.sports.model

object GhlTeams {
    val teams = listOf(
        // Nova Division
        Team("ARC", "Wolves", "Arcturus", "Inner Rim", "Nova"),
        Team("VEG", "Lancers", "Vega", "Inner Rim", "Nova"),
        Team("SOL", "Flares", "Sol Station", "Inner Rim", "Nova"),
        Team("PRX", "Phantoms", "Proxima", "Inner Rim", "Nova"),
        Team("SIR", "Ice Hawks", "Sirius", "Inner Rim", "Nova"),
        Team("ALT", "Comets", "Altair", "Inner Rim", "Nova"),
        Team("CAS", "Storm", "Cassiopeia", "Inner Rim", "Nova"),
        Team("POL", "Bears", "Polaris", "Inner Rim", "Nova"),
        // Pulsar Division
        Team("CYG", "Reapers", "Cygnus", "Inner Rim", "Pulsar"),
        Team("AND", "Titans", "Andromeda", "Inner Rim", "Pulsar"),
        Team("LYR", "Bolts", "Lyra", "Inner Rim", "Pulsar"),
        Team("AQL", "Talons", "Aquila", "Inner Rim", "Pulsar"),
        Team("ORI", "Hunters", "Orion", "Inner Rim", "Pulsar"),
        Team("DRA", "Serpents", "Draco", "Inner Rim", "Pulsar"),
        Team("CEN", "Chargers", "Centauri", "Inner Rim", "Pulsar"),
        Team("GEM", "Twins", "Gemini", "Inner Rim", "Pulsar"),
        // Nebula Division
        Team("NEB", "Knights", "Nebula Prime", "Outer Rim", "Nebula"),
        Team("PLR", "Frost", "Pulsar Bay", "Outer Rim", "Nebula"),
        Team("HYD", "Krakens", "Hydra", "Outer Rim", "Nebula"),
        Team("PHX", "Flames", "Phoenix", "Outer Rim", "Nebula"),
        Team("CRT", "Rovers", "Crater", "Outer Rim", "Nebula"),
        Team("LEO", "Lions", "Leo Major", "Outer Rim", "Nebula"),
        Team("AQR", "Tides", "Aquarius", "Outer Rim", "Nebula"),
        Team("SCR", "Stingers", "Scorpius", "Outer Rim", "Nebula"),
        // Void Division
        Team("VOI", "Wraiths", "Void Station", "Outer Rim", "Void"),
        Team("TAU", "Rams", "Taurus", "Outer Rim", "Void"),
        Team("PEG", "Stallions", "Pegasus", "Outer Rim", "Void"),
        Team("ERI", "Glaciers", "Eridanus", "Outer Rim", "Void"),
        Team("LUP", "Howlers", "Lupus", "Outer Rim", "Void"),
        Team("CRV", "Ravens", "Corvus", "Outer Rim", "Void"),
        Team("PER", "Blades", "Perseus", "Outer Rim", "Void"),
        Team("VEL", "Drifters", "Vela", "Outer Rim", "Void"),
    )

    val byAbbreviation = teams.associateBy { it.abbreviation }

    fun displayName(abbreviation: String): String {
        val team = byAbbreviation[abbreviation] ?: return abbreviation
        return "${team.city} ${team.name}"
    }
}
