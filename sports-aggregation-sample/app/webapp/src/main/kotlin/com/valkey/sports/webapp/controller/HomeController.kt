package com.valkey.sports.webapp.controller

import com.valkey.sports.model.GhlTeams
import com.valkey.sports.webapp.service.GameDataService
import org.springframework.stereotype.Controller
import org.springframework.ui.Model
import org.springframework.web.bind.annotation.GetMapping

@Controller
class HomeController(private val gameDataService: GameDataService) {

    @GetMapping("/")
    fun home(model: Model): String {
        model.addAttribute("games", gameDataService.getAllGames())
        model.addAttribute("trending", gameDataService.getTrendingMatches())
        model.addAttribute("winProbs", gameDataService.getWinProbabilities())
        model.addAttribute("teams", GhlTeams.byAbbreviation)
        return "index"
    }
}
